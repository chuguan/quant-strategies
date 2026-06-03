     1|     1|#!/usr/bin/env python3
     2|     2|"""CG-05 2024全年回测+冠军表+邮件"""
     3|     3|import json, os, sys, time, subprocess, requests
     4|     4|sys.path.insert(0, os.path.dirname(__file__))
     5|     5|from send_email import send_email
     6|     6|from datetime import datetime
     7|     7|
     8|     8|YEAR = "2024"
     9|     9|CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
    10|    10|
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
    31|    31|        if dif[i] is not None and dea[i] is not None: macd[i] = dif[i] - dea[i]
    32|    32|    return dif, dea, macd
    33|    33|
    34|    34|def kdj_calc(highs, lows, closes, n=9):
    35|    35|    L = len(closes)
    36|    36|    if L < n: return None, None, None
    37|    37|    k = [50.0]*L; d = [50.0]*L; j = [50.0]*L
    38|    38|    for i in range(n-1, L):
    39|    39|        hh = max(highs[i-n+1:i+1]); ll = min(lows[i-n+1:i+1])
    40|    40|        rsv = 50.0 if hh == ll else (closes[i]-ll)/(hh-ll)*100
    41|    41|        if i == n-1: k[i] = 50.0
    42|    42|        else: k[i] = 2/3*k[i-1] + 1/3*rsv
    43|    43|        d[i] = 2/3*d[i-1] + 1/3*k[i]
    44|    44|        j[i] = 3*k[i] - 2*d[i]
    45|    45|    return k, d, j
    46|    46|
    47|    47|P = {"pct_lower": 4, "pct_upper": 5, "ma5_slope_min": 10, "close_pos_min": 50, "vr_max": 2.5, "j_ratio_min": 15}
    48|    48|
    49|    49|print(f"📡 加载数据 ({YEAR})...")
    50|    50|all_data = {}
    51|    51|for fn in os.listdir(CACHE_DIR):
    52|    52|    if not fn.endswith('.json'): continue
    53|    53|    if not (fn.startswith('sh6') or fn.startswith('sz0')): continue
    54|    54|    try:
    55|    55|        with open(os.path.join(CACHE_DIR, fn), 'rb') as f:
    56|    56|            recs = json.loads(f.read().decode('utf-8'))
    57|    57|        if not isinstance(recs, list) or len(recs) < 80: continue
    58|    58|        cd = fn.replace('.json','').replace('sh','').replace('sz','')
    59|    59|        cp = [r["close"] for r in recs]; hp = [r["high"] for r in recs]
    60|    60|        lp = [r["low"] for r in recs]; vv = [r["volume"] for r in recs]
    61|    61|        op = [r.get("open", r["close"]) for r in recs]; ds = [r["date"] for r in recs]
    62|    62|        pct = [0.0]
    63|    63|        for i in range(1, len(cp)): pct.append((cp[i]/cp[i-1]-1)*100)
    64|    64|        ma5=ma(cp,5); ma10=ma(cp,10); ma20=ma(cp,20); ma60=ma(cp,60)
    65|    65|        v5=ma(vv,5); dif,dea,macd=macd_full(cp); k_,d_,j_=kdj_calc(hp,lp,cp)
    66|    66|        di_={ds[i]:i for i in range(len(ds))}
    67|    67|        all_data[cd]={"p":cp,"h":hp,"l":lp,"v":vv,"o":op,"pct":pct,"ds":ds,"di":di_,
    68|    68|            "ma5":ma5,"ma10":ma10,"ma20":ma20,"ma60":ma60,"v5":v5,
    69|    69|            "dif":dif,"dea":dea,"macd":macd,"k":k_,"d":d_,"j":j_,"recs":recs}
    70|    70|    except: pass
    71|    71|print(f"  ✅ {len(all_data)} 只")
    72|    72|
    73|    73|tds = sorted(set(dt for sd in all_data.values() for dt in sd["ds"] if dt[:4] == YEAR))
    74|    74|print(f"  📅 {tds[0]} ~ {tds[-1]} 共{len(tds)}天")
    75|    75|
    76|    76|print("📡 预计算...")
    77|    77|fl = {}
    78|    78|for cd, sd in all_data.items():
    79|    79|    recs = sd["recs"]
    80|    80|    for i in range(len(recs)-5):
    81|    81|        dt = recs[i]["date"]
    82|    82|        if dt[:4] != YEAR: continue
    83|    83|        buy = recs[i]["close"]
    84|    84|        if buy <= 0: continue
    85|    85|        after = recs[i+1:i+6]
    86|    86|        if not after: continue
    87|    87|        m5 = round((max(x["high"] for x in after)/buy-1)*100, 1)
    88|    88|        dd = []; prev = buy
    89|    89|        for x in after:
    90|    90|            dh = round((x["high"]/buy-1)*100, 1)
    91|    91|            dc = round((x["close"]/buy-1)*100, 1)
    92|    92|            arr = "↑" if x["close"] > prev else ("↓" if x["close"] < prev else "→")
    93|    93|            dd.append({"high":dh,"close":dc,"arrow":arr,"date":x["date"]})
    94|    94|            prev = x["close"]
    95|    95|        fl[(cd,dt)] = {"max5":m5,"daily":dd}
    96|    96|print(f"  ✅ {len(fl)} 条")
    97|    97|
    98|    98|print("📡 大盘...")
    99|    99|idx = {}
   100|   100|try:
   101|   101|    r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,500,qfq",
   102|   102|                     headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
   103|   103|    d = r.json()
   104|   104|    sd = d.get('data',{}).get('sh000001',{})
   105|   105|    k = sd.get('qfqday',[])
   106|   106|    if not k:
   107|   107|        for key in sd:
   108|   108|            if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list): k=sd[key]; break
   109|   109|    prev = None
   110|   110|    for x in k:
   111|   111|        dt = x[0]; close = float(x[2])
   112|   112|        if dt[:4] == YEAR:
   113|   113|            if prev: idx[dt] = round((close/prev-1)*100, 2)
   114|   114|            else: idx[dt] = 0.0
   115|   115|        prev = close
   116|   116|except: pass
   117|   117|
   118|   118|print(f"🚀 回测 {len(tds)}天...")
   119|   119|champ = {}; top5 = {}
   120|   120|
   121|   121|for td in tds:
   122|   122|    res = []
   123|   123|    for cd, sd in all_data.items():
   124|   124|        di = sd["di"].get(td)
   125|   125|        if di is None or di < 80: continue
   126|   126|        p=sd["p"]; h=sd["h"]; l=sd["l"]; v=sd["v"]; o=sd["o"]; pct=sd["pct"]
   127|   127|        m5=sd["ma5"]; m10=sd["ma10"]; m20=sd["ma20"]; m60=sd["ma60"]
   128|   128|        v5=sd["v5"]; dif=sd["dif"]; dea=sd["dea"]; macd=sd["macd"]
   129|   129|        k=sd["k"]; d=sd["d"]; j=sd["j"]
   130|   130|        
   131|   131|        cur = p[di]
   132|   132|        if cur > 80: continue
   133|   133|        if cur <= o[di] or (cur-o[di])/o[di]*100 < 1: continue
   134|   134|        if v5[di] and v[di]/v5[di] > P["vr_max"]: continue
   135|   135|        if (h[di]-l[di]) > 0 and (cur-l[di])/(h[di]-l[di])*100 < P["close_pos_min"]: continue
   136|   136|        if not (m60[di] and m60[di] > 0): continue
   137|   137|        if not (dif[di] and dea[di] and dif[di] > dea[di]): continue
   138|   138|        if not (macd[di] and macd[di] > 0): continue
   139|   139|        if dif[di]-dea[di] < 0.1: continue
   140|   140|        if macd[di-1] is not None and macd[di] <= macd[di-1]: continue
   141|   141|        if macd[di-1] is not None and macd[di-2] is not None:
   142|   142|            if macd[di]-macd[di-1] < macd[di-1]-macd[di-2]: continue
   143|   143|        if dif[di-3] is not None and dif[di] <= dif[di-3]: continue
   144|   144|        
   145|   145|        js = j[di]-j[di-1] if (j[di-1] is not None and j[di] is not None) else 0
   146|   146|        dp = d[di-1] if d[di-1] is not None and d[di-1] != 0 else 1
   147|   147|        jr = js/dp*100
   148|   148|        kg = (j[di]>k[di]>d[di]) or (j[di]>k[di] and k[di]<=d[di])
   149|   149|        if j[di-1] is not None and k[di-1] is not None and j[di-1]<=k[di-1] and j[di]>k[di]: kg = True
   150|   150|        if not (jr > P["j_ratio_min"] or kg): continue
   151|   151|        if k[di] > 80 and j[di] > 90: continue
   152|   152|        if k[di] < 20: continue
   153|   153|        if not (m5[di] and m5[di-3] and m5[di] > m5[di-3]): continue
   154|   154|        if not (m20[di] and m20[di-5] and m20[di] > m20[di-5]): continue
   155|   155|        if not (m5[di] and m10[di] and m20[di] and m5[di] > m10[di] > m20[di]): continue
   156|   156|        if not (m5[di] and cur > m5[di]): continue
   157|   157|        if m5[di] and m5[di-5] and m5[di-5] > 0:
   158|   158|            sl = (m5[di]-m5[di-5])/m5[di-5]*100
   159|   159|            if sl <= P["ma5_slope_min"]: continue
   160|   160|        else: continue
   161|   161|        gap = m10[di]-m20[di] if (m10[di] and m20[di]) else 0
   162|   162|        gb = m10[di-4]-m20[di-4] if (m10[di-4] and m20[di-4]) else 0
   163|   163|        if gap <= gb*0.8: continue
   164|   164|        if not (P["pct_lower"] < pct[di] < P["pct_upper"]): continue
   165|   165|        
   166|   166|        sc = 0
   167|   167|        mr = dif[di]/cur*100 if cur > 0 else 0
   168|   168|        if mr > 5: sc += 25
   169|   169|        elif mr > 2: sc += 20
   170|   170|        elif mr > 1: sc += 12
   171|   171|        elif mr > 0: sc += 5
   172|   172|        vr = v[di]/v5[di] if v5[di] else 0
   173|   173|        if pct[di] > 7: sc += 30
   174|   174|        elif pct[di] > 5: sc += 25
   175|   175|        elif pct[di] > 3: sc += 15
   176|   176|        elif pct[di] > 0: sc += 8
   177|   177|        if vr > 2: sc += 15
   178|   178|        elif vr > 1.2: sc += 10
   179|   179|        elif vr > 0.7: sc += 5
   180|   180|        if m5[di] and cur > m5[di]: sc += 12
   181|   181|        if len(p) >= 120 and di >= 120:
   182|   182|            bh = max(h[di-60:di-1]); bl = min(l[di-60:di-1])
   183|   183|            rl = min(p[di-120:di]); rh = max(p[di-120:di])
   184|   184|            pos = ((bh+bl)/2 - rl)/(rh - rl)*100 if (rh-rl) > 0 else 50
   185|   185|        else: pos = 50
   186|   186|        if pos < 30: sc += 15
   187|   187|        elif pos < 50: sc += 8
   188|   188|        elif pos > 60: sc -= 5
   189|   189|        s5 = sum(pct[di-4:di+1]) if di >= 5 else 0
   190|   190|        if s5 > 5: sc += 8
   191|   191|        if 5 < cur < 35: sc += 5
   192|   192|        gc = sum(1 for i in range(max(0,di-5), di-1) if pct[i] > 0)
   193|   193|        if gc >= 3: sc += 5
   194|   194|        if pct[di] > 4.5: sc -= 8
   195|   195|        if di >= 1 and pct[di-1] > 3: sc -= 5
   196|   196|        if di >= 2 and pct[di-2] > 3: sc -= 5
   197|   197|        sh = h[di] - max(o[di], cur); tr = h[di]-l[di]
   198|   198|        if tr > 0 and sh > 0:
   199|   199|            sr = sh/tr*100
   200|   200|            if sr > 50: sc -= 5
   201|   201|            elif sr > 30: sc -= 3
   202|   202|            elif sr > 15: sc -= 1
   203|   203|        
   204|   204|        fp = fl.get((cd, td))
   205|   205|        res.append({"code":cd,"name":"?","score":sc,"price":cur,"pct_d":pct[di],
   206|   206|            "max5":fp["max5"] if fp else None,"daily":fp["daily"] if fp else []})
   207|   207|    
   208|   208|    if not res:
   209|   209|        champ[td] = None
   210|   210|        continue
   211|   211|    
   212|   212|    res.sort(key=lambda x: -x["score"])
   213|   213|    c = res[0]
   214|   214|    champ[td] = {"name":"?","code":c["code"],"qscore":c["score"],
   215|   215|        "kl_close":c["price"],"pct_d":c["pct_d"],
   216|   216|        "max5":c["max5"],"daily":c["daily"],"index_pct":idx.get(td)}
   217|   217|    top5[td] = [{"rank":i+1,"name":"?","code":r["code"],"score":r["score"],
   218|   218|        "price":round(r["price"],2),"pct":r["pct_d"],"max5":r["max5"],
   219|   219|        "daily":r["daily"] if i==0 else []} for i,r in enumerate(res[:5])]
   220|   220|
   221|   221|print("📡 获取股票名称...")
   222|   222|cc = set()
   223|   223|for dt,c in champ.items():
   224|   224|    if c: cc.add(c["code"])
   225|   225|for dt,t in top5.items():
   226|   226|    for r in t: cc.add(r["code"])
   227|   227|nm = {}
   228|   228|for c in sorted(cc):
   229|   229|    try:
   230|   230|        mk = "sh" if int(c) >= 600000 else "sz"
   231|   231|        tx = subprocess.run(['curl','-s','-m','5',f'https://qt.gtimg.cn/q={mk}{c}'],
   232|   232|                          capture_output=True,timeout=8).stdout.decode('gbk',errors='replace')
   233|   233|        pts = tx.split("~"); nm[c] = pts[1] if len(pts) > 1 else c
   234|   234|    except: nm[c] = c
   235|   235|for dt,c in champ.items():
   236|   236|    if c and c["code"] in nm: c["name"] = nm[c["code"]]
   237|   237|for dt,t in top5.items():
   238|   238|    for r in t:
   239|   239|        if r["code"] in nm: r["name"] = nm[r["code"]]
   240|   240|
   241|   241|vl = [(k,v) for k,v in sorted(champ.items(), reverse=True) if v is not None]
   242|   242|h10 = sum(1 for _,c in vl if isinstance(c.get("max5"),(int,float)) and c["max5"]>=10)
   243|   243|h5 = sum(1 for _,c in vl if isinstance(c.get("max5"),(int,float)) and c["max5"]>=5)
   244|   244|tt = sum(1 for _,c in vl if isinstance(c.get("max5"),(int,float)))
   245|   245|av = sum(c["max5"] for _,c in vl if isinstance(c.get("max5"),(int,float)))
   246|   246|avs = f"{av/tt:.1f}" if tt else "0"
   247|   247|h10r = f"{h10/tt*100:.0f}" if tt else "0"
   248|   248|l5 = sorted(top5.keys(), reverse=True)[:5]
   249|   249|
   250|   250|h = f"""<!DOCTYPE html>
   251|   251|<html lang="zh-CN">
   252|   252|<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
   253|   253|<style>
   254|   254|*{{margin:0;padding:0;box-sizing:border-box}}
   255|   255|body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:10px}}
   256|   256|.container{{max-width:680px;margin:0 auto}}
   257|   257|.header{{background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:12px;padding:14px;margin-bottom:10px;border:1px solid #30363d;text-align:center}}
   258|   258|.header h1{{font-size:17px;color:#58a6ff}}
   259|   259|.header .sub{{font-size:9px;color:#8b949e;margin-top:2px}}
   260|   260|.stats{{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap;justify-content:center}}
   261|   261|.sb{{flex:1;min-width:60px;max-width:90px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:6px 4px;text-align:center}}
   262|   262|.sb .n{{font-size:15px;font-weight:700}}
   263|   263|.sb .l{{font-size:7px;color:#8b949e;margin-top:1px}}
   264|   264|.sb.g .n{{color:#f85149}} .sb.b .n{{color:#58a6ff}} .sb.o .n{{color:#d29922}}
   265|   265|.st{{font-size:12px;font-weight:700;padding:6px 2px 2px}}
   266|   266|.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;margin-bottom:8px;overflow-x:auto}}
   267|   267|.sw{{overflow-x:auto}}
   268|   268|table{{width:100%;border-collapse:collapse;font-size:9px;min-width:620px}}
   269|   269|th{{background:#1c2128;padding:3px 2px;text-align:center;font-weight:500;color:#8b949e;font-size:7px;border-bottom:1px solid #30363d}}
   270|   270|td{{padding:3px 2px;text-align:center;border-bottom:1px solid #21262d;font-family:"Consolas",monospace;font-size:8px}}
   271|   271|.num{{font-family:"Consolas",monospace;text-align:center}}
   272|   272|.up{{color:#f85149}} .down{{color:#3fb950}} .warn{{color:#d29922}}
   273|   273|.code{{color:#8b949e;font-size:7px}}
   274|   274|.ft{{text-align:center;color:#484f58;font-size:7px;padding:6px 0}}
   275|   275|.dc{{padding:6px 8px}}
   276|   276|.dt{{font-size:10px;font-weight:700;margin-bottom:4px}}
   277|   277|.fs{{font-size:7px}}
   278|   278|.na{{color:#484f58}}
   279|   279|</style></head><body>
   280|   280|<div class="container">
   281|   281|<div class="header">
   282|   282|<h1>🐉 CG-05 {YEAR}全年冠军表</h1>
   283|   283|<div class="sub">{tds[0]} ~ {tds[-1]} | 涨4~5% MA5≥10% 位≥50% 量≤2.5 J≥15%</div>
   284|   284|</div>
   285|   285|<div class="stats">
   286|   286|<div class="sb g"><div class="n">{avs}%</div><div class="l">均最高</div></div>
   287|   287|<div class="sb b"><div class="n">{h10r}%</div><div class="l">达标10%+</div></div>
   288|   288|<div class="sb o"><div class="n">{len(vl)}天</div><div class="l">出票</div></div>
   289|   289|</div>"""
   290|   290|
   291|   291|h += '<div class="st">📋 全期冠军表</div><div class="card"><div class="sw"><table>'
   292|   292|h += '<thead><tr><th>日期</th><th>最优选</th><th>评分</th><th>买入价</th><th>当天%</th><th>D+1</th><th>D+2</th><th>D+3</th><th>D+4</th><th>D+5</th><th>5日最高</th><th>大盘</th></tr></thead><tbody>'
   293|   293|
   294|   294|for dt, c in vl:
   295|   295|    dly = c.get("daily",[]); b5 = None; dcells = ""
   296|   296|    for di in range(5):
   297|   297|        if di < len(dly):
   298|   298|            dh = dly[di].get("high"); dc = dly[di].get("close")
   299|   299|            if isinstance(dh,(int,float)) and (b5 is None or dh > b5): b5 = dh
   300|   300|            hs = f"{dh:+.1f}%" if isinstance(dh,(int,float)) else "—"
   301|   301|            cs = f"{dc:+.1f}%" if isinstance(dc,(int,float)) else "—"
   302|   302|            hc = "up" if isinstance(dh,(int,float)) and dh>=0 else ("down" if isinstance(dh,(int,float)) else "")
   303|   303|            cc = "up" if isinstance(dc,(int,float)) and dc>=0 else ("down" if isinstance(dc,(int,float)) else "")
   304|   304|            dcells += f'<td class="num">{hs}<br><span class="{cc} fs">{cs}</span></td>'
   305|   305|        else:
   306|   306|            dcells += '<td class="num na">—</td>'
   307|   307|    b5v = b5 if b5 is not None else c.get("max5")
   308|   308|    b5s = f"{b5v:+.1f}%" if isinstance(b5v,(int,float)) else "—"
   309|   309|    b5c = "up" if isinstance(b5v,(int,float)) and b5v>=5 else ("warn" if isinstance(b5v,(int,float)) and b5v>=2 else "")
   310|   310|    ip = c.get("index_pct")
   311|   311|    ips = f"{ip:+.2f}%" if ip is not None else "—"
   312|   312|    ipc = "up" if ip is not None and ip>=0 else ("down" if ip is not None else "")
   313|   313|    pc = "up" if c.get("pct_d",0) > 0 else "down"
   314|   314|    h += f'<tr><td>{dt}</td><td><strong>{c["name"]}</strong><span class="code">{c["code"]}</span></td>'
   315|   315|    h += f'<td class="num" style="color:#58a6ff;font-weight:700">{c["qscore"]}</td>'
   316|   316|    h += f'<td class="num">{c.get("kl_close",0):.2f}</td><td class="num {pc}">{c.get("pct_d",0):+.2f}%</td>'
   317|   317|    h += dcells
   318|   318|    h += f'<td class="num {b5c}"><strong>{b5s}</strong></td><td class="num {ipc}">{ips}</td></tr>'
   319|   319|
   320|   320|h += '</tbody></table></div></div>'
   321|   321|
   322|   322|h += '<div class="st">📊 近5日Top5</div>'
   323|   323|for dt in l5:
   324|   324|    t = top5.get(dt,[]); c = champ.get(dt,{})
   325|   325|    if not t: continue
   326|   326|    h += f'<div class="card"><div class="dc"><div class="dt">📅 {dt}</div><div class="sw"><table style="min-width:300px"><thead><tr><th>#</th><th>名称</th><th>评分</th><th>买入价</th><th>当天%</th><th>5日最高</th></tr></thead><tbody>'
   327|   327|    for r in t:
   328|   328|        m5s = f"{r['max5']:+.1f}%" if r['max5'] is not None else "—"
   329|   329|        m5c = "up" if r['max5'] is not None and r['max5']>=5 else ("warn" if r['max5'] is not None and r['max5']>=2 else "")
   330|   330|        pc = "up" if r['pct']>0 else "down"
   331|   331|        h += f'<tr><td>{r["rank"]}</td><td><strong>{r["name"]}</strong><span class="code">{r["code"]}</span></td>'
   332|   332|        h += f'<td class="num" style="color:#58a6ff">{r["score"]}</td><td class="num">{r["price"]:.2f}</td>'
   333|   333|        h += f'<td class="num {pc}">{r["pct"]:+.2f}%</td><td class="num {m5c}"><strong>{m5s}</strong></td></tr>'
   334|   334|    h += '</tbody></table></div>'
   335|   335|    if c and c.get("daily"):
   336|   336|        h += f'<div style="margin-top:4px;font-size:8px;color:#d29922">🏆 {c["name"]} D+1~D+5:'
   337|   337|        for di,dd in enumerate(c["daily"]):
   338|   338|            hc_ = "up" if dd["high"]>=0 else "down"; cc_ = "up" if dd["close"]>=0 else "down"
   339|   339|            h += f' D+{di+1}<span class="{hc_}">{dd["high"]:+.1f}%</span>/<span class="{cc_}">{dd["close"]:+.1f}%</span>'
   340|   340|        h += '</div>'
   341|   341|    h += '</div></div>'
   342|   342|
   343|   343|h += f'<div class="ft">CG-05 · {datetime.now().strftime("%Y-%m-%d %H:%M")}</div></div></body></html>'
   344|   344|
   345|   345|rcp = ["1254628314@qq.com"]
   346|   346|print(f"\n📧 发送到 {', '.join(rcp)}...")
   347|   347|send_email(rcp, f"🐉 CG-05 {YEAR}全年冠军表 {datetime.now().strftime('%Y-%m-%d')}", h, html=True)
   348|   348|print("✅ 完成!")
   349|   349|
   350|   350|print(f"\n{'='*80}")
   351|   351|print(f"  🐉 CG-05 {YEAR} ({len(tds)}天) 出票{len(vl)}天")
   352|   352|print(f"  达标10%+: {h10}/{tt}天({h10r}%) | 达标5%+: {h5}/{tt}天({h5/tt*100:.0f}% if tt else 0) | 均最高+{avs}%")
   353|   353|print(f"{'='*80}")
   354|   354|