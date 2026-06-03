"""虚涨日：加用户减分项"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']
dates = [x for x in sorted(data.keys()) if '2025-01-01' <= x < '2026-06-01']

def classify(dt):
    stocks = data.get(dt, [])
    if not stocks: return 'flat'
    ps = [s.get('p', 0) or 0 for s in stocks]
    vrs = [s.get('vol_ratio', 0) or 0 for s in stocks if s.get('vol_ratio', 0)]
    avg_p = sum(ps) / len(ps)
    avg_vr = sum(vrs) / len(vrs) if vrs else 0
    hot = sum(1 for p in ps if 5 <= p <= 8)
    if avg_p > 0.5:
        return 'fake_up' if hot < 15 or avg_vr < 0.9 else 'real_up'
    if avg_p < -0.5: return 'down'
    return 'flat'

fakes = [dt for dt in dates if classify(dt) == 'fake_up']
print(f"虚涨日{len(fakes)}天")
print()

# 测试：调整选股范围 + 加减分
tests = [
    # (name, p_min, p_max, vr_min, vr_max, p_w, cl_w, macd_w, 
    #  vr_bonus, ma5_b, 
    #  减分: 放量不涨扣, 放量下跌扣, 缩量扣)
    
    # == 用户建议理想区间2-5% ==
    ("v1原:0-6%,量0.6-2.5,涨1+CL0.05+MACD0.5", 0,6,0.6,2.5, 1.0,0.05,0.5, 0,0, 0,0,0),
    ("v15:2-5%,量1.0-2.5,涨1+CL0.02+MACD0.5+VR1-1.5x1+MA5x2", 2,5,1.0,2.5, 1.0,0.02,0.5, 1.0,2, 0,0,0),
    ("v16:2-5%,量1.0-2.5,涨1.5+CL0.02+MACD0.5+VR1-1.5x1+MA5x2", 2,5,1.0,2.5, 1.5,0.02,0.5, 1.0,2, 0,0,0),
    
    # == 用户减分项 ==
    # 减分: 放量不涨(vr>1.5且p<3%扣3),  放量下跌(阴线+vr>1.2扣5),  缩量(vr<1扣2)
    ("v17:0-6%+减分项", 0,6,0.6,2.5, 1.0,0.05,0.5, 0,0, 3,5,2),
    ("v18:2-5%+量比1.0+减分项", 2,5,1.0,2.5, 1.0,0.02,0.5, 1.0,2, 3,5,0),
    ("v19:0-6%+涨2+CL0+减分项", 0,6,0.6,2.5, 2.0,0,0.5, 0,0, 3,5,2),
    
    # == 缩量(vr<1)直接排除 ==
    ("v20:0-6%,量1.0-2.5,涨1.5+CL0.02+MACD0.5+MA5x2", 0,6,1.0,2.5, 1.5,0.02,0.5, 0,2, 0,0,0),
    ("v21:2-5%,量1.0-2.5,涨1.5+CL0.01+MACD0.3+MA5x2", 2,5,1.0,2.5, 1.5,0.01,0.3, 0,2, 0,0,0),
    
    # == 最优组合搜索 ==
    ("v22:2-5%,量1.0-2.5,涨2+CL0+MACD0.5", 2,5,1.0,2.5, 2.0,0,0.5, 0,0, 0,0,0),
    ("v23:2-5%,量1.0-2.5,涨1.5+CL0.01+MACD0.5+MA5x2", 2,5,1.0,2.5, 1.5,0.01,0.5, 0,2, 0,0,0),
]

for name,p_min,p_max,vr_min,vr_max,p_w,cl_w,macd_w,vr_b,ma5_b,dk_bz,dk_dn,dk_sl in tests:
    wins = 0
    bads = []
    no_pool = 0
    for dt in fakes:
        cand = []
        for s in data.get(dt, []):
            code = s['code']
            p = s.get('p', 0) or 0
            if p < p_min or p > p_max: continue
            vr = s.get('vol_ratio', 0) or 0
            if vr < vr_min or vr > vr_max: continue
            ri = real.get(code)
            if not ri: continue
            h = (ri.get('hsl', 0) or 0)
            if h < 5 or h > 20: continue
            if (ri.get('shizhi', 0) or 0) >= 200: continue
            nm = names.get(code, '')
            if 'ST' in nm or '*ST' in nm or '退' in nm: continue
            cl = s.get('cl', 0)
            if cl < 30 or cl > 95: continue
            nh = s.get('n', 0) or 0
            if nh <= 0: continue
            dif = s.get('dif_val', 0) or 0
            mg = s.get('macd_golden', 0)
            buy = s.get('close', 0) or 0
            a5 = s.get('above_ma5', 0) or 0
            iy = s.get('is_yang', 0) or 0
            
            ms = 0
            if mg and dif > 0.5: ms = 10
            elif mg and dif > 0.2: ms = 8
            elif mg: ms = 6
            elif dif > 0.5: ms = 4
            elif dif > 0: ms = 2
            ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
            vr_pt = vr_b * 1.5 if 1.0 <= vr <= 1.5 else 0
            ma5_g = ma5_b if a5 else 0
            
            # 减分项
            dk = 0
            if dk_bz and vr > 1.5 and p < 3: dk = -dk_bz  # 放量不涨
            if dk_dn and not iy and vr > 1.2: dk = -dk_dn  # 放量阴线
            if dk_sl and vr < 1: dk = -dk_sl  # 缩量
            
            score = p * p_w + cl * cl_w + ps2 * 0.3 + ms * macd_w + vr_pt + ma5_g + dk
            cand.append((score, nh, p, nm[:12], cl, vr, iy))
        
        if cand:
            cand.sort(key=lambda x: (-x[0], -x[2]))
            if cand[0][1] >= 2.5:
                wins += 1
            else:
                bads.append(dt)
        else:
            no_pool += 1
            bads.append(f"{dt}(无池)")
    
    print(f"{wins}/17={wins*100/17:.1f}% | {name}", end="")
    if no_pool:
        print(f" [缺池{no_pool}天]", end="")
    print()
    if bads:
        print(f"  ❌ {', '.join(bads)}")
