#!/usr/bin/env python3
"""实时API资金流向分析"""
import sys, os, time, subprocess, json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

def curl_get(url, t=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(t),url],capture_output=True,timeout=t+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

t0 = time.time()

# 批量拉全市场
codes = [str(i) for i in range(600000,606000)] + [f'{i:06d}' for i in range(3000)]
all_stocks = {}

for i in range(0,len(codes),80):
    chunk=codes[i:i+80]
    syms=[f'{PREFIX(c)}{c}' for c in chunk]
    text=curl_get(f'https://qt.gtimg.cn/q={",".join(syms)}',6)
    for line in text.split('\n'):
        if '~' not in line: continue
        parts=line.split('~')
        if len(parts)<46: continue
        try:
            nm=parts[1]; code=parts[2]
            if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
            if not IS_MAIN(code): continue
            p=float(parts[3]) if parts[3] else 0
            pc=float(parts[4]) if parts[4] else 0
            pct=round((p/pc-1)*100,2) if pc else 0
            hi=float(parts[33]) if parts[33] else 0
            lo=float(parts[34]) if parts[34] else 0
            op=float(parts[5]) if parts[5] else 0
            vr=float(parts[38]) if parts[38] else 0
            hsl=float(parts[46]) if parts[46] and float(parts[46])<100 else 0
            # 资金流向（外盘-内盘）
            inner=float(parts[41]) if parts[41] else 0
            outer=float(parts[42]) if parts[42] else 0
            net_money = outer - inner  # 正=资金净流入
            amount=float(parts[37])/10000 if parts[37] else 0  # 亿元
            sz=float(parts[44])/1e8 if parts[44] else 0
            
            all_stocks[code] = {
                'name':nm,'price':p,'pct':pct,'vr':vr,'hsl':hsl,
                'net':net_money,'amount':amount,'sz':sz,
                'high':hi,'low':lo,'open':op
            }
        except: pass

elapsed = time.time()-t0

# ===== 分析 =====
stocks = list(all_stocks.values())
total = len(stocks)
up = sum(1 for s in stocks if s['pct']>0)
down = sum(1 for s in stocks if s['pct']<0)
flat = total-up-down
涨停 = sum(1 for s in stocks if s['pct']>=9.8)
跌停 = sum(1 for s in stocks if s['pct']<=-9.8)
涨5 = sum(1 for s in stocks if 5<=s['pct']<=8)
涨3 = sum(1 for s in stocks if 3<=s['pct']<5)
跌3 = sum(1 for s in stocks if -5<=s['pct']<=-3)
跌5 = sum(1 for s in stocks if -8<=s['pct']<=-5)

avg_pct = sum(s['pct'] for s in stocks)/total if total else 0
avg_vr = sum(s['vr'] for s in stocks if s['vr']>0)/sum(1 for s in stocks if s['vr']>0) if any(s['vr']>0 for s in stocks) else 0

# 涨幅榜
top_gainers = sorted(stocks, key=lambda x:-x['pct'])[:10]
# 跌幅榜
top_losers = sorted(stocks, key=lambda x:x['pct'])[:5]
# 资金净流入TOP
top_net_in = sorted(stocks, key=lambda x:-x['net'])[:10]
# 资金净流出TOP
top_net_out = sorted(stocks, key=lambda x:x['net'])[:5]
# 放量TOP
top_vr = sorted(stocks, key=lambda x:-x['vr'])[:10]

# 资金意图分析
net_in_total = sum(s['net'] for s in stocks if s['net']>0)
net_out_total = sum(s['net'] for s in stocks if s['net']<0)
net_in_count = sum(1 for s in stocks if s['net']>0)
net_out_count = sum(1 for s in stocks if s['net']<0)

