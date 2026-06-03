"""检查2025年数据完整性"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

P_MIN,P_MAX=5,8;VR_MIN,VR_MAX=0.8,2.0;HSL_MIN,HSL_MAX=5,15;SZ_MAX=300;CL_MIN,CL_MAX=60,90;J_MAX=100

# 检查2025年每天候选池中，有多少只有K线数据
print("=== 2025年数据完整性检查 ===", flush=True)
print(f"{'日期':<12} {'候选只':>5} {'有K线':>5} {'有次日':>5} {'次日达2.5%':>10} {'说明':>12}", flush=True)
print('-'*55, flush=True)

missing_nxt = 0
total_cand_2025 = 0
total_with_nxt = 0
total_poor_days = 0

for dt in dates:
    if not dt.startswith('2025'): continue
    cand_count = 0
    with_nxt = 0
    reach_25 = 0
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
        cand_count += 1
        
        # 检查K线
        fp=os.path.join(CACHE_DIR,f'{code}.json')
        if os.path.exists(fp):
            try:
                with open(fp) as f: kdata=json.load(f)
                idx=next((i for i,k in enumerate(kdata) if k['date']==dt), None)
                if idx is not None and idx+1 < len(kdata):
                    with_nxt += 1
                    bc=kdata[idx]['close']
                    nh=(kdata[idx+1]['high']/bc-1)*100 if bc>0 else 0
                    if nh>=2.5: reach_25+=1
            except: pass
    
    total_cand_2025 += cand_count
    total_with_nxt += with_nxt
    
    if cand_count > 0 and with_nxt == 0:
        total_poor_days += 1
        note = '❌ 无次日数据'
    elif cand_count > 0 and with_nxt < cand_count * 0.5:
        total_poor_days += 1
        note = f'⚠️ 仅{with_nxt}/{cand_count}有'
    else:
        note = '✅'
    
    if cand_count > 0:
        print(f"{dt:<12} {cand_count:>5} {with_nxt:>5} {with_nxt:>5} {reach_25*100/max(with_nxt,1):>9.1f}% {note}", flush=True)

print(f"\n=== 汇总 ===", flush=True)
print(f"总候选: {total_cand_2025}只", flush=True)
print(f"有次日数据: {total_with_nxt}只 ({total_with_nxt*100/max(total_cand_2025,1):.1f}%)", flush=True)
print(f"数据缺失严重的天数: {total_poor_days}天", flush=True)

# 再检查K线文件本身的日期范围
print(f"\n=== K线文件日期范围（抽样20只） ===", flush=True)
import random
codes = list(names.keys())[:20]
for code in codes:
    fp=os.path.join(CACHE_DIR,f'{code}.json')
    if os.path.exists(fp):
        try:
            with open(fp) as f: kdata=json.load(f)
            print(f"{code}({names.get(code,'')[:8]:<8}): {kdata[0]['date']} ~ {kdata[-1]['date']} ({len(kdata)}条)", flush=True)
        except:
            print(f"{code}: 读取失败", flush=True)
