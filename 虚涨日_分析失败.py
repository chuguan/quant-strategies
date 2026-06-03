"""深度分析失败2天的评分"""
import pickle, os, sys

os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
d = pickle.load(open('big_cache_full.pkl', 'rb'))
data, real, names = d['data'], d['real'], d['names']

def analyze_date(dt):
    print(f"\n{'='*60}")
    print(f"【{dt}】虚涨日 - 全场评分排名")
    print(f"{'='*60}")
    
    cand = []
    for s in data.get(dt, []):
        code = s['code']
        p = s.get('p', 0) or 0
        if p < 0 or p > 6: continue
        vr = s.get('vol_ratio', 0) or 0
        if vr < 0.6 or vr > 2.5: continue
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
        iy = s.get('is_yang', 0)
        a5 = s.get('above_ma5', 0)
        jv = s.get('j_val', 0) or 0
        
        ms = 0
        if mg and dif > 0.5: ms = 10
        elif mg and dif > 0.2: ms = 8
        elif mg: ms = 6
        elif dif > 0.5: ms = 4
        elif dif > 0: ms = 2
        
        ps2 = min(10, max(1, 11 - buy / 10)) if buy else 0
        score = p * 1.0 + cl * 0.05 + ps2 * 0.3 + ms * 0.5
        cand.append((score, nh, p, nm[:12], cl, vr, mg, dif, a5, iy, buy, jv, code))
    
    cand.sort(key=lambda x: (-x[0], -x[2]))
    
    print(f"候选池共{len(cand)}只")
    print(f"{'名':>3} {'名称':<12} {'涨幅':>5} {'CL':>3} {'量比':>5} {'金叉':>3} {'dif':>5} {'MA5':>3} {'阳':>3} {'买价':>7} {'评分':>6} {'次收':>6}")
    print("-"*80)
    for i, c in enumerate(cand[:20]):
        tag = 'A' if c[1] >= 5 else ('B' if c[1] >= 2.5 else 'C')
        print(f"{i+1:3d}. {c[3]:<12} {c[2]:+5.1f}% {int(c[4]):3d}% {c[5]:5.2f} {c[6]:3d} {c[7]:5.1f} {c[8]:3d} {c[9]:3d} {c[10]:7.2f} {c[0]:6.1f} {c[1]:+5.1f}%[{tag}]  {c[12]}")

analyze_date('2026-02-03')
analyze_date('2026-05-19')
