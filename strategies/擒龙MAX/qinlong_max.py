"""
擒龙MAX — v9.0 六重风控版
基于5/11~5/15回测验证：
  Top3平均+14.8%，命中率11/15=73%

六重风控规则：
  ① 放量>2.5x二板 → 排除（巨量出货）
  ② 连板≥5 → 排除（动能耗尽）
  ③ 20日涨幅>50%+5日涨幅<20% → 排除（高位弱势反弹）
  ④ 首板放量>3x → 排除（分歧太大）
  ⑤ 连板≥1 → 扣10分（已涨过降权）
  ⑥ 7天内重复入选 → 排除（回避回头草）

评分：涨幅(35) > MACD/价比(25) > 量比(15) > 站MA5(12) > 位置(15)
加成：位置>50%减半，价格>45再减半
"""
import json, os, sys, time, subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

def curl_get(url, timeout=10):
    """用curl代替requests（修复SSL握手超时问题）"""
    try:
        r = subprocess.run(['curl', '-s', '--max-time', str(timeout), url],
                          capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ""

def fetch_kline(code, market):
    kf = os.path.join(CACHE_DIR, f"{market}{code}.json")
    if os.path.exists(kf) and time.time() - os.path.getmtime(kf) < 3600:
        try: return json.load(open(kf))
        except: pass
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,300,qfq"
    try:
        text = curl_get(url)
        d = json.loads(text) if text.strip().startswith("{") else {}
        sd = d.get("data",{}).get(f"{market}{code}",{})
        k = sd.get("qfqday",[])
        if not k:
            for key in sd:
                if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
        if len(k) < 80: return None
        recs = [{"date":x[0],"open":float(x[1]),"close":float(x[2]),"high":float(x[3]),"low":float(x[4]),"volume":float(x[5])} for x in k]
        os.makedirs(CACHE_DIR, exist_ok=True); json.dump(recs, open(kf, "w"))
        return recs
    except: return None

def ma(d, pd):
    res = []
    for i in range(len(d)):
        if i < pd-1: res.append(None)
        else: res.append(sum(d[i-pd+1:i+1])/pd)
    return res

def macd_calc(ps):
    if len(ps) < 26: return None, None, 0
    e12 = [ps[0]]; e26 = [ps[0]]; dif = [None]*len(ps); dea = [None]*len(ps)
    for i in range(1,len(ps)):
        e12.append(e12[-1]*11/13+ps[i]*2/13)
        e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i] = e12[i] - e26[i]
    dea[0] = dif[0] if dif[0] else 0
    for i in range(1,len(ps)): dea[i] = dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    return dif[-1], dea[-1], (dif[-1]-dea[-1]) if dif[-1] and dea[-1] else 0

