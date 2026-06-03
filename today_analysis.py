#!/usr/bin/env python3
"""今日选股详细分析 — 冠军为什么是冠军？落榜的为什么不行？"""
import json, os, time, sys
sys.stdout.reconfigure(line_buffering=True)
from collections import defaultdict

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
TODAY = "2026-05-24"

def calc_ma(s,p):
    n=len(s); r={}
    for pd in p:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r
def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n
    if n<26: return dif,dea
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    return dif,dea

print("📡 加载数据...")
t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and (f.startswith('sh6') or f.startswith('sz0') or f.startswith('sz2'))]
all_codes={}

for idx,fn in enumerate(all_files):
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<80: continue
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        mas=calc_ma(c,[5,10,20,60])
        dif,dea=calc_macd(c)
        pct=[0.0]
        for i in range(1,len(c)): pct.append((c[i]/c[i-1]-1)*100)
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        date_idx={r["date"]:idx for idx,r in enumerate(recs)}
        all_codes[code]={"c":c,"h":h,"l":l,"o":o,"v":v,"mas":mas,"dif":dif,"dea":dea,"pct":pct,"recs":recs,"atr":atr,"date_idx":date_idx}
    except: pass
print(f"✅ {len(all_codes)}只, {time.time()-t0:.0f}秒")

# ═══ 今日选股（带完整特征）═══
print(f"\n{'='*80}")
print(f"📅 {TODAY} CG-07 v14 选股分析")
print(f"{'='*80}")

di_check = TODAY
candidates_detail = []

for code, sd in all_codes.items():
    di = sd["date_idx"].get(di_check)
    if di is None or di < 80: continue
    
    cl=sd["c"][di]; op=sd["o"][di]; hi=sd["h"][di]; lo=sd["l"][di]
    m=sd["mas"]
    
    # 硬过滤 & 记录每个过滤条件
    filters = {}
    filters['价<80'] = cl < 80
    filters['均线多头'] = (m[5][di] and m[10][di] and m[20][di] and m[60][di] and
                          m[5][di] > m[10][di] > m[20][di] > m[60][di])
    filters['MACD零轴上'] = (sd["dif"][di] and sd["dea"][di] and 
                            sd["dif"][di] > 0 and sd["dif"][di] > sd["dea"][di])
    atr_v=sd["atr"][di]
    filters['ATR>3%'] = (atr_v and cl > 0 and atr_v/cl*100 > 3)
    filters['站MA60'] = (m[60][di] and cl > m[60][di])
    filters['阳线'] = cl > op
    filters['站MA5'] = (m[5][di] and cl > m[5][di])
    
    passed = all(filters.values())
    
    # 计算评分因子（不管过不过过滤都算）
    atr_pct = atr_v/cl*100 if atr_v and cl>0 else 0
    body_pct = abs(cl-op)/op*100 if op>0 else 0
    rng = hi-lo
    shadow_pct = (hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
    
    # v14评分各分量
    shadow_score = max(0, 35 - shadow_pct * 1.2) if shadow_pct < 30 else 0
    body_score = min(body_pct * 3, 25)
    atr_score = min(atr_pct * 2, 16)
    total_score = shadow_score + body_score + atr_score
    
    # 涨幅
    pct_today = sd["pct"][di]
    
    # 次日最高（如果有数据）
    next_high = round((sd["recs"][di+1]["high"]/cl-1)*100, 2) if di+1 < len(sd["recs"]) else None
    
    candidates_detail.append({
        'code': code, 'close': cl, 'open': op, 'high': hi, 'low': lo,
        'shadow_pct': round(shadow_pct, 1), 'body_pct': round(body_pct, 2),
        'atr_pct': round(atr_pct, 2), 'pct_today': round(pct_today, 2),
        'shadow_score': round(shadow_score, 1),
        'body_score': round(body_score, 1),
        'atr_score': round(atr_score, 1),
        'total_score': round(total_score, 1),
        'passed': passed,
        'filters': filters,
        'next_high': next_high,
        'pos20': round(sd.get('pos20', [None]*len(sd['c']))[di] if 'pos20' in sd else 0, 1)
    })

# 按评分排序
candidates_detail.sort(key=lambda x: x['total_score'], reverse=True)

# ===== 统计 =====
total_scanned = len(candidates_detail)
passed_count = sum(1 for c in candidates_detail if c['passed'])
print(f"\n📊 全市场扫描: {total_scanned}只主板股")
print(f"✅ 通过7条硬过滤: {passed_count}只")
print(f"❌ 被过滤: {total_scanned-passed_count}只")

# 过滤原因统计
reasons = defaultdict(int)
for c in candidates_detail:
    if not c['passed']:
        for k, v in c['filters'].items():
            if not v:
                reasons[k] += 1
print(f"\n❌ 过滤原因排名:")
for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"   {reason:<12} {count:>4}只 ({count/total_scanned*100:.0f}%)")

# ===== 冠军vs runner-ups 详细对比 =====
passed_candidates = [c for c in candidates_detail if c['passed']]

print(f"\n{'='*80}")
print(f"🏆 冠军 vs 落选者 — 详细评分对比")
print(f"{'='*80}")

