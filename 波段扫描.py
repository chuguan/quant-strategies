#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
波段交易系统 — 早盘/尾盘扫描
================================
每天跑两轮：早盘(9:30)选买入，尾盘(14:50)选买入+检查持仓卖出
自动记录完整买卖闭环
"""
import json, sqlite3, os, re, subprocess, sys, time
from datetime import datetime, date, timedelta

# 邮件
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'lib'))
try:
    from send_email import dispatch_email
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False

# ========== 路径 ==========
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
CACHE_DIR = r'C:\Users\12546\AppData\Local\hermes\hermes-agent\cache'
JOURNAL = os.path.join(SCRIPTS_DIR, '波段交易日记.json')

# ========== 交易规则 ==========
MAX_HOLD_DAYS = 10          # 最长持有10天
TAKE_PROFIT_PCT = 8.0       # 止盈: 赚超8%+J>85
STOP_LOSS_PCT = -7.0        # 止损: 亏超-7%
STOP_LOSS_STRONG = -10.0    # 强信号止损

# ========== 数据工具 ==========
def get_cache(code):
    m = "sh" if code.startswith(("6","9")) else "sz"
    p = os.path.join(CACHE_DIR, f"{m}{code}.json")
    if not os.path.exists(p): return None
    with open(p, encoding='utf-8') as f: return json.load(f)

def _cache_idx(cache, dt):
    """从cache中找到dt对应的索引，适配bt_data(cache)和cache两种日期格式"""
    dt_norm = dt.replace('-', '')
    dt_dash = f"{dt_norm[:4]}-{dt_norm[4:6]}-{dt_norm[6:8]}"
    return next((i for i,d in enumerate(cache) if d['date']==dt_norm or d['date']==dt_dash), -1)

def get_vr(cache, dt):
    if not cache: return 1.0
    idx = _cache_idx(cache, dt)
    if idx<20: return 1.0
    avg = sum(cache[i]['volume'] for i in range(idx-20,idx))/20
    return cache[idx]['volume']/avg if avg>0 else 1.0

def get_h10(cache, dt):
    if not cache: return 0
    idx = _cache_idx(cache, dt)
    if idx<9: return 0
    return max(cache[i]['high'] for i in range(idx-9,idx+1))

def get_main(code, dt, cur):
    """主力净流入(万元)"""
    cur.execute("SELECT main_net FROM tushare_cache WHERE code=? AND date=?", (code, dt.replace('-','')))
    r = cur.fetchone()
    return r[0]/1e4 if r and r[0] else 0

def get_live_price(code):
    """获取实时行情"""
    pref = "sh" if code.startswith(("6","9")) else "sz"
    try:
        rt = subprocess.run(["curl","-s","--max-time","3",f"https://qt.gtimg.cn/q={pref}{code}"],
                          capture_output=True, timeout=5)
        raw = rt.stdout.decode("gbk", errors="replace")
        m = re.search(r'"([^"]+)"', raw)
        if m:
            f = m.group(1).split("~")
            return {
                'price': float(f[3]) if len(f)>3 and f[3] else 0,
                'pct': float(f[32]) if len(f)>32 and f[32] else 0,
                'high': float(f[33]) if len(f)>33 and f[33] else 0,
                'low': float(f[34]) if len(f)>34 and f[34] else 0,
                'yd_close': float(f[4]) if len(f)>4 and f[4] else 0,
                'volume': float(f[6]) if len(f)>6 and f[6] else 0,
                'amount': float(f[37]) if len(f)>37 and f[37] else 0,
            }
    except: pass
    return None

def score_v2(chg1, df0, j0, vr, pth, da, m0, p0, hs):
    """V2评分 — 38-39黄金区间"""
    s = 0
    if 2<=chg1<=6.5: s+=20
    elif 0.5<=chg1<2: s+=12
    elif -3<=chg1<0 and vr>=1.2 and m0>0 and da>0: s+=16
    elif chg1<0: s+=3
    elif chg1>6.5: s+=5
    else: s+=3
    if pth>=99.5: s+=10
    elif pth>=96: s+=7
    elif pth>=92: s+=4
    else: s+=1
    if vr>=2.0: s+=10
    elif vr>=1.5: s+=8
    elif vr>=1.2: s+=5
    elif vr<0.8: s+=1
    else: s+=3
    if da>0.05: s+=5
    elif da>0: s+=3
    elif df0>0: s+=2
    if m0>50: s+=5
    elif m0>0: s+=3
    elif m0>-30: s+=2
    if j0>85: s-=8
    elif j0<15: s-=3
    if chg1>3 and vr<1.2: s-=8
    iw = da>0.05 and m0>0
    sl = hs or 0
    if df0>2 and sl>8 and p0<-1 and not iw: s-=10
    elif sl>10 and p0<-2 and not iw: s-=7
    if df0>3 and chg1>3 and not iw: s-=5
    return max(s, 0)

# ========== MA5回踩辅助函数 ==========
def get_ma_from_cache(cache, dt, n):
    """从cache计算n日均线，返回(ma值, 距ma%)"""
    if not cache: return None, None
    idx = _cache_idx(cache, dt)
    if idx < n-1: return None, None
    closes = [cache[i]['close'] for i in range(idx-(n-1), idx+1)]
    ma = sum(closes) / n
    return ma, (cache[idx]['close'] - ma) / ma * 100

def get_ma5_trend(cache, dt, days=3):
    """MA5在最近days天的趋势：1=向上, 0=走平, -1=向下"""
    if not cache: return 0
    idx = _cache_idx(cache, dt)
    if idx < 4+days: return 0
    vals = []
    for d in range(days):
        i = idx - d
        if i < 4: break
        closes = [cache[j]['close'] for j in range(i-4, i+1)]
        vals.append(sum(closes)/5)
    if len(vals) < 2: return 0
    pct = (vals[0] - vals[-1]) / vals[-1] * 100
    if pct > 0.5: return 1
    elif pct < -0.5: return -1
    return 0

def score_ma5_pullback(c0, ma5, ma20, ma5_trend, vr, df0, j0):
    """MA5回踩评分 0-100：分数越高=确定性越强"""
    if not ma5 or not ma20: return 0, None
    ma5_dist = (c0 - ma5) / ma5 * 100
    ma20_dist = (c0 - ma20) / ma20 * 100
    s = 0
    # ① 距离MA5 — 精準回踩得分最高
    if -0.5 <= ma5_dist <= 0.5: s += 35
    elif 0.5 < ma5_dist <= 1.5: s += 25
    elif -1.5 <= ma5_dist < -0.5: s += 15
    elif 1.5 < ma5_dist <= 3: s += 8
    elif 3 < ma5_dist <= 5: s += 3
    else: s -= 20
    # ② MA5趋势 — 向上才是真回踩
    if ma5_trend > 0: s += 25
    elif ma5_trend == 0: s += 5
    else: s -= 15
    # ③ 在MA20上方 — 上升趋势确认
    if ma20_dist > 0: s += 20
    elif ma20_dist > -2: s += 5
    else: s -= 20
    # ④ 缩量回踩=惜售，放量=出货
    if vr < 0.8: s += 10
    elif vr < 1.2: s += 15
    elif vr < 1.5: s += 8
    elif vr < 2.0: s += 3
    else: s -= 10
    # ⑤ DIF多头
    if df0 > 0.5: s += 15
    elif df0 > 0: s += 8
    else: s -= 10
    # ⑥ J不过热
    if 20 <= j0 <= 80: s += 10
    elif j0 > 85: s -= 10
    elif j0 < 15: s -= 5
    return max(s, 0), round(ma5_dist, 2)

# ========== 核心函数 ==========
def load_journal():
    if os.path.exists(JOURNAL):
        with open(JOURNAL, encoding='utf-8') as f:
            return json.load(f)
    return {"version":"1.0","last_scan":None,"positions":[],"completed_trades":[]}

def save_journal(j):
    with open(JOURNAL, 'w', encoding='utf-8') as f:
        json.dump(j, f, ensure_ascii=False, indent=2)

def get_bt_latest(code, cur):
    """获取bt_data最新一条"""
    cur.execute("SELECT date,close,p,dif,j_val,k_val,d_val,hsl FROM bt_data WHERE code=? ORDER BY date DESC LIMIT 1", (code,))
    return cur.fetchone()

def get_bt_history(code, cur, dt, n=5):
    """获取最近n条历史"""
    cur.execute("SELECT date,close,p,dif,j_val,k_val,d_val,hsl FROM bt_data WHERE code=? AND date<=? ORDER BY date DESC LIMIT ?", (code, dt, n))
    return cur.fetchall()

def get_dif_trend(code, cur, dt):
    """获取DIF变化趋势"""
    cur.execute("SELECT dif FROM bt_data WHERE code=? AND date<=? ORDER BY date DESC LIMIT 5", (code, dt))
    difs = [r[0] for r in cur.fetchall() if r[0]]
    return difs  # 最新在前

# ========== 买入扫描 ==========
def scan_buy_signals(cur, now_dt):
    """扫描强票池，找买入信号"""
    with open(os.path.join(SCRIPTS_DIR, 'strong_pool.json'), encoding='utf-8') as f:
        pool = json.load(f)
    stocks_dict = pool['stocks']
    
    results = []
    for code, info in stocks_dict.items():
        name = info.get('name', '')
        cache = get_cache(code)
        
        row = get_bt_latest(code, cur)
        if not row: continue
        
        dt, c0, p0, df0, j0, _, _, hs = row
        # 过滤无效数据
        if (abs(j0-50)<=3 and abs(df0)<0.01): continue
        if df0 <= 0.5: continue  # DIF>0.5
        if j0 >= 85: continue    # J<85
        
        # 前1天数据
        cur.execute("SELECT p,dif FROM bt_data WHERE code=? AND date<? ORDER BY date DESC LIMIT 1", (code, dt))
        pr = cur.fetchone()
        if not pr: continue
        chg1 = pr[0]; prev_df = pr[1]
        
        # DIF趋势
        cur.execute("SELECT dif FROM bt_data WHERE code=? AND date<? ORDER BY date DESC LIMIT 2", (code, dt))
        difs = [r[0] for r in cur.fetchall() if r[0]]
        if len(difs) < 2: continue
        df2 = difs[1]
        cur.execute("SELECT dif FROM bt_data WHERE code=? AND date<? ORDER BY date DESC LIMIT 1 OFFSET 4", (code, dt))
        r5 = cur.fetchone()
        df5 = r5[0] if r5 else df2
        dr = df0 - df2; dp = df2 - df5; da = dr - dp
        
        vr = get_vr(cache, dt)
        h10 = get_h10(cache, dt)
        pth = c0/h10*100 if h10>0 else 100
        m0 = get_main(code, dt, cur)
        
        sv = score_v2(chg1, df0, j0, vr, pth, da, m0, p0, hs)

        # ═══ 安全过滤：前高附近量能不足 = 见顶风险 ═══
        # 深深房A教训(pth=99%+chg1=2.3%→次日-8.3%)：
        # 国恩股份教训(pth=96%+vr=1.51→次日-7%) 加缓冲至1.6
        # 前高附近(>95%) + 涨幅温和(<3%) + 量能不足(≤1.6) = 主力出逃风险
        if pth > 95 and vr <= 1.6 and chg1 < 3:
            continue  # 前高附近不创新高=见顶风险极高，宁可错过不买错
        # 前高附近(>98%) + 任何微涨(<0.5%) = 滞涨
        if pth > 98 and chg1 < 0.5:
            continue


        # V2黄金条件: 评分38-39
        if 38 <= sv <= 39:
            results.append({
                'code': code, 'name': name, 'score': sv,
                'diff': df0, 'j': j0, 'vr': vr,
                'chg1': chg1, 'pth': pth, 'da': da,
                'bt_price': c0,
                'win_rate': info.get('win_rate', 0),
                'trades': info.get('trades', 0),
                'wins': info.get('wins', 0),
                'avg_gain': info.get('avg_gain', 0),
            })
    
    # 按胜率排序
    results.sort(key=lambda x: (-x['win_rate'], -x['avg_gain'], -x['score']))
    return results

# ========== MA5回踩扫描 ==========
def scan_ma5_pullback(cur, now_dt):
    """扫描强票池中正在回踩MA5的股票（尾盘专用）"""
    with open(os.path.join(SCRIPTS_DIR, 'strong_pool.json'), encoding='utf-8') as f:
        pool = json.load(f)
    stocks_dict = pool['stocks']
    
    results = []
    for code, info in stocks_dict.items():
        name = info.get('name', '')
        cache = get_cache(code)
        if not cache: continue
        
        row = get_bt_latest(code, cur)
        if not row: continue
        dt, c0, p0, df0, j0, _, _, hs = row
        
        # MA5/MA20
        ma5, ma5_dist = get_ma_from_cache(cache, dt, 5)
        ma20, ma20_dist = get_ma_from_cache(cache, dt, 20)
        if not ma5 or not ma20: continue
        ma5_trend = get_ma5_trend(cache, dt)
        vr = get_vr(cache, dt)
        
        score, _ = score_ma5_pullback(c0, ma5, ma20, ma5_trend, vr, df0, j0)
        
        if score >= 60:  # 高确定性回踩
            results.append({
                'code': code, 'name': name,
                'ma5_score': score,
                'ma5_dist': round(ma5_dist, 2),
                'ma5': round(ma5, 2),
                'ma20': round(ma20, 2),
                'price': round(c0, 2),
                'dif': round(df0, 3),
                'j': round(j0, 1),
                'vr': round(vr, 2),
                'ma5_trend': ma5_trend,
            })
    
    results.sort(key=lambda x: -x['ma5_score'])
    return results

# ========== 卖出检查 ==========
def check_sell_conditions(pos, cur):
    """检查持仓是否满足卖出条件"""
    code = pos['code']
    buy_price = pos['buy_price']
    buy_date = pos['buy_date']
    
    # 计算持有天数
    hold_days = (datetime.now().date() - datetime.strptime(buy_date, '%Y-%m-%d').date()).days
    # 扣除周末（简单算法：按交易日算）
    # 用bt_data中的天数
    cur.execute("SELECT COUNT(DISTINCT date) FROM bt_data WHERE code=? AND date>? AND date<=?",
                (code, buy_date.replace('-',''), datetime.now().strftime('%Y%m%d')))
    trade_days = cur.fetchone()[0] or hold_days
    
    # 获取实时价格
    live = get_live_price(code)
    if not live or live['price'] <= 0:
        return None, None
    
    now_price = live['price']
    profit_pct = round((now_price - buy_price) / buy_price * 100, 2)
    
    # T+1制度：当日买入不能卖出
    today_str = datetime.now().strftime('%Y-%m-%d')
    if buy_date == today_str:
        return None, live  # 监控不卖出
    
    # 获取最新bt_data (收盘后的数据)
    row = get_bt_latest(code, cur)
    latest_j = row[4] if row else None
    latest_dif = row[3] if row else None
    bt_date = row[0] if row else None
    
    # --- 卖出条件判断 ---
    reason = None
    
    # ① 止盈: 赚超8%+J>85
    if profit_pct >= TAKE_PROFIT_PCT:
        if latest_j and latest_j >= 85:
            reason = f"止盈(赚{profit_pct:.1f}%+J{latest_j:.0f}≥85)"
        elif profit_pct >= 10:
            reason = f"止盈(赚{profit_pct:.1f}%≥10%)"
    
    # ② 止损: 亏超-7%
    if not reason and profit_pct <= STOP_LOSS_PCT:
        reason = f"止损(亏{profit_pct:.1f}%≤{STOP_LOSS_PCT}%)"
    
    # ③ 强止损: 亏超-10%
    if not reason and profit_pct <= STOP_LOSS_STRONG:
        reason = f"强止损(亏{profit_pct:.1f}%≤{STOP_LOSS_STRONG}%)"
    
    # ④ DIF连降卖出
    if not reason and latest_dif is not None:
        difs = get_dif_trend(code, cur, bt_date or datetime.now().strftime('%Y%m%d'))
        if len(difs) >= 3 and difs[0] < difs[1] and difs[1] < difs[2]:
            reason = f"DIF连续下降({difs[2]:.3f}→{difs[1]:.3f}→{difs[0]:.3f})"
        elif len(difs) >= 2 and difs[0] < difs[1] and profit_pct < 0:
            reason = f"DIF下降+亏损({difs[1]:.3f}→{difs[0]:.3f})"
    
    # ⑤ 超时: 持有＞10天(交易日)
    if not reason and trade_days > MAX_HOLD_DAYS:
        reason = f"超时(持有{trade_days}天>{MAX_HOLD_DAYS}天)"
    
    if reason:
        return {
            'sell_date': datetime.now().strftime('%Y-%m-%d'),
            'sell_time': datetime.now().strftime('%H:%M'),
            'sell_price': now_price,
            'sell_reason': reason,
            'hold_days': trade_days,
            'return_pct': profit_pct,
            'daily_return': round(profit_pct / trade_days, 2) if trade_days > 0 else profit_pct,
            'sell_j': latest_j,
            'sell_dif': latest_dif,
        }, live
    
    return None, live

# ========== 主流程 ==========
def main():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    hour_min = now.strftime('%H:%M')
    is_morning = now.hour < 12
    
    print(f"{'🌅' if is_morning else '🌆'} 波段交易扫描 {today} {hour_min}")
    print("=" * 80)
    
    # 加载日记
    journal = load_journal()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    report_buy = []
    report_sell = []
    report_skip = []
    
    # ====== 第一步：检查持仓卖出 ======
    positions = journal.get('positions', [])
    if positions:
        print(f"\n📋 当前持仓: {len(positions)}只")
        remaining_positions = []
        for pos in positions:
            code = pos['code']
            result, live = check_sell_conditions(pos, cur)
            if result:
                # 卖出！
                pos.update(result)
                pos['status'] = '已平仓'
                journal['completed_trades'].append(dict(pos))
                report_sell.append(pos)
                print(f"  🔴 卖出: {pos['name']}({code}) | {pos['sell_reason']} | 盈亏{pos['return_pct']:+.2f}% | 持有{pos['hold_days']}天 | 日化{pos['daily_return']:+.2f}%")
            else:
                # 继续持仓
                pct_s = f"{((live['price']-pos['buy_price'])/pos['buy_price']*100):+.2f}%" if live else "--"
                print(f"  🟢 持有中: {pos['name']}({code}) | 买入{pos['buy_price']} | 现价{live['price'] if live else '--'} | {pct_s}")
                remaining_positions.append(pos)
        journal['positions'] = remaining_positions
    else:
        print("\n📋 当前持仓: 空仓")
    
    # ====== 第二步：扫描买入信号 ======
    print(f"\n🔍 {'早盘' if is_morning else '尾盘'}买入扫描...")
    
    # 已持仓的code列表（避免重复买入）
    held_codes = {p['code'] for p in journal['positions']}
    
    signals = scan_buy_signals(cur, today)
    print(f"   黄金信号: {len(signals)}只")
    
    for s in signals:
        code = s['code']
        if code in held_codes:
            report_skip.append(f"{s['name']}({code}) 已在持仓中(等待闭环)")
            continue
        
        # 获取实时价格作为买入参考
        live = get_live_price(code)
        buy_price = live['price'] if live and live['price'] > 0 else s['bt_price']
        
        new_pos = {
            'code': code,
            'name': s['name'],
            'buy_date': today,
            'buy_time': hour_min,
            'buy_price': buy_price,
            'bt_price': s['bt_price'],
            'score': s['score'],
            'dif': s['diff'],
            'j': s['j'],
            'vr': s['vr'],
            'chg1': s['chg1'],
            'pth': s['pth'],
            'win_rate': s['win_rate'],
            'trades': s['trades'],
            'wins': s['wins'],
            'avg_gain': s['avg_gain'],
            'status': '持仓中',
        }
        journal['positions'].append(new_pos)
        report_buy.append(new_pos)
        print(f"  🟢 买入: {s['name']}({code}) 评分{s['score']}⭐ | DIF{s['diff']:+.3f} J{s['j']:.0f} | 买入价{buy_price:.2f} | 历史{s['wins']}/{s['trades']}={s['win_rate']:.0f}% 均{s['avg_gain']:+.2f}%")
    
    if not signals:
        print("   无符合条件的买入信号(宁缺毋滥)")
    
    # ====== MA5回踩扫描（尾盘专用） ======
    if not is_morning:
        print(f"\n🔍 MA5回踩扫描...")
        ma5_sigs = scan_ma5_pullback(cur, today)
        if ma5_sigs:
            print(f"   ⭐ 回踩确认信号: {len(ma5_sigs)}只\n")
            # 分级显示
            levels = {'🟢 高确定性(≥80)': [], '🟡 中确定性(70-79)': [], '🔵 低确定性(60-69)': []}
            for s in ma5_sigs:
                if s['ma5_score'] >= 80: levels['🟢 高确定性(≥80)'].append(s)
                elif s['ma5_score'] >= 70: levels['🟡 中确定性(70-79)'].append(s)
                else: levels['🔵 低确定性(60-69)'].append(s)
            for label, items in levels.items():
                if not items: continue
                print(f"  {label}:")
                for s in items:
                    trend = '↑' if s['ma5_trend'] > 0 else ('→' if s['ma5_trend'] == 0 else '↓')
                    dist = f"{s['ma5_dist']:+.2f}%"
                    print(f"    {s['name']}({s['code']}) 评分{s['ma5_score']} | 距MA5:{dist} MA5:{s['ma5']} MA20:{s['ma20']} | 价{s['price']} DIF{s['dif']:+.3f} J{s['j']:.0f} VR{s['vr']:.2f} {trend}")
        else:
            print("   未发现回踩MA5信号")
    
    # ====== 保存 ======
    journal['last_scan'] = f"{today} {hour_min}"
    save_journal(journal)
    conn.close()
    
    # ====== 汇总 ======
    print("\n" + "=" * 80)
    print(f"📊 波段交易汇总")
    print(f"   本次买入: {len(report_buy)}只")
    print(f"   本次卖出: {len(report_sell)}只")
    print(f"   当前持仓: {len(journal['positions'])}只")
    print(f"   已平仓: {len(journal['completed_trades'])}笔")
    
    # 计算已平仓统计
    if journal['completed_trades']:
        wins = [t for t in journal['completed_trades'] if t.get('return_pct',0) > 0]
        total_pct = sum(t.get('return_pct',0) for t in journal['completed_trades'])
        avg_pct = total_pct / len(journal['completed_trades']) if journal['completed_trades'] else 0
        avg_days = sum(t.get('hold_days',1) for t in journal['completed_trades']) / len(journal['completed_trades'])
        print(f"   胜率: {len(wins)}/{len(journal['completed_trades'])}={len(wins)/len(journal['completed_trades'])*100:.0f}%")
        print(f"   总收益: {total_pct:+.2f}% | 平均每笔{avg_pct:+.2f}% | 均持{avg_days:.1f}天")
    
    # 选择推送内容（简短版）
    print("\n" + "=" * 80)
    if report_buy or report_sell:
        lines = [f"{'🌅' if is_morning else '🌆'} 波段交易扫描 {today} {hour_min}"]
        if report_buy:
            lines.append("")
            lines.append(f"🟢 买入 {len(report_buy)}只:")
            for p in report_buy:
                lines.append(f"  {p['name']}({p['code']}) 评分{p['score']} DIF{p['dif']:+.3f} J{p['j']:.0f} 买入价{p['buy_price']:.2f}")
        if report_sell:
            lines.append("")
            lines.append(f"🔴 卖出 {len(report_sell)}只:")
            for p in report_sell:
                lines.append(f"  {p['name']}({p['code']}) {p['sell_reason']} 盈亏{p['return_pct']:+.2f}% 持有{p['hold_days']}天 日化{p['daily_return']:+.2f}%")
        if report_skip:
            lines.append("")
            lines.append(f"⏭️ 跳过(已在持仓):")
            for s in report_skip:
                lines.append(f"  {s}")
        lines.append("")
        lines.append(f"📊 持仓{len(journal['positions'])}只 | 已平仓{len(journal['completed_trades'])}笔")
        print("\n".join(lines))
    else:
        print("本次扫描无操作")
    
    # ====== 发送邮件 ======
    _send_email_report(is_morning, today, hour_min, report_buy, report_sell, report_skip, journal)

def _send_email_report(is_morning, today, hour_min, report_buy, report_sell, report_skip, journal):
    """生成并发送HTML邮件（零边距手机优化）"""
    if not HAS_EMAIL:
        print("⚠️ send_email模块不可用，跳过邮件发送")
        return
    
    prefix = "🌅 早盘" if is_morning else "🌆 尾盘"
    subject = f"波段交易扫描 {today} {hour_min}"
    
    # 公共CSS
    css = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;font-size:13px;color:#333}
h1{font-size:16px;padding:8px 4px}
h2{font-size:14px;padding:6px 4px;margin:8px 0 4px}
.sub{color:#666;font-size:11px;padding:4px 4px 8px}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{min-width:420px;width:100%;border-collapse:collapse;font-size:11px}
th{background:#1a1a2e;color:#fff;padding:5px 3px;text-align:center;white-space:nowrap}
td{padding:5px 3px;border-bottom:1px solid #eee;white-space:nowrap;text-align:center}
td.l{text-align:left}
td.r{text-align:right}
.f{text-align:center;color:#999;font-size:10px;padding:10px 4px;border-top:1px solid #eee}
.st{background:#eef2ff;padding:8px;border-radius:4px;font-size:11px;margin:8px 0}
</style>"""
    
    sections = []
    
    for p in journal['positions']:
        live_pct = ""  # 持仓的实时涨跌不在这里显示
    
    # 买入表
    buy_section = ""
    if report_buy:
        fr = ""
        for p in report_buy:
            bg = "#fff5f5"
            gold = "⭐" if 38 <= p['score'] <= 39 else ""
            fr += f"""<tr style="background:{bg}">
<td class="l"><b>{p['name']}</b> 🔥<span style="color:#999;font-size:10px"> {p['code']}</span></td>
<td style="font-weight:bold;color:#e94560">{p['score']}{gold}</td>
<td>{p['buy_price']:.2f}</td>
<td style="color:#dc2626">{p['dif']:+.3f}</td>
<td>{p['j']:.0f}</td>
<td>{p['wins']}/{p['trades']}={p['win_rate']:.0f}%</td>
<td>{p['avg_gain']:+.2f}%</td>
</tr>"""
        buy_section = f"""<h2 style="color:#16a34a;border-bottom:2px solid #16a34a">🟢 新买入 {len(report_buy)}只</h2>
<div class="wrap"><table><thead><tr>
<th class="l">股票</th><th>评分</th><th>买入价</th><th>DIF</th><th>J</th><th>历史波段</th><th>均赚</th>
</tr></thead><tbody>{fr}</tbody></table></div>"""
    
    # 卖出表
    sell_section = ""
    if report_sell:
        fr = ""
        for p in report_sell:
            profit = p['return_pct']
            bg = "#fff5f5" if profit > 0 else "#f0fdf4"
            color = "#dc2626" if profit > 0 else "#16a34a"
            fr += f"""<tr style="background:{bg}">
<td class="l"><b>✅ {p['name']}</b><span style="color:#999;font-size:10px"> {p['code']}</span></td>
<td class="l" style="font-size:10px;color:#666">{p['sell_reason']}</td>
<td style="font-weight:bold;color:{color}">{profit:+.2f}%</td>
<td>{p['hold_days']}天</td>
<td style="color:{color}">{p['daily_return']:+.2f}%</td>
<td style="color:{'#dc2626' if p.get('sell_j',0) and p['sell_j']>0 else '#666'}">{p.get('sell_j',0):.0f}</td>
</tr>"""
        sell_section = f"""<h2 style="color:#dc2626;border-bottom:2px solid #dc2626">🔴 卖出平仓 {len(report_sell)}笔</h2>
<div class="wrap"><table><thead><tr>
<th class="l">股票</th><th class="l">原因</th><th>盈亏</th><th>持有</th><th>日化</th><th>J</th>
</tr></thead><tbody>{fr}</tbody></table></div>"""
    
    # 持仓表
    # 持仓表
    pos_section = ""
    if journal['positions']:
        fr = ""
        for p in journal['positions']:
            init_flag = p.get('init', False)
            init_tag = " 🆕" if init_flag else ""
            today_bought = (not init_flag) and p.get('buy_date','') == today
            today_tag = " 🔥今日" if today_bought else ""
            remark = p.get('remark', '') + init_tag + today_tag
            dif_p = p.get('dif', 0)
            dif_color = "#dc2626" if dif_p > 0 else "#16a34a"
            wr = f"{p.get('wins',0)}/{p.get('trades',0)}={p.get('win_rate',0):.0f}%"
            is_100 = "✅" if p.get('win_rate',0) >= 100 else ""
            bg = "#faf5ff" if p.get('win_rate',0) >= 100 else "#fff"
            # 持仓中 → 卖出日/卖出价 为空
            sell_date = p.get('sell_date', '')
            sell_price = p.get('sell_price', '')
            sd = f"<span style='color:#999'>--</span>" if not sell_date else sell_date
            sp = f"<span style='color:#999'>--</span>" if not sell_price else f"{sell_price:.2f}"
            name_display = f"🟢 {p['name']}{' 🔥' if today_bought else ''}"
            # 计算收益率
            buy_price = p.get('buy_price', 0)
            # 计算持有天数（交易日估算）
            try:
                bd = datetime.strptime(p['buy_date'], '%Y-%m-%d')
                hold_d = (datetime.now() - bd).days
                # 粗略扣除周末（约2/7）
                trade_days = max(1, round(hold_d * 5 / 7))
            except:
                trade_days = 1
            
            if sell_price and sell_price > 0:
                # 已平仓
                ret = (sell_price - buy_price) / buy_price * 100
                ret_str = f"{ret:+.2f}%"
                ret_color = "#dc2626" if ret > 0 else "#16a34a"
                daily_ret = ret / max(p.get('hold_days', trade_days), 1)
                daily_str = f"{daily_ret:+.2f}%"
            else:
                # 持仓中 → 查实时价
                live = get_live_price(p['code'])
                if live and live['price'] > 0:
                    ret = (live['price'] - buy_price) / buy_price * 100
                    ret_str = f"{ret:+.2f}%"
                    ret_color = "#dc2626" if ret > 0 else "#16a34a"
                    daily_ret = ret / trade_days
                    daily_str = f"{daily_ret:+.2f}%"
                else:
                    ret_str = "--"
                    ret_color = "#999"
                    daily_str = "--"
            fr += f"""<tr style="background:{bg}">
<td class="l"><b>{name_display}</b><span style="color:#999;font-size:10px"> {p['code']}</span></td>
<td style="font-size:10px">{p['buy_date']}</td>
<td>{p['buy_price']:.2f}</td>
<td style="font-size:10px">{sd}</td>
<td style="font-size:10px">{sp}</td>
<td style="font-weight:bold;color:{ret_color};font-size:11px">{ret_str}</td>
<td style="font-size:10px;color:{ret_color}">{daily_str}</td>
<td style="color:{dif_color}">{dif_p:+.3f}</td>
<td>{p.get('j',0):.0f}</td>
<td style="font-size:10px">{wr} {is_100}</td>
<td class="l" style="font-size:10px;color:#666">{remark}</td>
</tr>"""
        pos_section = f"""<h2 style="color:#2563eb;border-bottom:2px solid #2563eb">📋 当前持仓 {len(journal['positions'])}只</h2>
<div class="wrap"><table><thead><tr>
<th class="l">股票</th><th>买入日</th><th>买入价</th><th>卖出日</th><th>卖出价</th><th>收益率</th><th>日化率</th><th>DIF</th><th>J</th><th>历史波段</th><th class="l">说明</th>
</tr></thead><tbody>{fr}</tbody></table></div>"""
    
    # 胜率统计
    stat_section = ""
    if journal['completed_trades']:
        wins = [t for t in journal['completed_trades'] if t.get('return_pct',0) > 0]
        total_pct = sum(t.get('return_pct',0) for t in journal['completed_trades'])
        avg_pct = total_pct / len(journal['completed_trades']) if journal['completed_trades'] else 0
        avg_days = sum(t.get('hold_days',1) for t in journal['completed_trades']) / len(journal['completed_trades'])
        stat_color = "#dc2626" if total_pct > 0 else "#16a34a"
        stat_section = f"""<div class="st">
📊 累计 <b>{len(wins)}/{len(journal['completed_trades'])}={len(wins)/len(journal['completed_trades'])*100:.0f}%</b>
｜总收益 <b style="color:{stat_color}">{total_pct:+.2f}%</b>
｜均每笔 {avg_pct:+.2f}% ｜均持 {avg_days:.1f}天</div>"""
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{css}</head><body>
<h1>{prefix} 波段交易扫描</h1>
<p class="sub">{today} {hour_min}</p>
{buy_section}
{sell_section}
{pos_section}
{stat_section}
<div class="f">📌 波段交易系统 · 基于强票池V2(评分38-39黄金区间)自动扫描<br>
T+1制度：当日买入次日才能卖出｜止盈≥8%+J≥85｜止损≤-7%｜DIF连降卖出｜超时10天强制平仓<br>
<span style="color:#e94560;font-weight:bold">⚠️ 当前为测试阶段，仅模拟跟踪，不构成投资建议</span></div></body></html>"""
    
    try:
        ok = dispatch_email(subject=subject, body=html, html=True, report_type='波段交易', groups=['A','C'])
        ok_msg = ' | '.join(f'{g}:{m}' for g,m in ok.items())
        print(f"📧 邮件: {ok_msg}")
    except Exception as e:
        print(f"⚠️ 邮件发送异常: {e}")

if __name__ == '__main__':
    main()
