#!/usr/bin/env python3
"""CG-05 最近30天回测 → 冠军表 + 近5日Top5"""
import json, os, sys
from datetime import datetime

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
OUT_DIR = r"C:\Users\12546\AppData\Local\hermes\scripts"

# ═══ 技术指标 ═══
def ma(d, pd):
    res = []
    for i in range(len(d)):
        if i < pd-1: res.append(None)
        else: res.append(sum(d[i-pd+1:i+1])/pd)
    return res

def macd_full(ps):
    n = len(ps)
    if n < 26: return None, None, None
    e12 = [ps[0]]; e26 = [ps[0]]
    dif = [None]*n; dea = [None]*n; macd = [None]*n
    for i in range(1, n):
        e12.append(e12[-1]*11/13+ps[i]*2/13)
        e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i] = e12[i] - e26[i]
    dea[0] = dif[0] if dif[0] else 0
    for i in range(1, n):
        dea[i] = dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            macd[i] = dif[i] - dea[i]
    return dif, dea, macd

def kdj_calc(highs, lows, closes, n=9):
    length = len(closes)
    if length < n: return None, None, None
    k = [50.0]*length; d = [50.0]*length; j = [50.0]*length
    for i in range(n-1, length):
        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
        if i == n-1: k[i] = 50.0
        else: k[i] = 2/3*k[i-1] + 1/3*rsv
        d[i] = 2/3*d[i-1] + 1/3*k[i]
        j[i] = 3*k[i] - 2*d[i]
    return k, d, j

# ═══ CG-05 参数 ═══
CFG = {"pct_lower": 4, "pct_upper": 5, "ma5_slope_min": 10, "close_pos_min": 50, "vr_max": 2.5, "j_ratio_min": 15}

# ═══ 加载数据 ═══
print("📡 加载K线数据...")
all_data = {}
for fn in os.listdir(CACHE_DIR):
    if not fn.endswith('.json'): continue
    if not (fn.startswith('sh6') or fn.startswith('sz0')): continue
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, 'rb') as fh:
            recs = json.loads(fh.read().decode('utf-8'))
        if not isinstance(recs, list) or len(recs) < 80: continue
        market = "sh" if fn.startswith("sh") else "sz"
        code = fn.replace('.json','').replace('sh','').replace('sz','')
        
        close_p = [r["close"] for r in recs]
        high_p = [r["high"] for r in recs]
        low_p = [r["low"] for r in recs]
        vol = [r["volume"] for r in recs]
        open_p = [r.get("open", r["close"]) for r in recs]
        dates = [r["date"] for r in recs]
        
        pct_list = [0.0]
        for i in range(1, len(close_p)): pct_list.append((close_p[i]/close_p[i-1]-1)*100)
        ma5 = ma(close_p, 5); ma10 = ma(close_p, 10); ma20 = ma(close_p, 20); ma60 = ma(close_p, 60)
        v5 = ma(vol, 5)
        dif, dea, macd = macd_full(close_p)
        k, d, j = kdj_calc(high_p, low_p, close_p)
        date_idx = {dt: i for i, dt in enumerate(dates)}
        
        all_data[code] = {"p": close_p, "h": high_p, "l": low_p, "v": vol, "o": open_p,
            "pct": pct_list, "dates": dates, "date_idx": date_idx,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "v5": v5, "dif": dif, "dea": dea, "macd": macd,
            "k": k, "d": d, "j": j, "recs": recs, "market": market}
    except: pass
print(f"  ✅ {len(all_data)} 只股票")

# 最近30天
all_dates = sorted(set(dt for sd in all_data.values() for dt in sd["dates"] if dt.startswith("2026-")))
dates_30 = all_dates[-30:]
print(f"  📅 {dates_30[0]} ~ {dates_30[-1]} 共{len(dates_30)}天")

