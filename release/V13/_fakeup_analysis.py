"""分析V13虚涨日全量失败案例"""
import pickle, os, sys, importlib
sys.path.insert(0, ".")

with open("big_cache_full.pkl", "rb") as f:
    d = pickle.load(f)
data, real, names = d["data"], d["real"], d["names"]
with open("features_30d.pkl", "rb") as f:
    precomputed = pickle.load(f)

def mkt_class(stocks):
    if not stocks: return "flat"
    ps = [s.get("p",0) or 0 for s in stocks]
    vrs = [s.get("vol_ratio",0) or 0 for s in stocks if s.get("vol_ratio",0)]
    ap = sum(ps)/len(ps); av = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return "fake_up" if hot<15 or av<0.9 else "real_up"
    if ap<-0.5: return "down"
    return "flat"

def load_mod(name):
    fp = os.path.join(".", "评分策略", f"分而治之_V10_{name}_评分策略.py")
    spec = importlib.util.spec_from_file_location("m", fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

STRATS = {}
for n in ["真实涨日", "虚涨日", "跌日", "横盘"]:
    STRATS[n] = load_mod(n)
MK_MAP = {"real_up":"真实涨日","fake_up":"虚涨日","down":"跌日","flat":"横盘"}
LO = ["L0","L1","L2","L3","L4"]

def is_momentum_exhausted(s, code, dt):
    feats = precomputed.get((code, dt), {})
    if not feats: return False
    sl5 = feats.get("slope5",0); t4s = feats.get("t4_shadow",0)
    cu = feats.get("cons_up",0); pk = feats.get("peak_decay",0); pv = s.get("p",0) or 0
    if sl5>8 and t4s>25: return True
    if sl5>10 and t4s>18: return True
    if cu>=5 and sl5>15: return True
    if pk>5 and sl5>5 and pv<6: return True
    if sl5>5 and t4s>30: return True
    if cu>=4 and sl5>10 and pv<7: return True
    return False

def get_feats(code, dt):
    return precomputed.get((code, dt), {})

def compute_7day_decay_penalty(code, dt, p_today):
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt)
    prev = all_dates[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s["code"] == code:
                gains.append(s.get("p",0) or 0)
                found = True; break
        if not found: gains.append(0)
    gains.append(p_today)
    n = len(gains)
    if n < 5: return 0
    d6,d5,d4,d3,d2,d1,p = gains[-7:] if n>=7 else [0]*(7-n) + gains
    p_is_max = p >= max(gains[:-1]) if len(gains) > 1 else True
    avg_7d = sum(gains)/n
    wrv = 50
    for s in data.get(dt, []):
        if s["code"] == code: wrv = s.get("wr_val",50) or s.get("wrv",50); break
    penalty = 0
    if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty -= 8
    if p_is_max and avg_7d<0.8 and p<8:
        if avg_7d<0: penalty -= 15
        elif avg_7d<0.3: penalty -= 12
        elif avg_7d<0.7: penalty -= 8
        else: penalty -= 5
    if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty -= 8
    if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty -= 10
    if n>=5 and d5>d1 and d5>d2 and p<=d5:
        recent_sum = (d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
        if recent_sum<=2: penalty -= 8
    if n>=5:
        last5 = gains[-5:]
        if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty -= 10
    return penalty

def v10_score(s, code, dt, mk_cn):
    mod = STRATS[mk_cn]
    stock = {}
    stock["p"] = s.get("p",0) or 0
    stock["cl"] = s.get("cl",50)
    stock["vr"] = s.get("vol_ratio",1) or s.get("vr",1)
    stock["dif"] = s.get("dif_val",0) or s.get("dif",0)
    stock["mg"] = s.get("macd_golden",0) or s.get("mg",0)
    stock["wrv"] = s.get("wr_val",0) or s.get("wrv",50)
    stock["jv"] = s.get("j_val",0) or s.get("jv",50)
    stock["kv"] = s.get("k_val",0) or s.get("kv",50)
    stock["dv"] = s.get("d_val",0) or s.get("dv",50)
    stock["a5"] = s.get("above_ma5",0)
    stock["kdj_g"] = s.get("kdj_golden",0) or s.get("kdj_g",0)
    stock["pos_in_day"] = s.get("pos_in_day",50)
    stock["nm"] = s.get("nm","") or s.get("name","") or names.get(s["code"],"")
    ri = real.get(s["code"],{})
    stock["hsl"] = ri.get("hsl",0) or 0
    feats = get_feats(code, dt)
    stock["t4_shadow"] = feats.get("t4_shadow",0)
    stock["slope5"] = feats.get("slope5",0)
    stock["cons_up"] = feats.get("cons_up",0)
    stock["d1"] = feats.get("d1",0)
    stock["d2"] = feats.get("d2",0)
    stock["d3"] = feats.get("d3",0)
    penalty = compute_7day_decay_penalty(code, dt, s.get("p",0) or 0)
    return round(mod.score(stock) + penalty, 1)

# 100天回测 - 仅虚涨日
dates = sorted(k for k in data.keys() if "2026-01-01" <= k <= "2026-05-28")
fake_results = []
skipped_no_feats = 0

# 先看虚涨日大盘特征
print("="*60)
print("虚涨日大盘特征分析")
print("="*60)
fake_up_dates = []
for dt in dates:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p",0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss)
    if mk == "fake_up":
        hot = sum(1 for s in ss if 5<=(s.get("p",0) or 0)<=8)
        avg_vr = sum((s.get("vol_ratio",0) or 0) for s in ss if s.get("vol_ratio",0)) / max(sum(1 for s in ss if s.get("vol_ratio",0)),1)
        fake_up_dates.append((dt, hot, round(avg_vr,2)))

print(f"共{len(fake_up_dates)}天虚涨日")
# 统计原因分布
vr_low = sum(1 for _,_,avr in fake_up_dates if avr<0.9)
hot_low = sum(1 for _,hot,_ in fake_up_dates if hot<15)
# can overlap
print(f"  原因是量比低: {vr_low}天")
print(f"  原因是热点少: {hot_low}天")

print()
print("="*60)
print("虚涨日V13#1逐日明细")
print("="*60)

for dt in dates:
    ss = data.get(dt, [])
    ss = [s for s in ss if (s.get("p",0) or 0) < 15]
    if not ss: continue
    mk = mkt_class(ss)
    if mk != "fake_up": continue
    mk_cn = "虚涨日"
    mod = STRATS[mk_cn]; LEVELS = mod.LEVELS
    lm = {l["name"]: i for i, l in enumerate(LEVELS)}
    pool = None; eliminated = 0
    for ln in LO:
        if ln not in lm: continue
        i = lm[ln]; lv = LEVELS[i]; cand = []
        for s in ss:
            p = s.get("p",0) or 0
            if p < lv["p_min"] or p > min(lv.get("p_max",10), 8): continue
            vr = s.get("vol_ratio",0) or 0
            if vr < lv["vr_min"] or vr > lv["vr_max"]: continue
            ri = real.get(s["code"],{}); hsl = ri.get("hsl",0) or 0
            if hsl < lv.get("hs_min",0) or hsl > lv.get("hs_max",99): continue
            if (ri.get("shizhi",0) or 0) >= lv.get("sz_max",9999): continue
            nm = names.get(s["code"],"")
            if "ST" in nm or "*ST" in nm or "退" in nm: continue
            cl = s.get("cl",0)
            if cl < lv.get("cl_min",0) or cl > lv.get("cl_max",100): continue
            if is_momentum_exhausted(s, s["code"], dt): eliminated += 1; continue
            cand.append(s)
        if len(cand) >= 10: pool = cand; break
    if not pool: continue
    
    scored = [(v10_score(s, s["code"], dt, mk_cn), s) for s in pool]
    scored.sort(key=lambda x: -x[0])
    champ = scored[0][1]; champ_sc = scored[0][0]
    nh = champ.get("n",0) or 0
    nm = names.get(champ["code"],"?")
    p = champ.get("p",0)
    code = champ["code"]
    feats = get_feats(code, dt)
    feats_ok = bool(feats)
    if not feats_ok: skipped_no_feats += 1
    wrv = champ.get("wr_val",50) or champ.get("wrv",50)
    vr = champ.get("vol_ratio",1) or champ.get("vr",1)
    cl_ = champ.get("cl",50)
    hsl = real.get(code,{}).get("hsl",0) or 0
    win = 1 if nh >= 2.5 else 0
    fake_results.append({
        "date":dt,"code":code,"name":nm,"p":p,"score":champ_sc,
        "nh":nh,"win":win,"wr":wrv,"vr":vr,"cl":cl_,"hsl":hsl,
        "feats_ok":feats_ok,"slope5":feats.get("slope5",0),
        "t4_shadow":feats.get("t4_shadow",0),
        "pool_size":len(pool),
    })

wins = [r for r in fake_results if r["win"]]
fails = [r for r in fake_results if not r["win"]]

# 表格
print(f"总: {len(wins)}/{len(fake_results)} = {len(wins)*100/len(fake_results):.1f}% (无特征={skipped_no_feats}天)")
print(f"{'日期':>12} {'代码':>8} {'名称':>10} {'p%':>5} {'评分':>7} {'nh%':>5} {'结果':>4} {'WR':>4} {'VR':>4} {'CL':>3} {'HSL':>5} {'池':>3}")
print("-"*80)
for r in fake_results:
    flag = "✅" if r["win"] else "❌"
    print(f'{r["date"]} {r["code"]:>8} {r["name"]:>10} {r["p"]:>5.1f} {r["score"]:>7.1f} {r["nh"]:>+5.1f} {flag} {r["wr"]:>4.0f} {r["vr"]:>4.2f} {r["cl"]:>3.0f} {r["hsl"]:>5.1f} {r["pool_size"]:>3}')

# 失败共性
print(f"\n{'='*60}")
print("失败共性统计")
print(f"{'='*60}")
if fails and wins:
    print(f"  失败天数: {len(fails)}")
    print(f"  成功天数: {len(wins)}")
    for feat_name, key in [("p%","p"),("WR","wr"),("VR","vr"),("CL","cl"),("HSL","hsl"),("池大小","pool_size")]:
        f_avg = round(sum(r[key] for r in fails)/len(fails),1)
        w_avg = round(sum(r[key] for r in wins)/len(wins),1)
        d = f_avg - w_avg
        arrow = "⬆" if d>0 else "⬇" if d<0 else "="
        print(f"  {feat_name:>5}: 失败={f_avg:>8}  成功={w_avg:>8}  差={d:>+7.1f}{arrow}")

# 分析评分分布
print(f"\n{'='*60}")
print("虚涨日评分剖析")
print(f"{'='*60}")
# 当前虚涨日评分公式: p*0.5 + cl*0.05 + macd_score*1 + dif_bonus(2)
# macd_score: if mg and dif>0.5:10, elif mg and dif>0.2:8, elif mg:6, elif dif>0.5:4, elif dif>0:2
# p*0.5 for p=4.7 => 2.35
# CL*0.05 for CL=80 => 4
# macd max=10, dif_bonus=2
# total estimate: ~2.35+4+10+2=18.35 but actual=14.4

# 看看平均评分
avg_sc = sum(r["score"] for r in fake_results)/len(fake_results)
print(f"  虚涨日平均评分: {avg_sc:.1f}")

# 对比其他行情
print(f"\n  【其他行情平均评分参考】")
for mk_n in ["真实涨日","跌日","横盘"]:
    mod = STRATS[mk_n]
    print(f"    {mk_n}: PARAMS={mod.PARAMS}")

# 看看失败日的7天序列
print(f"\n{'='*60}")
print("失败日7天涨幅序列")
print(f"{'='*60}")
for r in fails:
    code, dt = r["code"], r["date"]
    all_dates = sorted(data.keys())
    idx = all_dates.index(dt)
    prev = all_dates[max(0,idx-6):idx]
    gains = []
    for pd in prev:
        found = False
        for s in data[pd]:
            if s["code"] == code:
                gains.append(round(s.get("p",0) or 0,1))
                found = True; break
        if not found: gains.append(0)
    gains.append(round(r["p"],1))
    gs = " -> ".join(f"{x:+.1f}" for x in gains)
    penalty = compute_7day_decay_penalty(code, dt, r["p"])
    print(f'  {dt} {r["name"]}({code}) 评分={r["score"]:.1f} nh={r["nh"]:+.1f}% 扣分={penalty}')
    print(f'    7天: {gs}  avg={sum(gains)/len(gains):+.2f}')
