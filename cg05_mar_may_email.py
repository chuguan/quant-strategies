     1|     1|#!/usr/bin/env python3
     2|     2|"""CG-05 3月~5月回测+冠军表+邮件"""
     3|     3|import json, os, sys, time, subprocess, requests
     4|     4|sys.path.insert(0, os.path.dirname(__file__))
     5|     5|from send_email import send_email
     6|     6|from datetime import datetime
     7|     7|
     8|     8|CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
     9|     9|
    10|    10|# 技术指标
    11|    11|def ma(d, pd):
    12|    12|    r = []
    13|    13|    for i in range(len(d)):
    14|    14|        if i < pd-1: r.append(None)
    15|    15|        else: r.append(sum(d[i-pd+1:i+1])/pd)
    16|    16|    return r
    17|    17|
    18|    18|def macd_full(ps):
    19|    19|    n = len(ps)
    20|    20|    if n < 26: return None, None, None
    21|    21|    e12 = [ps[0]]; e26 = [ps[0]]
    22|    22|    dif = [None]*n; dea = [None]*n; macd = [None]*n
    23|    23|    for i in range(1, n):
    24|    24|        e12.append(e12[-1]*11/13+ps[i]*2/13)
    25|    25|        e26.append(e26[-1]*25/27+ps[i]*2/27)
    26|    26|        dif[i] = e12[i] - e26[i]
    27|    27|    dea[0] = dif[0] if dif[0] else 0
    28|    28|    for i in range(1, n):
    29|    29|        dea[i] = dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    30|    30|    for i in range(n):
    31|    31|        if dif[i] is not None and dea[i] is not None:
    32|    32|            macd[i] = dif[i] - dea[i]
    33|    33|    return dif, dea, macd
    34|    34|
    35|    35|def kdj_calc(highs, lows, closes, n=9):
    36|    36|    L = len(closes)
    37|    37|    if L < n: return None, None, None
    38|    38|    k = [50.0]*L; d = [50.0]*L; j = [50.0]*L
    39|    39|    for i in range(n-1, L):
    40|    40|        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
    41|    41|        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
    42|    42|        if i == n-1: k[i] = 50.0
    43|    43|        else: k[i] = 2/3*k[i-1] + 1/3*rsv
    44|    44|        d[i] = 2/3*d[i-1] + 1/3*k[i]
    45|    45|        j[i] = 3*k[i] - 2*d[i]
    46|    46|    return k, d, j
    47|    47|
    48|    48|# CG-05参数
    49|    49|P = {"pct_lower": 4, "pct_upper": 5, "ma5_slope_min": 10, "close_pos_min": 50, "vr_max": 2.5, "j_ratio_min": 15}
    50|    50|
    51|    51|# ═══ 加载 ═══
    52|    52|print("📡 加载数据...")
    53|    53|all_data = {}
    54|    54|for fn in os.listdir(CACHE_DIR):
    55|    55|    if not fn.endswith('.json'): continue
    56|    56|    if not (fn.startswith('sh6') or fn.startswith('sz0')): continue
    57|    57|    try:
    58|    58|        with open(os.path.join(CACHE_DIR, fn), 'rb') as f:
    59|    59|            recs = json.loads(f.read().decode('utf-8'))
    60|    60|        if not isinstance(recs, list) or len(recs) < 80: continue
    61|    61|        mkt = "sh" if fn.startswith("sh") else "sz"
    62|    62|        cd = fn.replace('.json','').replace('sh','').replace('sz','')
    63|    63|        cp = [r["close"] for r in recs]; hp = [r["high"] for r in recs]
    64|    64|        lp = [r["low"] for r in recs]; vv = [r["volume"] for r in recs]
    65|    65|        op = [r.get("open", r["close"]) for r in recs]; ds = [r["date"] for r in recs]
    66|    66|        pct = [0.0]
    67|    67|        for i in range(1, len(cp)): pct.append((cp[i]/cp[i-1]-1)*100)
    68|    68|        ma5=ma(cp,5); ma10=ma(cp,10); ma20=ma(cp,20); ma60=ma(cp,60)
    69|    69|        v5=ma(vv,5); dif,dea,macd=macd_full(cp); k_,d_,j_=kdj_calc(hp,lp,cp)
    70|    70|        di_={ds[i]:i for i in range(len(ds))}
    71|    71|        all_data[cd]={"p":cp,"h":hp,"l":lp,"v":vv,"o":op,"pct":pct,"ds":ds,"di":di_,
    72|    72|            "ma5":ma5,"ma10":ma10,"ma20":ma20,"ma60":ma60,"v5":v5,
    73|    73|            "dif":dif,"dea":dea,"macd":macd,"k":k_,"d":d_,"j":j_,"recs":recs}
    74|    74|    except: pass
    75|    75|print(f"  ✅ {len(all_data)} 只")
    76|    76|
    77|    77|# 日期
    78|    78|tds = sorted(set(dt for sd in all_data.values() for dt in sd["ds"] if dt >= "2025-01-01" and dt <= "2025-12-31"))
    79|    79|print(f"  📅 {tds[0]} ~ {tds[-1]} 共{len(tds)}天")
    80|    80|
    81|    81|# 预计算
    82|    82|print("📡 预计算...")
    83|    83|fl = {}
    84|    84|for cd, sd in all_data.items():
    85|    85|    recs = sd["recs"]
    86|    86|    for i in range(len(recs)-5):
    87|    87|        dt = recs[i]["date"]
    88|    88|        if dt < "2025-01-01" or dt > "2025-12-31": continue
    89|    89|        buy = recs[i]["close"]
    90|    90|        if buy <= 0: continue
    91|    91|        after = recs[i+1:i+6]
    92|    92|        if not after: continue
    93|    93|        m5 = round((max(x["high"] for x in after)/buy-1)*100, 1)
    94|    94|        dd = []; prev = buy
    95|    95|        for x in after:
    96|    96|            dh = round((x["high"]/buy-1)*100, 1)
    97|    97|            dc = round((x["close"]/buy-1)*100, 1)
    98|    98|            arr = "↑" if x["close"] > prev else ("↓" if x["close"] < prev else "→")
    99|    99|            dd.append({"high":dh,"close":dc,"arrow":arr,"date":x["date"]})
   100|   100|            prev = x["close"]
   101|   101|        fl[(cd,dt)] = {"max5":m5,"daily":dd}
   102|   102|print(f"  ✅ {len(fl)} 条")
   103|   103|
   104|   104|# 大盘
   105|   105|print("📡 大盘...")
   106|   106|idx = {}
   107|   107|try:
   108|   108|    r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,320,qfq",
   109|   109|                     headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
   110|   110|    d = r.json()
   111|   111|    sd = d.get('data',{}).get('sh000001',{})
   112|   112|    k = sd.get('qfqday',[])
   113|   113|    if not k:
   114|   114|        for key in sd:
   115|   115|            if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
   116|   116|    prev = None
   117|   117|    for x in k:
   118|   118|        dt = x[0]; close = float(x[2])
   119|   119|        if dt >= "2025-01-01" and dt <= "2025-12-31":
   120|   120|            if prev: idx[dt] = round((close/prev-1)*100, 2)
   121|   121|            else: idx[dt] = 0.0
   122|   122|        prev = close
   123|   123|except: pass
   124|   124|
   125|   125|# ═══ 回测 ═══
   126|   126|print(f"🚀 回测 {len(tds)}天...")
   127|   127|champ = {}; top5 = {}
   128|   128|
   129|   129|for td in tds:
   130|   130|    res = []
   131|   131|    for cd, sd in all_data.items():
   132|   132|        di = sd["di"].get(td)
   133|   133|        if di is None or di < 80: continue
   134|   134|        p=sd["p"]; h=sd["h"]; l=sd["l"]; v=sd["v"]; o=sd["o"]; pct=sd["pct"]
   135|   135|        m5=sd["ma5"]; m10=sd["ma10"]; m20=sd["ma20"]; m60=sd["ma60"]
   136|   136|        v5=sd["v5"]; dif=sd["dif"]; dea=sd["dea"]; macd=sd["macd"]
   137|   137|        k=sd["k"]; d=sd["d"]; j=sd["j"]
   138|   138|        
   139|   139|        cur = p[di]
   140|   140|        if cur > 80: continue
   141|   141|        if cur <= o[di] or (cur-o[di])/o[di]*100 < 1: continue
   142|   142|        if v5[di] and v[di]/v5[di] > P["vr_max"]: continue
   143|   143|        if (h[di]-l[di]) > 0 and (cur-l[di])/(h[di]-l[di])*100 < P["close_pos_min"]: continue
   144|   144|        if not (m60[di] and m60[di] > 0): continue
   145|   145|        if not (dif[di] and dea[di] and dif[di] > dea[di]): continue
   146|   146|        if not (macd[di] and macd[di] > 0): continue
   147|   147|        if dif[di]-dea[di] < 0.1: continue
   148|   148|        if macd[di-1] is not None and macd[di] <= macd[di-1]: continue
   149|   149|        if macd[di-1] is not None and macd[di-2] is not None:
   150|   150|            if macd[di]-macd[di-1] < macd[di-1]-macd[di-2]: continue
   151|   151|        if dif[di-3] is not None and dif[di] <= dif[di-3]: continue
   152|   152|        
   153|   153|        js = j[di]-j[di-1] if (j[di-1] is not None and j[di] is not None) else 0
   154|   154|        dp = d[di-1] if d[di-1] is not None and d[di-1] != 0 else 1
   155|   155|        jr = js/dp*100
   156|   156|        kg = (j[di]>k[di]>d[di]) or (j[di]>k[di] and k[di]<=d[di])
   157|   157|        if j[di-1] is not None and k[di-1] is not None and j[di-1]<=k[di-1] and j[di]>k[di]: kg = True
   158|   158|        if not (jr > P["j_ratio_min"] or kg): continue
   159|   159|        if k[di] > 80 and j[di] > 90: continue
   160|   160|        if k[di] < 20: continue
   161|   161|        if not (m5[di] and m5[di-3] and m5[di] > m5[di-3]): continue
   162|   162|        if not (m20[di] and m20[di-5] and m20[di] > m20[di-5]): continue
   163|   163|        if not (m5[di] and m10[di] and m20[di] and m5[di] > m10[di] > m20[di]): continue
   164|   164|        if not (m5[di] and cur > m5[di]): continue
   165|   165|        if m5[di] and m5[di-5] and m5[di-5] > 0:
   166|   166|            sl = (m5[di]-m5[di-5])/m5[di-5]*100
   167|   167|            if sl <= P["ma5_slope_min"]: continue
   168|   168|        else: continue
   169|   169|        gap = m10[di]-m20[di] if (m10[di] and m20[di]) else 0
   170|   170|        gb = m10[di-4]-m20[di-4] if (m10[di-4] and m20[di-4]) else 0
   171|   171|        if gap <= gb*0.8: continue
   172|   172|        if not (P["pct_lower"] < pct[di] < P["pct_upper"]): continue
   173|   173|        
   174|   174|        sc = 0
   175|   175|        mr = dif[di]/cur*100 if cur > 0 else 0
   176|   176|        if mr > 5: sc += 25
   177|   177|        elif mr > 2: sc += 20
   178|   178|        elif mr > 1: sc += 12
   179|   179|        elif mr > 0: sc += 5
   180|   180|        vr = v[di]/v5[di] if v5[di] else 0
   181|   181|        if pct[di] > 7: sc += 30
   182|   182|        elif pct[di] > 5: sc += 25
   183|   183|        elif pct[di] > 3: sc += 15
   184|   184|        elif pct[di] > 0: sc += 8
   185|   185|        if vr > 2: sc += 15
   186|   186|        elif vr > 1.2: sc += 10
   187|   187|        elif vr > 0.7: sc += 5
   188|   188|        if m5[di] and cur > m5[di]: sc += 12
   189|   189|        if len(p) >= 120 and di >= 120:
   190|   190|            bh = max(h[di-60:di-1]); bl = min(l[di-60:di-1])
   191|   191|            rl = min(p[di-120:di]); rh = max(p[di-120:di])
   192|   192|            pos = ((bh+bl)/2 - rl)/(rh - rl)*100 if (rh-rl) > 0 else 50
   193|   193|        else: pos = 50
   194|   194|        if pos < 30: sc += 15
   195|   195|        elif pos < 50: sc += 8
   196|   196|        elif pos > 60: sc -= 5
   197|   197|        s5 = sum(pct[di-4:di+1]) if di >= 5 else 0
   198|   198|        if s5 > 5: sc += 8
   199|   199|        if 5 < cur < 35: sc += 5
   200|   200|        gc = sum(1 for i in range(max(0,di-5), di-1) if pct[i] > 0)
   201|   201|        if gc >= 3: sc += 5
   202|   202|        if pct[di] > 4.5: sc -= 8
   203|   203|        if di >= 1 and pct[di-1] > 3: sc -= 5
   204|   204|        if di >= 2 and pct[di-2] > 3: sc -= 5
   205|   205|        sh = h[di] - max(o[di], cur); tr = h[di]-l[di]
   206|   206|        if tr > 0 and sh > 0:
   207|   207|            sr = sh/tr*100
   208|   208|            if sr > 50: sc -= 5
   209|   209|            elif sr > 30: sc -= 3
   210|   210|            elif sr > 15: sc -= 1
   211|   211|        
   212|   212|        fp = fl.get((cd, td))
   213|   213|        res.append({"code":cd,"name":"?","score":sc,"price":cur,"pct_d":pct[di],
   214|   214|            "max5":fp["max5"] if fp else None,"daily":fp["daily"] if fp else []})
   215|   215|    
   216|   216|    if not res:
   217|   217|        champ[td] = None
   218|   218|        continue
   219|   219|    
   220|   220|    res.sort(key=lambda x: -x["score"])
   221|   221|    c = res[0]
   222|   222|    champ[td] = {"name":"?","code":c["code"],"qscore":c["score"],
   223|   223|        "kl_close":c["price"],"pct_d":c["pct_d"],
   224|   224|        "max5":c["max5"],"daily":c["daily"],"index_pct":idx.get(td)}
   225|   225|    top5[td] = [{"rank":i+1,"name":"?","code":r["code"],"score":r["score"],
   226|   226|        "price":round(r["price"],2),"pct":r["pct_d"],"max5":r["max5"],
   227|   227|        "daily":r["daily"] if i==0 else []} for i,r in enumerate(res[:5])]
   228|   228|
   229|   229|# ═══ 获取名称 ═══
   230|   230|print("📡 获取股票名称...")
   231|   231|cc = set()
   232|   232|for dt,c in champ.items():
   233|   233|    if c: cc.add(c["code"])
   234|   234|for dt,t in top5.items():
   235|   235|    for r in t: cc.add(r["code"])
   236|   236|nm = {}
   237|   237|for c in sorted(cc):
   238|   238|    try:
   239|   239|        mk = "sh" if int(c) >= 600000 else "sz"
   240|   240|        tx = subprocess.run(['curl','-s','-m','5',f'https://qt.gtimg.cn/q={mk}{c}'],
   241|   241|                          capture_output=True,timeout=8).stdout.decode('gbk',errors='replace')
   242|   242|        pts = tx.split("~"); nm[c] = pts[1] if len(pts) > 1 else c
   243|   243|    except: nm[c] = c
   244|   244|for dt,c in champ.items():
   245|   245|    if c and c["code"] in nm: c["name"] = nm[c["code"]]
   246|   246|for dt,t in top5.items():
   247|   247|    for r in t:
   248|   248|        if r["code"] in nm: r["name"] = nm[r["code"]]
   249|   249|
   250|   250|# ═══ 统计 ═══
   251|   251|vl = [(k,v) for k,v in sorted(champ.items(), reverse=True) if v is not None]
   252|   252|h10 = sum(1 for _,c in vl if isinstance(c.get("max5"),(int,float)) and c["max5"]>=10)
   253|   253|h5 = sum(1 for _,c in vl if isinstance(c.get("max5"),(int,float)) and c["max5"]>=5)
   254|   254|tt = sum(1 for _,c in vl if isinstance(c.get("max5"),(int,float)))
   255|   255|av = sum(c["max5"] for _,c in vl if isinstance(c.get("max5"),(int,float)))
   256|   256|avs = f"{av/tt:.1f}" if tt else "0"
   257|   257|h10r = f"{h10/tt*100:.0f}" if tt else "0"
   258|   258|h5r = f"{h5/tt*100:.0f}" if tt else "0"
   259|   259|l5 = sorted(top5.keys(), reverse=True)[:5]
   260|   260|
   261|   261|# ═══ HTML ═══
   262|   262|h = """<!DOCTYPE html>
   263|   263|<html lang="zh-CN">
   264|   264|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
   265|   265|<style>
   266|   266|*{margin:0;padding:0;box-sizing:border-box}
   267|   267|body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:10px}
   268|   268|.container{max-width:680px;margin:0 auto}
   269|   269|.header{background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:12px;padding:14px;margin-bottom:10px;border:1px solid #30363d;text-align:center}
   270|   270|.header h1{font-size:17px;color:#58a6ff}
   271|   271|.header .sub{font-size:9px;color:#8b949e;margin-top:2px}
   272|   272|.stats{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap;justify-content:center}
   273|   273|.sb{flex:1;min-width:60px;max-width:90px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:6px 4px;text-align:center}
   274|   274|.sb .n{font-size:15px;font-weight:700}
   275|   275|.sb .l{font-size:7px;color:#8b949e;margin-top:1px}
   276|   276|.sb.g .n{color:#f85149} .sb.b .n{color:#58a6ff} .sb.o .n{color:#d29922}
   277|   277|.st{font-size:12px;font-weight:700;padding:6px 2px 2px}
   278|   278|.card{background:#161b22;border:1px solid #30363d;border-radius:8px;margin-bottom:8px;overflow-x:auto}
   279|   279|.sw{overflow-x:auto}
   280|   280|table{width:100%;border-collapse:collapse;font-size:9px;min-width:620px}
   281|   281|th{background:#1c2128;padding:3px 2px;text-align:center;font-weight:500;color:#8b949e;font-size:7px;border-bottom:1px solid #30363d}
   282|   282|td{padding:3px 2px;text-align:center;border-bottom:1px solid #21262d;font-family:"Consolas",monospace;font-size:8px}
   283|   283|.num{font-family:"Consolas",monospace;text-align:center}
   284|   284|.up{color:#f85149} .down{color:#3fb950} .warn{color:#d29922}
   285|   285|.code{color:#8b949e;font-size:7px}
   286|   286|.ft{text-align:center;color:#484f58;font-size:7px;padding:6px 0}
   287|   287|.dc{padding:6px 8px}
   288|   288|.dt{font-size:10px;font-weight:700;margin-bottom:4px}
   289|   289|.fs{font-size:7px}
   290|   290|.na{color:#484f58}
   291|   291|</style></head><body>
   292|   292|<div class="container">
   293|   293|<div class="header">
   294|   294|<h1>🐉 CG-05 2025全年冠军表</h1>
   295|   295|<div class="sub">2025-01-02 ~ 2025-12-31 | 涨4~5% MA5≥10% 位≥50% 量≤2.5 J≥15%</div>
   296|   296|</div>
   297|   297|<div class="stats">
   298|   298|<div class="sb g"><div class="n">"""+avs+"""%</div><div class="l">均最高</div></div>
   299|   299|<div class="sb b"><div class="n">"""+h10r+"""%</div><div class="l">达标10%+</div></div>
   300|   300|<div class="sb o"><div class="n">"""+str(len(vl))+"""天</div><div class="l">出票</div></div>
   301|   301|</div>"""
   302|   302|
   303|   303|# 冠军表
   304|   304|h += '<div class="st">📋 全期冠军表</div><div class="card"><div class="sw"><table>'
   305|   305|h += '<thead><tr><th>日期</th><th>最优选</th><th>评分</th><th>买入价</th><th>当天%</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th><th>5日最高</th><th>大盘</th></tr></thead><tbody>'
   306|   306|
   307|   307|for dt, c in vl:
   308|   308|    dly = c.get("daily",[]); b5 = None; dcells = ""
   309|   309|    for di in range(5):
   310|   310|        if di < len(dly):
   311|   311|            dh = dly[di].get("high"); dc = dly[di].get("close")
   312|   312|            if isinstance(dh,(int,float)) and (b5 is None or dh > b5): b5 = dh
   313|   313|            hs = f"{dh:+.1f}%" if isinstance(dh,(int,float)) else "—"
   314|   314|            cs = f"{dc:+.1f}%" if isinstance(dc,(int,float)) else "—"
   315|   315|            hc = "up" if isinstance(dh,(int,float)) and dh>=0 else ("down" if isinstance(dh,(int,float)) else "")
   316|   316|            cc = "up" if isinstance(dc,(int,float)) and dc>=0 else ("down" if isinstance(dc,(int,float)) else "")
   317|   317|            dcells += f'<td class="num">{hs}<br><span class="{cc} fs">{cs}</span></td>'
   318|   318|        else:
   319|   319|            dcells += '<td class="num na">—</td>'
   320|   320|    b5v = b5 if b5 is not None else c.get("max5")
   321|   321|    b5s = f"{b5v:+.1f}%" if isinstance(b5v,(int,float)) else "—"
   322|   322|    b5c = "up" if isinstance(b5v,(int,float)) and b5v>=5 else ("warn" if isinstance(b5v,(int,float)) and b5v>=2 else "")
   323|   323|    ip = c.get("index_pct")
   324|   324|    ips = f"{ip:+.2f}%" if ip is not None else "—"
   325|   325|    ipc = "up" if ip is not None and ip>=0 else ("down" if ip is not None else "")
   326|   326|    pc = "up" if c.get("pct_d",0) > 0 else "down"
   327|   327|    h += f'<tr><td>{dt}</td><td><strong>{c["name"]}</strong><span class="code">{c["code"]}</span></td>'
   328|   328|    h += f'<td class="num" style="color:#58a6ff;font-weight:700">{c["qscore"]}</td>'
   329|   329|    h += f'<td class="num">{c.get("kl_close",0):.2f}</td><td class="num {pc}">{c.get("pct_d",0):+.2f}%</td>'
   330|   330|    h += dcells
   331|   331|    h += f'<td class="num {b5c}"><strong>{b5s}</strong></td><td class="num {ipc}">{ips}</td></tr>'
   332|   332|
   333|   333|h += '</tbody></table></div></div>'
   334|   334|
   335|   335|# 近5日
   336|   336|h += '<div class="st">📊 近5日Top5</div>'
   337|   337|for dt in l5:
   338|   338|    t = top5.get(dt,[]); c = champ.get(dt,{})
   339|   339|    if not t: continue
   340|   340|    h += f'<div class="card"><div class="dc"><div class="dt">📅 {dt}</div><div class="sw"><table style="min-width:300px"><thead><tr><th>#</th><th>名称</th><th>评分</th><th>买入价</th><th>当天%</th><th>5日最高</th></tr></thead><tbody>'
   341|   341|    for r in t:
   342|   342|        m5s = f"{r['max5']:+.1f}%" if r['max5'] is not None else "—"
   343|   343|        m5c = "up" if r['max5'] is not None and r['max5']>=5 else ("warn" if r['max5'] is not None and r['max5']>=2 else "")
   344|   344|        pc = "up" if r['pct']>0 else "down"
   345|   345|        h += f'<tr><td>{r["rank"]}</td><td><strong>{r["name"]}</strong><span class="code">{r["code"]}</span></td>'
   346|   346|        h += f'<td class="num" style="color:#58a6ff">{r["score"]}</td><td class="num">{r["price"]:.2f}</td>'
   347|   347|        h += f'<td class="num {pc}">{r["pct"]:+.2f}%</td><td class="num {m5c}"><strong>{m5s}</strong></td></tr>'
   348|   348|    h += '</tbody></table></div>'
   349|   349|    if c and c.get("daily"):
   350|   350|        h += f'<div style="margin-top:4px;font-size:8px;color:#d29922">🏆 {c["name"]} D+1~D+5:'
   351|   351|        for di,dd in enumerate(c["daily"]):
   352|   352|            hc_ = "up" if dd["high"]>=0 else "down"; cc_ = "up" if dd["close"]>=0 else "down"
   353|   353|            h += f' D+{di+1}<span class="{hc_}">{dd["high"]:+.1f}%</span>/<span class="{cc_}">{dd["close"]:+.1f}%</span>'
   354|   354|        h += '</div>'
   355|   355|    h += '</div></div>'
   356|   356|
   357|   357|h += f'<div class="ft">CG-05 参数寻优版 · {datetime.now().strftime("%Y-%m-%d %H:%M")}</div></div></body></html>'
   358|   358|
   359|   359|# ═══ 发送 ═══
   360|   360|rcp = ["1254628314@qq.com"]
   361|   361|print(f"\n📧 发送到 {', '.join(rcp)}...")
   362|   362|send_email(rcp, f"🐉 CG-05 2025全年冠军表 {datetime.now().strftime('%Y-%m-%d')}", h, html=True)
   363|   363|print("✅ 完成!")
   364|   364|
   365|   365|# 控制台也打印
   366|   366|print(f"\n{'='*80}")
   367|   367|print(f"  🐉 CG-05 3月~5月 ({len(tds)}天) 出票{len(vl)}天")
   368|   368|print(f"  达标10%+: {h10}/{tt}天({h10r}%) | 达标5%+: {h5}/{tt}天({h5r}%) | 均最高+{avs}%")
   369|   369|print(f"{'='*80}")
   370|   370|print(f"{'日期':<12}{'最优选':<12}{'评分':>4}{'买入价':>8}{'当天%':>7}  {'D+1':>10}{'D+2':>10}{'D+3':>10}{'D+4':>10}{'D+5':>10}{'5日最高':>8}")
   371|   371|for dt, c in vl:
   372|   372|    dly = c.get("daily",[]); b5 = None
   373|   373|    line = f"{dt:<12}{c['name']:<12}{c['qscore']:>4}{c.get('kl_close',0):>8.2f}{c.get('pct_d',0):>+6.2f}% "
   374|   374|    for di in range(5):
   375|   375|        if di < len(dly):
   376|   376|            dh = dly[di].get("high"); dc = dly[di].get("close")
   377|   377|            if isinstance(dh,(int,float)) and (b5 is None or dh>b5): b5 = dh
   378|   378|            line += f"{dh:>+5.1f}/{dc:>+4.1f} " if isinstance(dh,(int,float)) else f"  {'—':>5}/{'—':>4} "
   379|   379|        else:
   380|   380|            line += f"  {'—':>5}/{'—':>4} "
   381|   381|    b5v = b5 if b5 is not None else c.get("max5")
   382|   382|    line += f"{b5v:>+8.1f}%" if isinstance(b5v,(int,float)) else f"{'—':>8}"
   383|   383|    print(line)
   384|   384|