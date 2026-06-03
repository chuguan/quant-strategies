"""逐个测试新维度因子——只保留真正有帮助的"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())
target = [d for d in dates if d >= '2026-04-10']

def get_nxt(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is not None and idx+1 < len(kdata):
            bc = kdata[idx]['close']
            return (kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
    except: return 0

def calc_wr(code, date):
    fp = os.path.join(CACHE_DIR, f'{code}.json')
    if not os.path.exists(fp): return 50, 50, 0
    try:
        with open(fp) as f: kdata = json.load(f)
        idx = next((i for i,k in enumerate(kdata) if k['date']==date), None)
        if idx is None or idx < 14: return 50, 50, 0
        h14 = max(k['high'] for k in kdata[idx-13:idx+1])
        l14 = min(k['low'] for k in kdata[idx-13:idx+1])
        c = kdata[idx]['close']
        wr_t = (h14-c)/(h14-l14)*100 if h14!=l14 else 50
        if idx < 15: return wr_t, 50, 0
        h14_y = max(k['high'] for k in kdata[idx-14:idx])
        l14_y = min(k['low'] for k in kdata[idx-14:idx])
        c_y = kdata[idx-1]['close']
        wr_y = (h14_y-c_y)/(h14_y-l14_y)*100 if h14_y!=l14_y else 50
        y_p = (kdata[idx-1]['close']/kdata[idx-2]['close']-1)*100 if idx>=2 else 0
        return wr_t, wr_y, y_p
    except: return 50, 50, 0

def ps(p): return min(10, max(1, 11-p/10))

# 选股固定
P_MIN,P_MAX=5,8; VR_MIN,VR_MAX=0.8,2.0; HSL_MIN,HSL_MAX=5,15; SZ_MAX=300; CL_MIN,CL_MAX=60,90; J_MAX=100

# 预计算
all_data={}
for dt in target:
    cand=[]
    for s in data.get(dt, []):
        code,p=s['code'],s['p']
        if p<P_MIN or p>P_MAX: continue
        vr=s.get('vol_ratio',0) or 0
        if vr<VR_MIN or vr>VR_MAX: continue
        ri=real.get(code)
        if not ri: continue
        hsl=(ri.get('hsl',0) or 0)
        if hsl<HSL_MIN or hsl>HSL_MAX: continue
        sz=(ri.get('shizhi',0) or 0)
        if sz>=SZ_MAX: continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        jv=s.get('j_val',0) or 0
        if jv>J_MAX: continue
        cl=s.get('cl',0)
        if cl<CL_MIN or cl>CL_MAX: continue
        buy=s.get('close',0); dif=s.get('dif_val',0) or 0
        macd_g=s.get('macd_golden',0); above5=s.get('above_ma5',0)
        is_yang=s.get('is_yang',0); close=s.get('close',0)
        ma5=s.get('ma5',0) or 0; ma10=s.get('ma10',0) or 0; ma20=s.get('ma20',0) or 0
        wr_t,wr_y,y_p=calc_wr(code,dt); nh=get_nxt(code,dt)
        fp=os.path.join(CACHE_DIR,f'{code}.json'); klines=None
        if os.path.exists(fp):
            try:
                with open(fp) as f: klines=json.load(f)
            except: pass
        
        # 预计算所有新因子
        # F1: 量比1.8~2.0加1分
        f1 = 1 if 1.8<=vr<2.0 else 0
        # F2: 量比2.0~2.5加2分
        f2 = 2 if 2.0<=vr<=2.5 else 0
        # F3: 换手5~7加2分
        f3 = 2 if 5<=hsl<=7 else 0
        # F4: 换手>10减2分
        f4 = -2 if hsl>10 else 0
        # F5: 均线多头加3分
        f5 = 3 if ma5>ma10>ma20 and ma5>close*0.98 else 0
        # F6: 均线空头减3分
        f6 = -3 if ma5<ma10<ma20 else 0
        # F7: 突破前5日高+20日线加3分
        f7 = 0
        if klines:
            idx=next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx is not None and idx>=5:
                h5=max(k['high'] for k in klines[idx-4:idx+1])
                if close>h5 and close>ma20: f7=3
        # F8: 市值50~200加2分
        f8 = 2 if 50<=sz<=200 else (-2 if sz<50 or sz>200 else 0)
        # F9: 收阳+量比>1.2加2分
        f9 = 2 if is_yang and vr>1.2 else 0
        # F10: MACD金叉+DIF>0加1分
        f10 = 1 if macd_g and dif>0 else 0
        # F11: 高位放量滞涨减5分
        f11 = 0
        if klines:
            idx=next((i for i,k in enumerate(klines) if k['date']==dt), None)
            if idx is not None and idx>=10:
                c10=klines[idx-9]['close']
                pct_10d=(close/c10-1)*100
                if pct_10d<20 and vr>2.5 and p<3: f11=-5
        
        # 突破v8基础分
        wr_s=min(5,max(0,(35-wr_t)*5/35)) if wr_t<35 and wr_y>=35 else 0
        yp=-3 if y_p>7 else 0
        macd_s=(10 if macd_g and dif>0.5 else 8 if macd_g and dif>0.2 else 6 if macd_g else 4 if dif>0.5 else 2 if dif>0 else 0)
        base=p*2.5+cl*0.1+ps(buy)*0.3+macd_s*0.3+3*above5+wr_s*0.5+yp
        
        cand.append((base,p,nh,nm,code,cl,vr,hsl,sz,close,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,ma5,ma10,ma20))
    if cand: all_data[dt]=cand

total=sum(len(v) for v in all_data.values())
print(f"{len(all_data)}天, {total}只, 均{total//len(all_data)}只/天\n", flush=True)

# ===== 逐个因子测试 =====
print(f"{'因子':<20} {'类型':>4} {'加权后胜率':>12} {'对比82.1%':>8} {'T3':>5}", flush=True)
print('-'*55, flush=True)

# 基线（无任何新因子）
w_base=0; nd=0
for dt in target:
    if dt not in all_data: continue
    cand=[(c[0],c[2],c[1]) for c in all_data[dt]]
    cand.sort(key=lambda x: (-x[0], -x[2]))
    nd+=1
    if cand[0][1]>=2.5: w_base+=1

# 逐个测试每个因子
factor_names = ['量比1.8~2.0+1','量比2.0~2.5+2','换手5~7+2','换手>10-2',
                '均线多头+3','均线空头-3','突破前5H+20MA+3','市值50~200+2',
                '收阳+VR>1.2+2','MACD金+DIF>0+1','高位放量滞涨-5']

for i, fname in enumerate(factor_names):
    fi = 10 + i  # f1~f11在tuple中的位置
    for w in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]:
        wins=0; ndays=0; t3=0
        for dt in target:
            if dt not in all_data: continue
            cand=[(c[0]+c[fi]*w, c[2], c[1]) for c in all_data[dt]]
            cand.sort(key=lambda x: (-x[0], -x[2]))
            ndays+=1
            if cand[0][1]>=2.5: wins+=1
            if any(x[1]>=2.5 for x in cand[:3]): t3+=1
        if wins*100/ndays >= w_base*100/nd:
            chg = wins*100/ndays - w_base*100/nd
            print(f"{fname:<20} {w:>4.1f} {wins*100/ndays:>10.1f}% {chg:>+7.1f}% {t3*100/ndays:>5.1f}%", flush=True)
            break  # 只显示第一个有效权重

print(f"\n基线(无新因子): {w_base}/{nd}({w_base*100/nd:.1f}%)", flush=True)

# ===== 组合最优因子 =====
print(f"\n=== 组合有效因子 ===", flush=True)
from itertools import combinations

# 找出所有有效因子
valid = [(10+i, fn) for i, fn in enumerate(factor_names)]

# 测试所有双因子组合
best_combo = None; best_rate=0
for r in range(1, min(5, len(valid)+1)):
    for combo in combinations(valid, r):
        idxs = [c[0] for c in combo]
        for w_combo in [(1.0,)]:  # 简化权重
            wins=0; ndays=0
            for dt in target:
                if dt not in all_data: continue
                cand=[]
                for c in all_data[dt]:
                    s = c[0]  # 基础分
                    for idx in idxs:
                        s += c[idx] * 1.0  # 每个因子权重1
                    cand.append((s, c[2], c[1]))
                if not cand: continue
                cand.sort(key=lambda x: (-x[0], -x[2]))
                ndays+=1
                if cand[0][1]>=2.5: wins+=1
            rate=wins*100/ndays
            if rate > best_rate:
                best_rate=rate
                best_combo=([fn for _,fn in combo], rate, wins, ndays)

if best_combo:
    print(f"最优组合: {', '.join(best_combo[0])}", flush=True)
    print(f"胜率: {best_combo[2]}/{best_combo[3]}({best_combo[1]:.1f}%)", flush=True)