# ═══ 预计算未来表现 ═══
print("📡 预计算未来5日表现...")
future_lookup = {}
for code, sd in all_data.items():
    recs = sd["recs"]
    for i in range(len(recs) - 5):
        dt = recs[i]["date"]; buy = recs[i]["close"]
        if buy <= 0: continue
        after = recs[i+1:i+6]
        if not after: continue
        m5 = round((max(x["high"] for x in after) / buy - 1) * 100, 1)
        closes = [x["close"] for x in after]
        day_data = []
        prev = buy
        for x in after:
            dh = round((x["high"]/buy-1)*100, 1)
            dc = round((x["close"]/buy-1)*100, 1)
            arr = "↑" if x["close"] > prev else ("↓" if x["close"] < prev else "→")
            day_data.append({"high": dh, "close": dc, "arrow": arr, "date": x["date"]})
            prev = x["close"]
        ret5 = round((closes[-1]/buy-1)*100, 1) if closes else None
        future_lookup[(code, dt)] = {"max5": m5, "daily": day_data, "ret5": ret5}
print(f"  ✅ {len(future_lookup)} 条记录")

# ═══ 获取大盘数据 ═══
print("📡 获取大盘指数...")
import requests
index_data = {}
try:
    r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,320,qfq",
                     headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    d = r.json()
    sd = d.get('data',{}).get('sh000001',{})
    k = sd.get('qfqday',[])
    if not k:
        for key in sd:
            if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
    prev_close = None
    for x in k:
        dt = x[0]; close = float(x[2])
        if not dt.startswith("2026-"): 
            prev_close = close
            continue
        if prev_close:
            chg = round((close/prev_close-1)*100, 2)
        else: chg = 0.0
        index_data[dt] = chg
        prev_close = close
except: pass
print(f"  ✅ {len(index_data)} 天")

# ═══ 跑回测 ═══
print(f"\n🚀 跑CG-05近30天回测...")
champ_data = {}
top5_cache = {}
cfg = CFG