def analyze(recs, code=None, past_top_codes=None):
    """擒龙MAX v8b评分
    code: 股票代码（用于重复入选检查）
    past_top_codes: set of stock codes that were in Top N in recent days (7天内重复入选排除)
    """
    if len(recs) < 80: return None
    if past_top_codes is None: past_top_codes = set()
    
    p = [r["close"] for r in recs]
    h = [r["high"] for r in recs]
    l = [r["low"] for r in recs]
    o = [r["open"] for r in recs]
    v = [r["volume"] for r in recs]
    n = len(recs)
    
    ma5 = ma(p,5); ma10 = ma(p,10); ma20 = ma(p,20); ma60 = ma(p,60)
    v5 = ma(v,5)
    d, m, mh = macd_calc(p)
    cur = p[-1]
    
    # ═══ 硬条件 ═══
    if not (ma60[-1] and cur > ma60[-1]): return None  # 站MA60
    if not (ma5[-1] and ma10[-1] and ma20[-1] and ma5[-1] > ma10[-1] > ma20[-1]): return None  # 多头排列
    if not (d and m and d > m): return None  # MACD金叉
    if cur >= 150: return None  # 不碰太贵的
    
    pct = [0]
    for i in range(1, n): pct.append((p[i]/p[i-1]-1)*100)
    
    if pct[-1] < -5: return None  # 大跌排除
    
    box_h = max(h[-61:-1]); box_l = min(l[-61:-1])
    if box_l and (box_h - box_l)/box_l * 100 > 80: return None  # 箱体太大
    
    # ═══ 新增风控过滤 ═══
    # 量比（不含当日）
    prev5 = v[-6:-1] if n >= 6 else v[:]
    avg_prev5 = sum(prev5)/len(prev5) if prev5 else 1
    vr_raw = v[-1] / avg_prev5 if avg_prev5 else 0
    vr = v[-1] / v5[-1] if v5[-1] else 0  # 原有量比（用于评分）
    
    # ① 放量>2.5x 且 前一天也是涨停 → 巨量出货板，排除
    if pct[-1] > 9 and vr_raw > 2.5 and n >= 2 and pct[-2] > 9:
        return None
    
    # ② 连续涨停≥5 → 耗尽动能，排除
    streak = 0
    for i in range(n-2, -1, -1):
        if pct[i] > 9: streak += 1
        else: break
    if streak >= 5:
        return None
    
    # ③ 20日涨幅>50% 且 5日涨幅<20% → 高位弱势反弹，排除
    if n >= 21:
        p20_chg = (p[-1] / p[-21] - 1) * 100
        p5_chg = (p[-1] / p[-6] - 1) * 100 if n >= 6 else 0
        if p20_chg > 50 and p5_chg < 20:
            return None
    
    # ④ 首板放量>3x → 分歧太大，排除
    if pct[-1] > 9 and vr_raw > 3 and streak == 0:
        return None
    
    # 位置（使用箱体中心法，同原作擒龙）
    if n >= 120:
        rl = min(p[-120:]); rh = max(p[-120:])
        pos = ((box_h + box_l) / 2 - rl) / (rh - rl) * 100 if (rh - rl) > 0 else 50
    else:
        pos = 50
    if pos > 85: return None  # 排除极高位置
    
    # ═══ v8b评分 ═══
    score = 0
    sigs = []
    
    # MACD/价格比（归一化）
    macd_r = d/cur*100 if cur > 0 else 0
    if macd_r > 5: score += 25; sigs.append(f"MCD/价{macd_r:.1f}%🔥")
    elif macd_r > 2: score += 20; sigs.append(f"MCD/价{macd_r:.1f}%↑")
    elif macd_r > 1: score += 12; sigs.append(f"MCD/价{macd_r:.1f}%")
    elif macd_r > 0: score += 5
    
    # 量比
    vr = v[-1] / v5[-1] if v5[-1] else 0
    
    # 今日涨幅（最高权重）
    if pct[-1] > 9: 
        score += 35; sigs.append(f"涨停🔥🔥🔥")
        # 涨停加分——位置>50%减半，价格>45再减半
        bonus_mult = 1.0
        if pos >= 50: bonus_mult *= 0.5
        if cur > 45: bonus_mult *= 0.5  # 高价股加成减半
        if macd_r > 5: score += int(15 * bonus_mult); sigs.append("MACD强板💎")
        if vr < 0.5: score += int(12 * bonus_mult); sigs.append("缩量板💎")
        elif vr > 2: score -= 5  # 放量涨停扣分（分歧大）
    elif pct[-1] > 7: score += 30; sigs.append(f"大涨{pct[-1]:.0f}%🔥🔥")
    elif pct[-1] > 5: score += 25; sigs.append(f"大涨{pct[-1]:.0f}%🔥")
    elif pct[-1] > 3: score += 15; sigs.append(f"启动{pct[-1]:.1f}%")
    elif pct[-1] > 0: score += 8; sigs.append(f"涨{pct[-1]:+.1f}%")
    elif pct[-1] > -2: score += 3

    # 量比确认
    if vr > 2: score += 15; sigs.append(f"放量{vr:.2f}x🔥")
    elif vr > 1.2: score += 10; sigs.append(f"量{vr:.2f}x")
    elif vr > 0.7: score += 5
    elif vr < 0.5: score += 3; sigs.append(f"缩量{vr:.2f}x")
    
    # 站MA5
    above_ma5 = ma5[-1] and cur > ma5[-1]
    if above_ma5: score += 12; sigs.append("站MA5")
    
    # 位置加分（越低越好，>50扣分）
    if pos < 30: score += 15; sigs.append(f"低位{pos:.0f}%🔥")
    elif pos < 40: score += 12; sigs.append(f"低位{pos:.0f}%")
    elif pos < 50: score += 8
    elif pos < 60: score += 3
    elif pos > 60: score -= 5  # 高位扣分（空间有限）
    
    # 前期动能
    sum5 = sum(pct[-5:]) if n >= 6 else 0
    if sum5 > 5: score += 8; sigs.append(f"前{sum5:.0f}%")
    elif sum5 > 2: score += 3
    
    # 价格加分（5-35元最佳）
    if 5 < cur < 35: score += 5
    
    # 连涨
    green5 = sum(1 for i in range(-6,-1) if pct[i] > 0)
    if green5 >= 3: score += 5; sigs.append(f"连涨{green5}")
    
    # ⑤ 连板扣分：买入前已有涨停 → 扣10分
    if streak >= 1:
        score -= 10
        sigs.append(f"连板{streak}⚠️")
    
    # ⑥ 7天内重复入选 → 排除（已在之前天数进过Top的，再入选就是鱼尾）
    if code in past_top_codes:
        return None
    
    if score < 60: return None
    
    return {"score": score, "sigs": " | ".join(sigs[:8]), "macd_r": round(macd_r, 2),
            "vr": round(vr, 2), "pos": round(pos, 1), "sum5": round(sum5, 1)}


