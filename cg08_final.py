#!/usr/bin/env python3
"""
CG-08 选股 — 实时API版 ⚡
评分：涨跌幅×1 + ATR×1.5 + DIF×0.5 + 收盘位×0.02 - 上影>40%-3
数据源：腾讯API实时K线 + 新浪实时行情
"""
import json, os, sys, time, subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── 工具函数 ─────────────────────────────
def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ""

def fetch_kline(code, market):
    """从腾讯API获取K线（1小时缓存自动刷新）"""
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
        os.makedirs(CACHE_DIR, exist_ok=True); json.dump(recs, open(kf,"w"))
        return recs
    except: return None

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "hermes-agent", "cache")
ST_FILE = os.path.join(os.path.dirname(__file__), "st_codes.txt")
ST = set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST = {l.strip() for l in f if l.strip()}

# ─── 评分 ─────────────────────────────────
def calc_atr(recs, n=14):
    if len(recs) < n: return 0
    trs = []
    for i in range(-n, 0):
        h, l, pc = recs[i]['high'], recs[i]['low'], recs[i-1]['close'] if i > -n else recs[i]['open']
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(trs)/n/recs[-1]['close']*100

def calc_cl(recs, n=20):
    if len(recs) < n: return 0
    hs = [r['high'] for r in recs[-n:]]
    ls = [r['low'] for r in recs[-n:]]
    c = recs[-1]['close']
    return (c - min(ls)) / (max(hs) - min(ls)) * 100

def cg08_score(recs):
    if len(recs) < 80: return None
    p = [r['close'] for r in recs]
    n = len(recs)
    ma5 = sum(p[-5:])/5; ma10 = sum(p[-10:])/10; ma20 = sum(p[-20:])/20; ma60 = sum(p[-60:])/60
    cur = p[-1]
    
    # 硬条件
    if not (cur > ma60): return None
    if not (ma5 > ma10 > ma20): return None
    if cur >= 80: return None
    
    # 涨跌幅
    pct = (p[-1]/p[-2]-1)*100
    if pct is None or not (1 <= pct < 8): return None
    
    # 阳线
    is_yang = 1 if recs[-1]['close'] > recs[-1]['open'] else 0
    if is_yang != 1: return None
    
    # 站上MA5
    if not (cur > ma5): return None
    
    # ATR
    atr = calc_atr(recs)
    if atr <= 3: return None
    
    # 收盘位
    cl = calc_cl(recs)
    
    # 上影
    last = recs[-1]
    upper_shadow = (last['high'] - max(last['close'], last['open'])) / (last['high'] - last['low']) * 100 if (last['high']-last['low']) > 0 else 0
    
    # MACD
    ema12 = [p[0]]
    ema26 = [p[0]]
    for i in range(1, n):
        ema12.append(ema12[-1]*11/13 + p[i]*2/13)
        ema26.append(ema26[-1]*25/27 + p[i]*2/27)
    dif = ema12[-1] - ema26[-1]
    dea = dif  # simplified
    
    # 评分
    score = pct + atr * 1.5 + dif * 0.5 + cl * 0.02 - (3 if upper_shadow > 40 else 0)
    
    return {
        'code': code,
        'pct': round(pct, 2), 'atr': round(atr, 2),
        'cl': round(cl, 1), 'dif': round(dif, 3),
        'shadow': round(upper_shadow, 1),
        'score': round(score, 2),
        'close': cur,
        'ma5': round(ma5, 2), 'ma10': round(ma10, 2), 'ma20': round(ma20, 2)
    }

if __name__ == '__main__':
    t0 = time.time()
    today = datetime.now()
    if today.weekday() >= 5:
        print(f"非交易日，跳过"); sys.exit(0)
    
    # 获取活跃股票
    all_codes = []
    for i in range(600000, 606000): all_codes.append(f"sh{i}")
    for i in range(0, 2000): all_codes.append(f"sz{i:06d}")
    for i in range(2000, 3000): all_codes.append(f"sz{i:06d}")
    
    print(f"扫描活跃股票...", flush=True)
    batches = [all_codes[i:i+50] for i in range(0, len(all_codes), 50)]
    active_codes = set()
    names = {}
    for batch in batches:
        text = curl_get(f"https://qt.gtimg.cn/q={','.join(batch)}", timeout=8)
        for line in text.split("\n"):
            if "=\"" not in line: continue
            parts = line.split("~")
            if len(parts) < 3: continue
            cid = line.split("_")[-1].split("=")[0]
            nm = parts[1]
            if not nm or "ST" in nm or "*ST" in nm or "退" in nm: continue
            if cid.startswith("sh") and cid[2:].startswith(("3","68")): continue
            if cid.startswith("sz") and cid[2:].startswith(("3","68")): continue
            active_codes.add(cid)
            names[cid] = nm
    
    print(f"  活跃: {len(active_codes)}只 ({time.time()-t0:.0f}s)", flush=True)
    
    # 获取K线
    kline_cache = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        mkt = lambda c: "sh" if c.startswith("sh") else "sz"
        futs = {ex.submit(fetch_kline, c[2:], mkt(c)): c for c in active_codes}
        for f in as_completed(futs):
            c = futs[f]; r = f.result()
            if r: kline_cache[c] = r
    
    print(f"  K线: {len(kline_cache)}/{len(active_codes)} ({time.time()-t0:.0f}s)", flush=True)
    
    # 评分
    results = []
    for code, recs in kline_cache.items():
        s = cg08_score(recs)
        if s: results.append(s)
    
    results.sort(key=lambda x: -x['score'])
    
    date_str = today.strftime('%Y-%m-%d')
    print(f"\n📅 {date_str}")
    print(f"🏆 CG-08 推荐Top3（实时API）：")
    for i, r in enumerate(results[:3], 1):
        nm = names.get(r['code'], '?')
        print(f"  {i}. {nm}({r['code']}) 买入{r['close']:.2f} 涨{r['pct']:+.1f}% ATR{r['atr']:.1f}% CL{r['cl']:.0f}% DIF{r['dif']:.3f} 评分{r['score']:.1f}")
    
    if len(results) > 3:
        print(f"  ...共{len(results)}只候选")
    
    print(f"\n⏱ 耗时: {time.time()-t0:.0f}s")