for td in dates_30:
    results = []
    for code, sd in all_data.items():
        di = sd["date_idx"].get(td)
        if di is None or di < 80: continue
        p=sd["p"]; h=sd["h"]; l=sd["l"]; v_=sd["v"]; o=sd["o"]
        pct=sd["pct"]; ma5=sd["ma5"]; ma10=sd["ma10"]; ma20=sd["ma20"]; ma60=sd["ma60"]
        v5=sd["v5"]; dif=sd["dif"]; dea=sd["dea"]; macd=sd["macd"]
        k_=sd["k"]; d_=sd["d"]; j_=sd["j"]
        
        cur = p[di]
        if cur > 80: continue
        if cur <= o[di] or (cur-o[di])/o[di]*100 < 1: continue
        if v5[di] and v_[di]/v5[di] > cfg["vr_max"]: continue
        if (h[di]-l[di]) > 0 and (cur-l[di])/(h[di]-l[di])*100 < cfg["close_pos_min"]: continue
        if not (ma60[di] and ma60[di] > 0): continue
        if not (dif[di] and dea[di] and dif[di] > dea[di]): continue
        if not (macd[di] and macd[di] > 0): continue
        if dif[di] - dea[di] < 0.1: continue
        if macd[di-1] is not None and macd[di] <= macd[di-1]: continue
        if macd[di-1] is not None and macd[di-2] is not None:
            if macd[di]-macd[di-1] < macd[di-1]-macd[di-2]: continue
        if dif[di-3] is not None and dif[di] <= dif[di-3]: continue
        
        j_slope = j_[di]-j_[di-1] if (j_[di-1] is not None and j_[di] is not None) else 0
        dp = d_[di-1] if d_[di-1] is not None and d_[di-1] != 0 else 1
        jr = j_slope/dp*100
        kdj_g = (j_[di]>k_[di]>d_[di]) or (j_[di]>k_[di] and k_[di]<=d_[di])
        if j_[di-1] is not None and k_[di-1] is not None and j_[di-1]<=k_[di-1] and j_[di]>k_[di]: kdj_g = True
        if not (jr > cfg["j_ratio_min"] or kdj_g): continue
        if k_[di] > 80 and j_[di] > 90: continue
        if k_[di] < 20: continue
        if not (ma5[di] and ma5[di-3] and ma5[di] > ma5[di-3]): continue
        if not (ma20[di] and ma20[di-5] and ma20[di] > ma20[di-5]): continue
        if not (ma5[di] and ma10[di] and ma20[di] and ma5[di] > ma10[di] > ma20[di]): continue
        if not (ma5[di] and cur > ma5[di]): continue
        if ma5[di] and ma5[di-5] and ma5[di-5] > 0:
            slope = (ma5[di]-ma5[di-5])/ma5[di-5]*100
            if slope <= cfg["ma5_slope_min"]: continue
        else: continue
        gap = ma10[di]-ma20[di] if (ma10[di] and ma20[di]) else 0
        gap_b = ma10[di-4]-ma20[di-4] if (ma10[di-4] and ma20[di-4]) else 0
        if gap <= gap_b*0.8: continue
        if not (cfg["pct_lower"] < pct[di] < cfg["pct_upper"]): continue
        
        # 评分
        score = 0
        macd_r = dif[di]/cur*100 if cur > 0 else 0
        if macd_r > 5: score += 25
        elif macd_r > 2: score += 20
        elif macd_r > 1: score += 12
        elif macd_r > 0: score += 5
        vr_cur = v_[di]/v5[di] if v5[di] else 0
        if pct[di] > 7: score += 30
        elif pct[di] > 5: score += 25
        elif pct[di] > 3: score += 15
        elif pct[di] > 0: score += 8
        if vr_cur > 2: score += 15
        elif vr_cur > 1.2: score += 10
        elif vr_cur > 0.7: score += 5
        if ma5[di] and cur > ma5[di]: score += 12
        if len(p) >= 120 and di >= 120:
            bh = max(h[di-60:di-1]); bl = min(l[di-60:di-1])
            rl = min(p[di-120:di]); rh = max(p[di-120:di])
            pos = ((bh+bl)/2 - rl)/(rh-rl)*100 if (rh-rl) > 0 else 50
        else: pos = 50
        if pos < 30: score += 15
        elif pos < 50: score += 8
        elif pos > 60: score -= 5
        sum5 = sum(pct[di-4:di+1]) if di >= 5 else 0
        if sum5 > 5: score += 8
        if 5 < cur < 35: score += 5
        gc = sum(1 for i in range(max(0,di-5),di-1) if pct[i] > 0)
        if gc >= 3: score += 5
        if pct[di] > 4.5: score -= 8
        if di >= 1 and pct[di-1] > 3: score -= 5
        if di >= 2 and pct[di-2] > 3: score -= 5
        sh = h[di] - max(o[di], cur); tr = h[di] - l[di]
        if tr > 0 and sh > 0:
            sr = sh/tr*100
            if sr > 50: score -= 5
            elif sr > 30: score -= 3
            elif sr > 15: score -= 1
        
        fp = future_lookup.get((code, td))
        results.append({"code":code, "name":"?", "score":score, "price":cur, "pct_d":pct[di], "pos":pos,
                        "vr":vr_cur, "max5":fp["max5"] if fp else None, "ret5":fp["ret5"] if fp else None,
                        "daily":fp["daily"] if fp else []})
    
    if not results:
        print(f"  {td}: 无选股")
        champ_data[td] = None
        continue
    
    results.sort(key=lambda x: -x["score"])
    champion = results[0]
    top5 = results[:5]
    
    # 存冠军
    champ = {"name": champion["name"], "code": champion["code"], "qscore": champion["score"],
             "kl_close": champion["price"], "pct_d": champion["pct_d"],
             "max5": champion["max5"], "daily": champion["daily"],
             "index_pct": index_data.get(td)}
    champ_data[td] = champ
    
    # 存Top5
    t5_list = []
    for i, r in enumerate(top5):
        t5_list.append({"rank":i+1, "name":r["name"], "code":r["code"], "score":r["score"],
                        "price":round(r["price"],2), "pct":r["pct_d"], "max5":r["max5"],
                        "daily":r["daily"] if i==0 else []})
    top5_cache[td] = t5_list
    
    # 获取名称
    try:
        import subprocess
        text = subprocess.run(['curl','-s','-m','5',f'https://qt.gtimg.cn/q={champion["code"]}'], 
                            capture_output=True, timeout=8).stdout.decode('gbk',errors='replace')
        pts = text.split("~")
        if len(pts) > 1:
            champ["name"] = pts[1]
    except: pass
    
    hit = "✅10%+" if isinstance(champ["max5"],(int,float)) and champ["max5"]>=10 else ""
    print(f"  {td}: #1 {champ['name']:<8} 评分{champ['qscore']:>3d}  当天{champ['pct_d']:+.2f}%  max5={champ['max5']} {hit}")

# ═══ 生成报表 ═══
print(f"\n{'='*90}")
print(f"  🐉 CG-05 近30日回测结果")
print(f"{'='*90}")