def batch_query(codes):
    qid = ",".join(codes)
    try:
        text = curl_get(f"https://qt.gtimg.cn/q={qid}", timeout=12)
        res = []
        for line in text.strip().split(";"):
            line = line.strip().strip(";")
            if not line or "=" not in line: continue
            pts = line.split("~")
            if len(pts) < 40: continue
            try:
                cf, nm = pts[2], pts[1]
                pr = float(pts[3]) if pts[3] else 0
                pc = float(pts[32]) if pts[32] else 0
                c = cf.replace("sh","").replace("sz","")
                mk = "sh" if cf.startswith("sh") else "sz"
                if c and nm and pr > 0:
                    res.append({"code":c,"market":mk,"name":nm,"price":pr,"pct":pc})
            except: continue
        return res
    except: return []

def get_future_perf(code, market, ed, ep):
    recs = fetch_kline(code, market)
    if not recs: return None
    bi = None
    for i, r in enumerate(recs):
        if r["date"] == ed: bi = i; break
    if bi is None: return None
    after = recs[bi+1:bi+6]
    if not after: return None  # 至少要有1天数据
    days = len(after)
    prices = [x["close"] for x in after]
    return {"max5": round((max(prices)/ep-1)*100, 1), "ret5": round((after[-1]["close"]/ep-1)*100, 1),
            "days": days}

