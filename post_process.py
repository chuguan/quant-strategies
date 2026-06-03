#!/usr/bin/env python
"""
数据后处理流水线 — 采集完API数据后自动执行
1. 补volume（从新浪API拉缺失的）
2. 刷新技术指标（WR/KDJ/MACD/DIF）
3. 计算特征（d1-d5/slope5/t4_shadow/cons_up/peak_decay）
4. 补high/low（从腾讯K线拉缺失的）
"""
import sqlite3, os, sys, subprocess, json, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

sys.path.insert(0, SCRIPTS_DIR)
from db_config import get_config

def log(msg):
    print(f'  {msg}')

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

NOW = datetime.now()
TODAY_STR = get_today()

# 获取最新交易日（非交易日返回None）
def get_latest_trading_day():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('SELECT MAX(date) FROM data_cache WHERE close > 0')
    dt = c.fetchone()[0]
    conn.close()
    return dt

LATEST_DT = get_latest_trading_day()
if not LATEST_DT:
    print('❌ data_cache无数据，退出')
    sys.exit(1)

print(f'\n≡≡≡ 后处理流水线 {NOW.strftime("%Y-%m-%d %H:%M")} ≡≡≡')
print(f'  最新交易日: {LATEST_DT}')

# ════════════ 1. 补volume ════════════
print(f'\n▶ [1/4] 补volume({LATEST_DT})...')
conn = sqlite3.connect(DB_PATH, timeout=60)
c = conn.cursor()
c.execute('SELECT code, name FROM data_cache WHERE date=? AND (volume IS NULL OR volume=0) AND close>0', (LATEST_DT,))
missing_vol_raw = c.fetchall()
# 排除剔除清单
try:
    exc_codes = set(r[0] for r in c.execute('SELECT code FROM excluded_stocks WHERE active=1').fetchall())
except:
    exc_codes = set()
missing_vol = [(c, n) for c, n in missing_vol_raw if c not in exc_codes]
conn.close()

if missing_vol:
    log(f'需补volume: {len(missing_vol)}只')
    BATCH = 50
    fixed = 0
    for i in range(0, len(missing_vol), BATCH):
        batch = missing_vol[i:i+BATCH]
        codes = [r[0] for r in batch]
        symbols = ','.join(f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in codes)
        url = f'http://qt.gtimg.cn/q={symbols}'
        try:
            r = subprocess.run(['curl', '-s', '--max-time', '8', url], capture_output=True, timeout=12)
            text = r.stdout.decode('gbk', errors='ignore')
            conn2 = sqlite3.connect(DB_PATH, timeout=30)
            c2 = conn2.cursor()
            for line in text.strip().split(';'):
                if not line or '=' not in line: continue
                try:
                    parts = line.split('=')[1].strip().strip('"').split('~')
                    if len(parts) < 40: continue
                    code = parts[2]
                    vol = float(parts[6]) if parts[6] else 0
                    if vol > 0:
                        c2.execute('UPDATE data_cache SET volume=? WHERE date=? AND code=?', (vol, LATEST_DT, code))
                        fixed += 1
                except: pass
            conn2.commit()
            conn2.close()
        except: pass
    log(f'  补完volume: {fixed}只')
else:
    log('  无需补充')

# ════════════ 2. 刷新技术指标 ════════════
print(f'\n▶ [2/4] 刷新技术指标({LATEST_DT})...')
from refresh_tech_indicators import refresh_technical_indicators
updated = refresh_technical_indicators()
# refresh_technical_indicators already prints its own output
log(f'  技术指标刷新: {updated}条')

# ════════════ 3. 补high/low ════════════
print(f'\n▶ [3/4] 补high/low({LATEST_DT})...')
conn = sqlite3.connect(DB_PATH, timeout=30)
c = conn.cursor()
c.execute('SELECT code, close FROM data_cache WHERE date=? AND (high IS NULL OR high=0) AND close>0', (LATEST_DT,))
missing_hl = c.fetchall()
conn.close()

if missing_hl:
    log(f'需补high/low: {len(missing_hl)}只')
    fixed = 0
    BATCH = 30
    for i in range(0, len(missing_hl), BATCH):
        batch = missing_hl[i:i+BATCH]
        codes = [r[0] for r in batch]
        symbols = ','.join(f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in codes)
        url = f'http://qt.gtimg.cn/q={symbols}'
        try:
            r = subprocess.run(['curl', '-s', '--max-time', '8', url], capture_output=True, timeout=12)
            text = r.stdout.decode('gbk', errors='ignore')
            conn2 = sqlite3.connect(DB_PATH, timeout=30)
            c2 = conn2.cursor()
            for line in text.strip().split(';'):
                if not line or '=' not in line: continue
                try:
                    parts = line.split('=')[1].strip().strip('"').split('~')
                    if len(parts) < 40: continue
                    code = parts[2]
                    high = float(parts[33]) if len(parts) > 33 and parts[33] else 0
                    low = float(parts[34]) if len(parts) > 34 and parts[34] else 0
                    if high > 0 and low > 0:
                        c2.execute('UPDATE data_cache SET high=?, low=? WHERE date=? AND code=?',
                                  (high, low, LATEST_DT, code))
                        fixed += 1
                except: pass
            conn2.commit()
            conn2.close()
        except: pass
    log(f'  补完high/low: {fixed}只')
