"""逐周逐日定位——找出最差周和日"""
import pickle, json, os
from datetime import datetime, timedelta
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d=pickle.load(open('big_cache_full.pkl','rb'))
data, real, names = d['data'], d['real'], d['names']
dates=[x for x in sorted(data.keys()) if x>='2025-01-01' and x<'2026-06-01']

def get_week_id(dt_str):
    """返回周标识 2025-W01"""
    dt=datetime.strptime(dt_str,'%Y-%m-%d')
    iso=dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

# 运行v11策略
from collections import defaultdict
weekly={}; daily={}
for dt in dates:
    stocks=data.get(dt,[])
    if not stocks: continue
    all_p=[x['p'] for x in stocks if 'p' in x]
    avg_mkt=sum(all_p)/len(all_p) if all_p else 0
    mkt='up' if avg_mkt>0.5 else ('down' if avg_mkt<-0.5 else 'flat')
    
    cand=[]
    for s in stocks:
        code,p=s['code'],s['p']
        if p<5 or p>8: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<0.8 or vr>2.0: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<5 or hsl>15: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=300: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>100: continue
        cl=s.get('cl',0)
        if cl<60 or cl>90: continue
        nh=s.get('n',0) or 0
        if nh<=0: continue
        buy=s.get('close',0); dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        ps2=min(10,max(1,11-buy/10))
        hsl_b=2*0.3 if 5<=hsl<=7 else 0
        duotou_b=3*0.3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        yang_vr_b=2*0.3 if is_yang and vr>1.2 else 0
        
        if mkt=='up':
            score=p*3.0+cl*0.1+ps2*0.3+macd_s*0.3+3*above5+hsl_b+duotou_b
        elif mkt=='down':
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5
        else:
            score=p*2.0+cl*0.05+ps2*0.3+macd_s*0.3+3*above5+hsl_b+yang_vr_b
        
        cand.append((score,nh,p,nm,code))
    
    if not cand: continue
    cand.sort(key=lambda x:(-x[0], -x[2]))
    win=1 if cand[0][1]>=2.5 else 0
    nh_actual=cand[0][1]
    
    wk=get_week_id(dt)
    weekly.setdefault(wk,[0,0])
    weekly[wk][0]+=win; weekly[wk][1]+=1
    daily[dt]={'win':win,'nh':nh_actual,'champ':cand[0][3],'code':cand[0][4],'mkt':mkt}

# ===== 输出最差周 =====
print(f"{'月份':<10} {'周':<12} {'天数':>4} {'冠军':>6} {'胜率':>6}", flush=True)
print('-'*45, flush=True)

# 按月汇总
monthly={}
for dt in dates:
    if dt not in daily: continue
    m=dt[:7]
    monthly.setdefault(m,[0,0])
    monthly[m][0]+=daily[dt]['win']
    monthly[m][1]+=1

# 按周排序输出
worst_weeks=[]
for wk in sorted(weekly.keys()):
    w,t=weekly[wk]
    rate=w*100/t
    m=wk[:7]
    if rate<50:
        worst_weeks.append((wk, w, t, rate))
        print(f"{m:<10} {wk:<12} {t:>4} {w:>3}/{t:<3} {rate:>5.1f}% ❌", flush=True)

print(f"\n{'='*60}", flush=True)
print(f"共 {len(worst_weeks)} 个周胜率<50%", flush=True)
print(f"{'='*60}", flush=True)

# ===== 最差周逐日明细 =====
print(f"\n=== 最差周逐日明细 ===", flush=True)
for wk,w,t,rate in sorted(worst_weeks, key=lambda x: x[3])[:10]:
    print(f"\n📅 {wk} (胜率{rate:.0f}%)", flush=True)
    print(f"{'日期':<12} {'冠军':<12} {'次日最高':>8} {'大盘':>4} {'结果':>2}", flush=True)
    print('-'*42, flush=True)
    for dt in sorted(daily.keys()):
        if get_week_id(dt)!=wk: continue
        d=daily[dt]
        tag='✅' if d['win'] else '❌'
        nh_str=f"{d['nh']:+.1f}%"
        print(f"{dt:<12} {d['champ'][:8]:<12} {nh_str:>8} {d['mkt']:>4} {tag:>2}", flush=True)