print(f"\n{'='*60}")
print(f"  实时资金流向分析 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
print(f"{'='*60}")
print(f"  📡 数据: {total}只主板股 ({elapsed:.0f}s)")

print(f"\n{'─'*40}")
print(f"  一、大盘全景")
print(f"{'─'*40}")
print(f"  涨:{up} | 跌:{down} | 平:{flat}")
print(f"  涨停:{涨停} | 跌停:{跌停}")
print(f"  涨5~8%:{涨5}只 | 涨3~5%:{涨3}只")
print(f"  跌3~5%:{跌3}只 | 跌5~8%:{跌5}只")
print(f"  均价涨幅: {avg_pct:+.2f}% | 均量比: {avg_vr:.2f}")

# 行情判定
if avg_pct > 0.5:
    hot = sum(1 for s in stocks if 5<=s['pct']<=8)
    market_type = '虚涨日' if hot < 15 or avg_vr < 0.9 else '真实涨日'
elif avg_pct < -0.5:
    market_type = '跌日'
else:
    market_type = '横盘'

print(f"  市场类型: {market_type}")

print(f"\n{'─'*40}")
print(f"  二、资金流向分析")
print(f"{'─'*40}")
print(f"  净流入家数: {net_in_count} (+{net_in_total/10000:.0f}万手)")
print(f"  净流出家数: {net_out_count} ({net_out_total/10000:.0f}万手)")
print(f"  资金态度: ", end='')
if net_in_count > net_out_count * 1.2:
    print("🟢 资金整体偏多，进场意愿强")
elif net_out_count > net_in_count * 1.2:
    print("🔴 资金整体偏空，出场意愿强")
else:
    print("🟡 资金态度分化，方向不明")

print(f"\n{'─'*40}")
print(f"  三、资金净流入TOP10（主力攻击方向）")
print(f"{'─'*40}")
print(f"  {'名称':<10} {'代码':>7} {'涨幅':>6} {'净流入手':>10} {'量比':>5} {'换手':>5}")
for s in top_net_in[:5]:
    print(f"  {s['name']:<10} {'':>7} {s['pct']:>+5.1f}% {s['net']:>10.0f} {s['vr']:>5.1f} {s['hsl']:>5.1f}%")

print(f"\n{'─'*40}")
print(f"  四、涨幅TOP10（最强进攻方向）")
print(f"{'─'*40}")
print(f"  {'名称':<10} {'涨幅':>6} {'量比':>5} {'换手':>5} {'净流入':>8}")
for s in top_gainers:
    icon = '🚀' if s['pct']>=9.8 else '🔥' if s['pct']>=7 else '⬆'
    arrow = '+' if s['net']>0 else ''
    print(f"  {icon} {s['name']:<10} {s['pct']:>+5.1f}% {s['vr']:>5.1f} {s['hsl']:>5.1f}% {arrow}{s['net']:>7.0f}")

print(f"\n{'─'*40}")
print(f"  五、放量异动TOP10（资金活动最活跃）")
print(f"{'─'*40}")
for s in top_vr[:5]:
    dir_s = '⬆' if s['pct']>0 else '⬇' if s['pct']<0 else '→'
    print(f"  {dir_s} {s['name']:<10} 量比{s['vr']:.1f}x {s['pct']:>+5.1f}% 换手{s['hsl']:.1f}%")

print(f"\n{'─'*40}")
print(f"  六、资金净流出TOP5（撤退方向）")
print(f"{'─'*40}")
for s in top_net_out:
    print(f"  ⬇ {s['name']:<10} 净流出{abs(s['net']):>8.0f}手 {s['pct']:>+5.1f}%")

print(f"\n{'─'*40}")
print(f"  七、擒龙MAX适配分析")
print(f"{'─'*40}")

# 筛选符合条件的候选
candidates = []
for code, s in all_stocks.items():
    pct = s['pct']
    if pct < -5 or pct > 10: continue
    vr = s['vr']
    if vr < 0.3: continue
    hsl = s['hsl']
    if hsl > 30: continue
    sz = s['sz']
    if sz >= 300: continue
    
    # 评分简版
    score = 0
    if pct > 9: score += 35
    elif pct > 7: score += 30
    elif pct > 5: score += 25
    elif pct > 3: score += 15
    elif pct > 0: score += 8
    
    if vr > 2: score += 15
    elif vr > 1.2: score += 10
    elif vr > 0.7: score += 5
    
    if s['net'] > 0: score += 10
    
    if score >= 30:
        candidates.append((score, s['name'], code, pct, vr, hsl, s['net']))

candidates.sort(key=lambda x:-x[0])
print(f"  候选池: {len(candidates)}只（评分≥30）")
print(f"\n  🏆 擒龙TOP3:")
for i, (sc, nm, code, pct, vr, hsl, net) in enumerate(candidates[:3], 1):
    m = ['🥇','🥈','🥉'][i-1]
    print(f"  {m} {nm:<10} 评分{sc} +{pct:.1f}% 量比{vr:.1f}x 换手{hsl:.1f}% 净流入{net:+.0f}手")
    if i==1:
        # 冠军资金意图
        if net > 0 and vr > 1.2 and pct > 5:
            print(f"     ↳ 资金意图: 放量上攻，主力积极做多 ✅")
        elif net < 0 and pct > 0:
            print(f"     ↳ 资金意图: 价涨量缩，主力边拉边出 ⚠️")
        elif vr < 0.7 and pct > 5:
            print(f"     ↳ 资金意图: 缩量上涨，分歧较小但需警惕 ⚡")

print(f"\n{'─'*40}")
print(f"  八、资金意图解读")
print(f"{'─'*40}")
print(f"  📊 今日本市场{market_type}：")
if market_type == '真实涨日':
    print(f"     🔥 真实涨日 + 资金净流入占比{net_in_count/total*100:.0f}% = 多头主导")
    print(f"     💡 建议：积极做多，擒龙/大道至简均可重仓")
elif market_type == '虚涨日':
    print(f"     ⚠️ 虚涨日（涨家数多但量不足）= 动能不足")
    if net_in_count > net_out_count:
        print(f"     💡 但资金净流入占比{net_in_count/total*100:.0f}%，可轻仓参与")
    else:
        print(f"     💡 资金也偏弱，建议观望")
elif market_type == '跌日':
    if net_out_count > net_in_count:
        print(f"     🔴 下跌+资金流出 = 空头主导，建议防守")
    else:
        print(f"     🟡 虽跌但资金未大幅流出 = 洗盘可能，观察明天")
else:  # 横盘
    print(f"     ➡️ 横盘整理，等待方向选择")
    if abs(avg_pct) < 0.2 and abs(net_in_count-net_out_count) < total*0.1:
        print(f"     💤 缩量横盘+资金平衡=观望等待")
    elif net_in_count > net_out_count:
        print(f"     🟢 横盘+暗流涌动（资金净流入>流出）= 蓄力上攻")

print(f"\n{'─'*40}")
print(f"  九、风险提示")
print(f"{'─'*40}")
if 涨停 > 20:
    print(f"  ✅ 涨停{涨停}只，市场情绪高涨")
elif 涨停 > 10:
    print(f"  ✅ 涨停{涨停}只，情绪正常")
else:
    print(f"  ⚠️ 涨停仅{涨停}只，情绪偏弱")

if 跌停 > 10:
    print(f"  🔴 跌停{跌停}只！注意风险")
if 涨5 < 10:
    print(f"  ⚠️ 涨5%+仅{涨5}只，赚钱效应差")
if avg_vr < 0.8:
    print(f"  💤 市场缩量（均量比{avg_vr:.2f}），观望气氛浓")

print(f"\n{'='*60}")
print(f"  耗时: {time.time()-t0:.0f}s")
print(f"{'='*60}")
