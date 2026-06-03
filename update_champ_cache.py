#!/usr/bin/env python3
"""更新冠军缓存：增加每日收盘涨幅 + 大盘每日涨跌幅"""
import json, os, requests
from datetime import datetime, timedelta

BASE = os.path.dirname(__file__)
CHAMP_CACHE = os.path.join(BASE, '..', 'hermes-agent', 'champion_cache_CG-01_mar-may.txt')
TOP5_CACHE = os.path.join(BASE, '..', 'hermes-agent', 'top5_cache_CG-01_mar-may.txt')
CACHE_DIR = os.path.join(BASE, '..', 'hermes-agent', 'cache')

def get_kl(code, market, test_date):
    """从缓存读取K线，返回该日之后的数据"""
    kf = os.path.join(CACHE_DIR, f"{market}{code}.json")
    if not os.path.exists(kf):
        return None, []
    recs = json.load(open(kf))
    bi = None
    for i, r in enumerate(recs):
        if r["date"] == test_date:
            bi = i
            break
    if bi is None:
        return None, []
    return recs[bi], recs[bi+1:bi+6]

def fetch_index_daily():
    """获取上证指数历史日K线"""
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,320,qfq"
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        d = r.json()
        sd = d.get('data', {}).get('sh000001', {})
        k = sd.get('qfqday', [])
        if not k:
            for key in sd:
                if isinstance(sd[key], list) and sd[key] and isinstance(sd[key][0], list):
                    k = sd[key]
                    break
        result = {}
        prev_close = None
        for x in k:
            dt = x[0]
            close = float(x[2])
            if prev_close is not None:
                chg_pct = round((close / prev_close - 1) * 100, 2)
            else:
                chg_pct = 0.0
            result[dt] = {"close": close, "pct": chg_pct}
            prev_close = close
        return result
    except Exception as e:
        print(f"  获取大盘数据失败: {e}")
        return {}

# ═══ 1. 更新冠军缓存 ═══
print("📡 读取冠军缓存...")
with open(CHAMP_CACHE) as f:
    champ_all = json.load(f)

print(f"  ✅ {len(champ_all)}天冠军数据")

print("📡 获取大盘日K线...")
index_data = fetch_index_daily()
print(f"  ✅ {len(index_data)}天大盘数据")

updates = 0
for dt, c in sorted(champ_all.items()):
    if c is None:
        continue
    
    # 更新daily: 增加收盘涨幅
    buy_price = c.get("kl_close", 0)
    code = c["code"]
    market = c["market"]
    
    _, after = get_kl(code, market, dt)
    if after and buy_price > 0:
        new_daily = []
        for r in after:
            dh = round((r["high"] / buy_price - 1) * 100, 1)
            dc = round((r["close"] / buy_price - 1) * 100, 1)
            chg = r["close"] - (buy_price if not new_daily else after[after.index(r)-1]["close"] if after.index(r) > 0 else buy_price)
            arr = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
            new_daily.append({
                "high": dh,
                "close": dc,
                "arrow": arr,
                "date": r["date"]
            })
        c["daily"] = new_daily
        updates += 1
    
    # 增加大盘当日涨跌
    if dt in index_data:
        c["index_pct"] = index_data[dt]["pct"]
    else:
        c["index_pct"] = None
    
    champ_all[dt] = c

print(f"  ✅ 更新了 {updates} 天的daily数据")

# ═══ 2. 保存 ═══
with open(CHAMP_CACHE, 'w') as f:
    json.dump(champ_all, f, ensure_ascii=False, indent=2, default=str)
print(f"  💾 冠军缓存已保存")

# 验证一下
print(f"\n📋 验证5/22数据:")
c = champ_all.get("2026-05-22")
if c:
    print(f"  {c['name']} 买入价={c['kl_close']}")
    for di, dd in enumerate(c.get("daily", [])):
        print(f"    D+{di+1} {dd['date']}: 最高{dd['high']:+.1f}% 收盘{dd['close']:+.1f}%")
    print(f"  大盘涨跌: {c.get('index_pct')}%")

print("\n✅ 更新完成!")
