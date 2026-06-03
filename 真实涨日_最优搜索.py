"""真实涨日 - 快速出结果"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
print("Loading...", flush=True)
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

def classify_market(stocks):
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps)/len(ps); avg_vr = sum(vrs)/len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5<=p<=8)
    if avg_p>0.5: return 'fake_up' if hot<15 or avg_vr<0.9 else 'real_up'
    if avg_p<-0.5: return 'down'
    return 'flat'

real_up_dates = []
for dt in dates:
    stocks = data.get(dt,[])
    if not stocks: continue
    if classify_market(stocks) == 'real_up': real_up_dates.append(dt)
print(f"真实涨日{len(real_up_dates)}天", flush=True)

def calc_macd(dif, mg):
    if mg and dif > 0.5: return 10
    if mg and dif > 0.2: return 8
    if mg: return 6
    if dif > 0.5: return 4
    if dif > 0: return 2
    return 0

# 通用跑测试
def run(dates, p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max,
        p_w,cl_w,macd_w,ma5_b,vr_b,hsl_b,wr_b,j_b,j_low_b):
    wins = 0
    for dt in dates:
        cand = []
        for s in data.get(dt, []):
            code = s['code']
            p = s.get('p', 0) or 0
            if p < p_min or p > p_max: continue
            vr = s.get('vol_ratio', 0) or 0
            if vr < vr_min or vr > vr_max: continue
            ri = real.get(code)
            if not ri: continue
            hsl = (ri.get('hsl', 0) or 0)
            if hsl < hs_min or hsl > hs_max: continue
            if (ri.get('shizhi', 0) or 0) >= sz_max: continue
            nm = names.get(code, '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < cl_min or cl > cl_max: continue
            nh = s.get('n', 0) or 0
            if nh <= 0: continue
            dif = s.get('dif_val', 0) or 0
            mg = s.get('macd_golden', 0)
            buy = s.get('close', 0) or 0
            a5 = s.get('above_ma5', 0) or 0
            jv = s.get('j_val', 0) or 0
            wrv = s.get('wr_val', 0) or 0
            ms = calc_macd(dif, mg)
            ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
            hsl_plus = hsl_b * 2 if 5 <= hsl <= 7 else 0
            j_plus = j_b if jv > 70 else 0
            j_low = j_low_b if jv < 20 else 0
            vr_plus = vr_b * 1.5 if 1.0 <= vr <= 1.5 else 0
            wr_plus = wr_b if wrv < -80 else 0
            ma5_plus = ma5_b if a5 else 0
            score = p * p_w + cl * cl_w + ps2 * 0.3 + ms * macd_w
            score += ma5_plus + vr_plus + hsl_plus + j_plus + j_low + wr_plus
            cand.append((score, nh))
        if cand:
            cand.sort(key=lambda x: (-x[0]))
            if cand[0][1] >= 2.5:
                wins += 1
    return wins

# ===== Step1: 选股条件 =====
print(f"\n【Step1 选股条件搜索】", flush=True)
best1 = {'w':0}
for p_min in [3, 4, 5]:
 for p_max in [7, 8]:
  if p_max - p_min < 2: continue
  for vr_min in [0.6, 0.8, 1.0]:
   for vr_max in [2.0, 2.5]:
    for hs_min in [3, 5]:
     for hs_max in [15, 20]:
      for sz_max in [200, 300]:
       for cl_min in [50, 60, 65]:
        for cl_max in [90, 95]:
         w = run(real_up_dates, p_min,p_max,vr_min,vr_max,hs_min,hs_max,sz_max,cl_min,cl_max,
                 1.0, 0.05, 0.3, 0, 0, 0, 0, 0, 0)
         if w > best1['w']:
             best1 = {'w':w,'p_min':p_min,'p_max':p_max,'vr_min':vr_min,'vr_max':vr_max,
                      'hs_min':hs_min,'hs_max':hs_max,'sz_max':sz_max,'cl_min':cl_min,'cl_max':cl_max}
             print(f"  {w}/{len(real_up_dates)}={w*100/len(real_up_dates):.1f}% | 涨{p_min}~{p_max}% 量{vr_min}~{vr_max} 换{hs_min}~{hs_max} CL{cl_min}~{cl_max} {sz_max}亿", flush=True)

print(f"\n 最优选股条件: 涨{best1['p_min']}~{best1['p_max']}% 量{best1['vr_min']}~{best1['vr_max']} 换{best1['hs_min']}~{best1['hs_max']} CL{best1['cl_min']}~{best1['cl_max']} {best1['sz_max']}亿 = {best1['w']}/{len(real_up_dates)}={best1['w']*100/len(real_up_dates):.1f}%")

# ===== Step2: 评分权重 =====
print(f"\n【Step2 评分权重搜索】", flush=True)
best2 = {'w':0}
for p_w in [0.5,1.0,1.5,2.0,2.5,3.0]:
 for cl_w in [0,0.03,0.05,0.08,0.1,0.15]:
  for macd_w in [0,0.3,0.5]:
   for ma5_b in [0,2,3]:
    for vr_b in [0,1,2]:
     for hsl_b in [0,0.3]:
      for wr_b in [0,2]:
       for j_b in [0,2]:
        for j_low_b in [0,2]:
         w = run(real_up_dates, best1['p_min'],best1['p_max'],best1['vr_min'],best1['vr_max'],
                 best1['hs_min'],best1['hs_max'],best1['sz_max'],best1['cl_min'],best1['cl_max'],
                 p_w,cl_w,macd_w,ma5_b,vr_b,hsl_b,wr_b,j_b,j_low_b)
         if w > best2['w']:
             best2 = {'w':w,'p_w':p_w,'cl_w':cl_w,'macd_w':macd_w,'ma5_b':ma5_b,'vr_b':vr_b,
                      'hsl_b':hsl_b,'wr_b':wr_b,'j_b':j_b,'j_low_b':j_low_b}
             print(f"  {w}/{len(real_up_dates)}={w*100/len(real_up_dates):.1f}% | 涨x{p_w}+CLx{cl_w}+MACDx{macd_w}+MA5x{ma5_b}+VRx{vr_b}+HSLx{hsl_b}+WRx{wr_b}+J>70x{j_b}+J<20x{j_low_b}", flush=True)

print(f"\n{'='*60}")
print(f"** 真实涨日最终最优 **")
print(f"选股: 涨{best1['p_min']}~{best1['p_max']}% 量{best1['vr_min']}~{best1['vr_max']} 换{best1['hs_min']}~{best1['hs_max']}% CL{best1['cl_min']}~{best1['cl_max']}% 市值<{best1['sz_max']}亿")
print(f"评分: 涨x{best2['p_w']}+CLx{best2['cl_w']}+MACDx{best2['macd_w']}+MA5x{best2['ma5_b']}+VR1-1.5x{best2['vr_b']}+换5-7x{best2['hsl_b']}+WR<-80x{best2['wr_b']}+J>70x{best2['j_b']}+J<20x{best2['j_low_b']}")
print(f"冠军胜率: {best2['w']}/{len(real_up_dates)}={best2['w']*100/len(real_up_dates):.1f}%")