else:
    log('  无需补充')

# ════════════ 4. 计算特征（如果需要） ════════════
print(f'\n▶ [4/4] 计算特征({LATEST_DT})...')
conn = sqlite3.connect(DB_PATH, timeout=30)
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM features_cache WHERE date=?', (LATEST_DT,))
has_feat = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM data_cache WHERE date=? AND close>0', (LATEST_DT,))
total_stocks = c.fetchone()[0]
conn.close()

if has_feat < total_stocks * 0.95:
    log(f'  特征缺失({has_feat}/{total_stocks}), 开始计算...')
    from compute_features import compute_features
    feat_count = compute_features()
    log(f'  特征计算: {feat_count}条')
else:
    log(f'  特征已齐全({has_feat}条)')

# ════════════ 5. 刷新剔除清单 ════════════
print(f'\n▶ [5/5] 刷新剔除清单...')
try:
    from refresh_excluded import refresh_st_excluded
    n = refresh_st_excluded()
    log(f'  剔除清单更新: 新增{n}只' if n else '  剔除清单: 无变化')
except Exception as e:
    log(f'  剔除清单刷新跳过: {e}')

# ════════════ 验证 ════════════
print(f'\n≡≡≡ 数据完整性验证 {LATEST_DT} ≡≡≡')
conn = sqlite3.connect(DB_PATH, timeout=10)
c = conn.cursor()

# 活跃股（排除剔除清单）
try:
    exc = set(r[0] for r in c.execute('SELECT code FROM excluded_stocks WHERE active=1').fetchall())
except:
    exc = set()
c.execute('SELECT code FROM data_cache WHERE date=? AND close>0', (LATEST_DT,))
active = [r[0] for r in c.fetchall() if r[0] not in exc]
total_active = len(active)
total_all = c.execute('SELECT COUNT(*) FROM data_cache WHERE date=?', (LATEST_DT,)).fetchone()[0]

print(f'  总股票: {total_all}只 | 活跃(剔除后): {total_active}只 | 剔除: {len(exc)}只')
print()

pass_all = True
checks = [
    ('close',     'close>0',                         total_active),
    ('volume',    'volume>0',                        total_active),
    ('high',      'high>0',                          total_active),
    ('low',       'low>0',                           total_active),
    ('p',         'p IS NOT NULL',                   total_active),
    ('cl',        'cl IS NOT NULL',                  total_active),
    ('wr_val',    'wr_val IS NOT NULL',               total_active),
    ('k_val',     'k_val IS NOT NULL',                total_active),
    ('d_val',     'd_val IS NOT NULL',                total_active),
    ('j_val',     'j_val IS NOT NULL',                total_active),
    ('dif_val',   'dif_val IS NOT NULL',             total_active),
]

for name, cond, expected in checks:
    # 在活跃股范围内检查
    codes_str = ','.join(["'%s'" % c for c in active])
    cnt = c.execute("SELECT COUNT(*) FROM data_cache WHERE date=? AND %s AND code IN (%s)" % (cond, codes_str), (LATEST_DT,)).fetchone()[0]
    pct = cnt * 100 / expected if expected else 0
    ok = cnt == expected
    status = '✅' if ok else '❌'
    if not ok: pass_all = False
    print(f'  {status} {name:15s} {cnt:>4d}/{expected} = {pct:5.1f}%')

# features_cache
c.execute("SELECT COUNT(*) FROM features_cache WHERE date=? AND code IN (%s)" % codes_str, (LATEST_DT,))
feat = c.fetchone()[0]
feat_ok = feat == total_active
if not feat_ok: pass_all = False
print(f'  {"✅" if feat_ok else "❌"} features        {feat:>4d}/{total_active} = {feat*100/total_active:5.1f}%')

# 全体结论
print()
if pass_all:
    print(f'  ✅ 数据完整性验证通过 — 活跃{total_active}只全部完整')
else:
    print(f'  ⚠️ 有缺失，请检查以上❌项目')

conn.close()

print(f'\n✅ 后处理完成 {datetime.now().strftime("%H:%M:%S")}')