# 全期统计
valid_days = {k:v for k,v in champ_data.items() if v is not None}
champ_list = [(k,v) for k,v in sorted(valid_days.items(), reverse=True)]
avg_max = sum(c["max5"] for _,c in champ_list if isinstance(c["max5"],(int,float)))
cnt_max = sum(1 for _,c in champ_list if isinstance(c["max5"],(int,float)))
hit10 = sum(1 for _,c in champ_list if isinstance(c["max5"],(int,float)) and c["max5"]>=10)
hit5 = sum(1 for _,c in champ_list if isinstance(c["max5"],(int,float)) and c["max5"]>=5)
avg_str = f"{avg_max/cnt_max:.1f}%" if cnt_max else "—"
print(f"\n  📊 出票{len(champ_list)}天 | 达标10%+: {hit10}天({hit10/cnt_max*100:.0f}% if cnt_max else 0) | 达标5%+: {hit5}天({hit5/cnt_max*100:.0f}% if cnt_max else 0) | 均最高+{avg_str}")
print(f"{'='*90}")

# 冠军表
print(f"\n{'─'*90}")
print(f"  {'日期':<12} {'最优选':<12} {'评分':>4} {'买入价':>8} {'当天%':>7} {'D+1高':>6} {'D+1收':>6} {'D+2高':>6} {'D+2收':>6} {'D+3高':>6} {'D+3收':>6} {'D+4高':>6} {'D+4收':>6} {'D+5高':>6} {'D+5收':>6} {'5日最高':>8}")
print(f"{'─'*90}")
for dt, c in champ_list:
    dly = c.get("daily", [])
    cells = [f"{dt:<12}", f"{c['name']:<12}", f"{c['qscore']:>4d}", f"{c.get('kl_close',0):>8.2f}", f"{c.get('pct_d',0):>+6.2f}%"]
    best_5d = None
    for di in range(5):
        if di < len(dly):
            dh = dly[di].get("high","—")
            dc = dly[di].get("close","—")
            if isinstance(dh,(int,float)) and (best_5d is None or dh > best_5d): best_5d = dh
            cells.append(f"{dh:>+6.1f}%" if isinstance(dh,(int,float)) else f"{'—':>6}")
            cells.append(f"{dc:>+6.1f}%" if isinstance(dc,(int,float)) else f"{'—':>6}")
        else:
            cells.append(f"{'—':>6}"); cells.append(f"{'—':>6}")
    b5 = best_5d if best_5d is not None else c.get("max5","—")
    cells.append(f"{b5:>+8.1f}%" if isinstance(b5,(int,float)) else f"{'—':>8}")
    print(" ".join(cells))

# 近5日Top5
print(f"\n\n{'='*90}")
print(f"  📊 近5日 Top5 明细")
print(f"{'='*90}")
last5 = sorted(top5_cache.keys(), reverse=True)[:5]
for dt in last5:
    t5 = top5_cache[dt]
    champ = champ_data.get(dt, {})
    if not t5: continue
    print(f"\n  📅 {dt} — Top5")
    print(f"  {'#':>2} {'名称':<10} {'评分':>4} {'买入价':>8} {'当天%':>7} {'5日最高':>8}")
    print(f"  {'─'*45}")
    for i, r in enumerate(t5):
        m5 = f"{r['max5']:+.1f}%" if r['max5'] is not None else "—"
        print(f"  {i+1:>2}. {r['name']:<10} {r['score']:>4} {r['price']:>8.2f} {r['pct']:>+6.2f}% {m5:>8}")
    
    if champ and champ.get("daily"):
        print(f"\n      🏆 {champ['name']} D+1~D+5分解:")
        for di, dd in enumerate(champ["daily"]):
            print(f"      D+{di+1} {dd['date']}: 最高{dd['high']:+.1f}%  收盘{dd['close']:+.1f}%")

# ═══ 保存缓存 ═══
cache = {"champ_data": {k:v for k,v in champ_data.items() if v is not None}, "top5_cache": top5_cache}
with open(os.path.join(OUT_DIR, "cg05_30day_cache.json"), "w") as f:
    json.dump(cache, f, ensure_ascii=False, indent=2, default=str)
print(f"\n💾 缓存已保存: cg05_30day_cache.json")