if passed_candidates:
    champ = passed_candidates[0]
    
    # 冠军详情
    print(f"\n🥇 #1 冠军: {champ['code']}")
    print(f"  总分: {champ['total_score']:.1f}分")
    print(f"    上影线: {champ['shadow_score']:.1f}分 (上影{champ['shadow_pct']:.1f}%)")
    print(f"    阳线实体: {champ['body_score']:.1f}分 (实体{champ['body_pct']:.2f}%)")
    print(f"    ATR: {champ['atr_score']:.1f}分 (ATR{champ['atr_pct']:.2f}%)")
    print(f"    今日涨跌: {champ['pct_today']:+.2f}%")
    print(f"    次日最高: {champ['next_high']}%" if champ['next_high'] else "    次日: 无数据")
    
    # 输出全部候选详细对比表
    print(f"\n📋 全部候选排名 (共{len(passed_candidates)}只)")
    print(f"{'排名':<4} {'代码':<10} {'总分':>5} {'上影分':>6} {'实体分':>6} {'ATR分':>5} {'上影%':>6} {'实体%':>6} {'ATR%':>6} {'涨%':>6} {'次日':>6}")
    print("-"*70)
    
    for rank, c in enumerate(passed_candidates[:20], 1):
        next_str = f"{c['next_high']:+.1f}%" if c['next_high'] else "N/A"
        mk = "🏆" if rank == 1 else ""
        print(f"{rank:<4} {c['code']:<10} {c['total_score']:>5.1f} {c['shadow_score']:>6.1f} {c['body_score']:>6.1f} {c['atr_score']:>5.1f} {c['shadow_pct']:>5.1f}% {c['body_pct']:>5.2f}% {c['atr_pct']:>5.2f}% {c['pct_today']:>5.2f}% {next_str:>6} {mk}")
    
    if len(passed_candidates) > 20:
        print(f"  ... 还有{len(passed_candidates)-20}只")
    
    # 冠军输家分析：为什么第2名没当冠军
    if len(passed_candidates) >= 2:
        print(f"\n{'='*80}")
        print(f"🔍 为什么亚军不是冠军？")
        print(f"{'='*80}")
        
        for rank, c in enumerate(passed_candidates[1:6], 2):
            print(f"\n#{rank} {c['code']}:")
            diff_shadow = champ['shadow_score'] - c['shadow_score']
            diff_body = champ['body_score'] - c['body_score']
            diff_atr = champ['atr_score'] - c['atr_score']
            loss_parts = []
            if diff_shadow > 0: loss_parts.append(f"上影输了{diff_shadow:.1f}分({champ['shadow_pct']:.1f}% vs {c['shadow_pct']:.1f}%)")
            elif diff_shadow < 0: loss_parts.append(f"上影赢了{-diff_shadow:.1f}分")
            if diff_body > 0: loss_parts.append(f"实体输了{diff_body:.1f}分({champ['body_pct']:.2f}% vs {c['body_pct']:.2f}%)")
            elif diff_body < 0: loss_parts.append(f"实体赢了{-diff_body:.1f}分")
            if diff_atr > 0: loss_parts.append(f"ATR输了{diff_atr:.1f}分({champ['atr_pct']:.2f}% vs {c['atr_pct']:.2f}%)")
            elif diff_atr < 0: loss_parts.append(f"ATR赢了{-diff_atr:.1f}分")
            print(f"  {' + '.join(loss_parts)}")
            print(f"  总分差: {champ['total_score']-c['total_score']:.1f}分")
        
        # 冠军的风险点分析
        print(f"\n{'='*80}")
        print(f"⚠️ 冠军风险点")
        print(f"{'='*80}")
        risks = []
        if champ['shadow_pct'] > 10: risks.append(f"上影线偏长({champ['shadow_pct']:.1f}%)，可能被砸")
        if champ['body_pct'] < 2: risks.append(f"阳线实体偏小({champ['body_pct']:.2f}%)，爆发力不足")
        if champ['pct_today'] > 5: risks.append(f"当日涨幅过大({champ['pct_today']:+.2f}%)，追高风险")
        if champ['pct_today'] < 0.5: risks.append(f"当日涨幅太小({champ['pct_today']:+.2f}%)，次日可能无冲劲")
        if not risks:
            risks.append("冠军各项指标健康")
        for r in risks:
            print(f"  ⚡ {r}")

# ===== 今日大盘环境 =====
print(f"\n{'='*80}")
print(f"📈 今日大盘环境")
print(f"{'='*80}")
# 看看上证
for code, sd in all_codes.items():
    if code in ['sh000001', 'sh999999']:
        di = sd["date_idx"].get(TODAY)
        if di:
            print(f"  上证指数: {sd['c'][di]:.2f} ({sd['pct'][di]:+.2f}%)")
            print(f"  今日开盘: {sd['o'][di]:.2f}  最高: {sd['h'][di]:.2f}  最低: {sd['l'][di]:.2f}")
            break

print(f"\n⏱ 总用时: {time.time()-t0:.0f}秒")