def run_qinlong_max(test_date=None, past_top_codes=None):
    t0 = time.time()
    is_bt = test_date is not None
    if past_top_codes is None: past_top_codes = set()
    
    print("=" * 80)
    print(f"  🐉 擒龙MAX — v8b纯评分版")
    print(f"  日期: {test_date if is_bt else datetime.now().strftime('%Y-%m-%d')}")
    print(f"  规则: MACD金叉+多头排列+站MA60 → v8b评分排序(不附加分)")
    print("=" * 80)
    
    # 获取全市场股票
    all_codes = []
    for i in range(600000, 606000): all_codes.append(f"sh{i}")
    for i in range(0, 2000): all_codes.append(f"sz{i:06d}")
    for i in range(2000, 3000): all_codes.append(f"sz{i:06d}")
    
    if is_bt:
        # 回测模式：先拿K线，从K线取价格
        batches = [all_codes[i:i+50] for i in range(0, len(all_codes), 50)]
        active_codes = set()
        code_names = {}
        with ThreadPoolExecutor(max_workers=20) as ex:
            fm = {ex.submit(batch_query, b): i for i, b in enumerate(batches)}
            for f in as_completed(fm):
                for s in f.result():
                    c = s["code"]
                    if not c.startswith(("300","688")) and "ST" not in s["name"].upper() and "退市" not in s["name"]:
                        active_codes.add(c)
                        code_names[c] = s["name"]
        print(f"  ✅ 活跃: {len(active_codes)}只 ({time.time()-t0:.0f}s)")
        
        kline_cache = {}
        with ThreadPoolExecutor(max_workers=30) as ex:
            fm = {ex.submit(fetch_kline, c, "sh" if c >= "600000" else "sz"): c for c in active_codes}
            for f in as_completed(fm):
                if f.result(): kline_cache[fm[f]] = f.result()
        print(f"  ✅ K线: {len(kline_cache)}/{len(active_codes)} ({time.time()-t0:.0f}s)")
        
        candidates = []
        for code, recs in kline_cache.items():
            hist = [r for r in recs if r["date"] <= test_date]
            if len(hist) < 80: continue
            cur = hist[-1]["close"]
            pct_d = (cur/hist[-2]["close"]-1)*100 if len(hist) >= 2 else 0
            if cur >= 150: continue
            candidates.append({"code": code, "market": "sh" if code >= "600000" else "sz",
                               "price": cur, "pct": pct_d, "name": code_names.get(code, "?")})
    else:
        batches = [all_codes[i:i+50] for i in range(0, len(all_codes), 50)]
        candidates = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            fm = {ex.submit(batch_query, b): i for i, b in enumerate(batches)}
            for f in as_completed(fm):
                for s in f.result():
                    c = s["code"]
                    if c.startswith(("300","688")) or "ST" in s["name"].upper() or "退市" in s["name"]: continue
                    candidates.append(s)
        print(f"  ✅ 候选: {len(candidates)}只 ({time.time()-t0:.0f}s)")
        
        kline_cache = {}
        with ThreadPoolExecutor(max_workers=30) as ex:
            fm = {ex.submit(fetch_kline, s["code"], s["market"]): s for s in candidates}
            for f in as_completed(fm):
                s = fm[f]; recs = f.result()
                if recs: kline_cache[s["code"]] = recs
        print(f"  ✅ K线: {len(kline_cache)}/{len(candidates)} ({time.time()-t0:.0f}s)")
    
    # 评分
    results = []
    for s in candidates:
        recs = kline_cache.get(s["code"])
        if not recs: continue
        hist = [r for r in recs if r["date"] <= (test_date if is_bt else recs[-1]["date"])]
        if len(hist) < 80: continue
        r = analyze(hist, code=s["code"], past_top_codes=past_top_codes)
        if r:
            results.append({**s, **r})
    
    print(f"  ✅ 评分通过: {len(results)}只")
    
    if not results:
        print("  ❌ 无候选")
        return []
    
    # 排序
    results.sort(key=lambda x: -x["score"])
    
    # 输出TopN，突出Top3
    top_n = 10
    top3 = results[:3]
    top10 = results[:top_n]
    tt = time.time() - t0
    
    print(f"\n{'='*80}")
    print(f"  🏆 TOP {top_n} (擒龙MAX)")
    print(f"{'='*80}")
    print(f"  {'#':>2} {'名称':<10} {'代码':<7} {'现价':>7} {'今日':>7} {'评分':>4} {'MCD/价':>6} {'量比':>5} {'位':>4} {'信号':<40}")
    print(f"  {'─'*100}")
    for i, r in enumerate(top10, 1):
        print(f"  {i:>2}. {r['name']:<10} {r['code']:<7} {r['price']:>7.2f} {r['pct']:>+6.2f}% {r['score']:>4}分 "
              f"{r['macd_r']:>5.1f}% {r['vr']:>4.2f}x {r['pos']:>3.0f}% {r['sigs'][:40]}")
    
    if is_bt and top3:
        print(f"\n  ── 买入后5日最高涨幅 ──")
        bt_res = []
        pf = []
        with ThreadPoolExecutor(max_workers=30) as ex:
            fm = {ex.submit(get_future_perf, r["code"], r["market"], test_date, r["price"]): r for r in top3}
            for f in as_completed(fm):
                r = fm[f]; p = f.result()
                r["max5"] = p["max5"] if p else None
                r["ret5"] = p["ret5"] if p else None
                r["days"] = p["days"] if p else None
                bt_res.append(r)
                if p: pf.append(p)
        wins = sum(1 for r in bt_res if r.get("ret5") and r["ret5"] >= 5)
        wins5 = sum(1 for r in bt_res if r.get("max5") and r["max5"] >= 5)
        avg5 = sum(p["max5"] for p in pf) / len(pf) if pf else 0
        print(f"  {'名称':<10} {'代码':<7} {'评分':>4} {'天数':>4} {'期间最高':>8} {'最新涨幅':>8}")
        print(f"  {'─'*45}")
        for r in bt_res:
            days = f"{r['days']}天" if r.get('days') else "—"
            m5 = f"{r['max5']:+.1f}%" if r['max5'] is not None else "—"
            r5 = f"{r['ret5']:+.1f}%" if r['ret5'] is not None else "—"
            print(f"  {r['name']:<10} {r['code']:<7} {r['score']:>4}分 {days:>4} {m5:>8} {r5:>8}")
        print(f"\n  📊 Top3 | 收涨≥5%: {wins}/3={wins/len(pf)*100 if pf else 0:.0f}% | 途中≥5%: {wins5}/3={wins5/len(pf)*100 if pf else 0:.0f}% | 平均: {avg5:+.1f}%")
    
    print(f"\n{'='*80}")
    print(f"  耗时: {tt:.0f}s")
    print(f"{'='*80}")
    return top10, {r['code'] for r in top10}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--backtest":
        run_qinlong_max(test_date=sys.argv[2])
    else:
        run_qinlong_max()
