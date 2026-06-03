"""
4行情评分优化 + 30天逐日明细
使用历史最优评分逻辑 + 失败分析微调
"""
import pickle, sys, os, importlib
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dev/current'))

with open(os.path.join(os.path.dirname(__file__), 'big_cache_full.pkl'), 'rb') as f:
    cache = pickle.load(f)
data = cache['data']
real_data = cache.get('real', {})
names = cache.get('names', {})

dates = sorted(x for x in data.keys() if '2025-06-01' <= x < '2026-06-01')

def cm(s):
    ps=[x.get('p',0) or 0 for x in s]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps)
    vrs=[x.get('vol_ratio',0) or 0 for x in s if x.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0
    ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

# 加载级别
mods = {
    'real_up': importlib.import_module('大道至简_真实涨日_评分策略'),
    'fake_up': importlib.import_module('大道至简_虚涨日_评分策略'),
    'down': importlib.import_module('大道至简_跌日_评分策略'),
    'flat': importlib.import_module('大道至简_横盘_评分策略'),
}

def fl(s_list, lv):
    pool=[]
    for sx in s_list:
        code=sx.get('code','')
        p=(sx.get('p',0) or 0)
        if p<lv['p_min'] or p>lv['p_max']: continue
        if p>=8: continue
        vr=(sx.get('vol_ratio',0) or 0)
        if vr<lv.get('vr_min',0) or vr>lv.get('vr_max',99): continue
        cl=(sx.get('cl',0) or 0)
        if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
        ri=real_data.get(code)
        if ri:
            hsl=(ri.get('hsl',0) or 0)
            if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
            szv=ri.get('shizhi',0) or 0
            if isinstance(szv,(int,float)) and szv>1: szv*=1e-8
            if szv>=lv.get('sz_max',99999): continue
        nm=names.get(code,'')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        nh=(sx.get('n',0) or 0)
        if nh<=0: continue
        if lv.get('a5_req',0) and (sx.get('above_ma5',0) or 0)<1: continue
        if lv.get('kdj_g_req',0) and (sx.get('kdj_golden',0) or 0)<1: continue
        if lv.get('no_macd',0) and (sx.get('macd_golden',0) or 0)>=1: continue
        pool.append({
            'code':code,'nm':names.get(code,'')[:8],'p':p,
            'cl':cl,'vr':vr,'hsl':(ri.get('hsl',0) or 0) if ri else 0,
            'dif':(sx.get('dif_val',0) or 0),'mg':(sx.get('macd_golden',0) or 0),
            'a5':(sx.get('above_ma5',0) or 0),'wrv':(sx.get('wr',0) or 0),
            'jv':(sx.get('j_val',0) or 0),'kv':(sx.get('k_val',0) or 0),
            'dv':(sx.get('d_val',0) or 0),'kdj_g':(sx.get('kdj_golden',0) or 0),
            'buy_c':(sx.get('close',0) or 0),'nh':nh,
        })
    return pool

# 评分函数 - 基于历史最优 + 失败分析
def score_real_up(stock):
    p=stock['p'];cl=stock['cl'];vr=stock['vr'];hsl=stock['hsl']
    dif=stock['dif'];mg=stock['mg'];a5=stock['a5']
    wrv=stock['wrv'];jv=stock['jv'];kv=stock['kv'];dv=stock['dv']
    kdj_g=stock['kdj_g'];buy_c=stock['buy_c']
    ms=0
    if mg and dif>0.5: ms=10
    elif mg and dif>0.2: ms=8
    elif mg: ms=6
    elif dif>0.5: ms=4
    elif dif>0: ms=2
    ps2=min(10,max(1,11-buy_c/10)) if buy_c else 0
    score = p*1.2 + cl*0.1 + ps2*0.3 + ms*0.3
    score += (3 if a5 else 0)
    score += (1.5 if 1.0<=vr<=1.5 else 0)
    score += (0.6 if 5<=hsl<=7 else 0)
    score += (2 if wrv<25 else 0)
    score += (2 if jv>kv>dv else 0)
    score += (2 if 20<=jv<=40 else 0)
    # 历史最优判断: 透支-8 / dif>0.5+3 / 金叉+3
    if p>5 and cl>80: score-=8
    if dif>0.5: score+=3
    if mg: score+=3
    # CL甜蜜区+惩罚
    if 65<=cl<=83: score+=2
    if 70<=cl<80: score-=1
    if 1.0<=vr<=1.3: score+=2
    # 失败分析: CL>85加强惩罚
    if cl>85: score-=3
    return round(score,1)

def score_down(stock):
    p=stock['p'];cl=stock['cl'];vr=stock['vr'];hsl=stock['hsl']
    dif=stock['dif'];mg=stock['mg'];a5=stock['a5']
    wrv=stock['wrv'];jv=stock['jv'];buy_c=stock['buy_c']
    ms=0
    if mg and dif>0.5: ms=10
    elif mg and dif>0.2: ms=8
    elif mg: ms=6
    elif dif>0.5: ms=4
    elif dif>0: ms=2
    ps2=min(10,max(1,11-buy_c/10)) if buy_c else 0
    score = p*1.0 + cl*0.1 + ps2*0.3 + ms*0.3
    score += (2 if a5 else 0)
    score += (4 if hsl>=5 else 0)     # 换手加分(加强)
    score += (3 if 0.6<=vr<=1.0 else 0)
    score += (3 if wrv>75 else 0)
    score += (3 if cl<15 else 0)
    score += (2 if p<-3 else 0)
    score += (3 if 50<=cl<=75 else 0)  # CL中区
    score += (-5 if cl>85 else 0)      # CL高区惩罚(加强)
    score += (-2 if p>=6 else 0)       # p透支惩罚(加强)
    score += (3 if mg else 0)          # MACD金叉加分(新增)
    return round(score,1)

def score_flat(stock):
    p=stock['p'];cl=stock['cl'];vr=stock['vr'];hsl=stock['hsl']
    dif=stock['dif'];mg=stock['mg'];a5=stock['a5']
    wrv=stock['wrv'];jv=stock['jv'];kv=stock['kv'];dv=stock['dv']
    kdj_g=stock['kdj_g'];buy_c=stock['buy_c']
    ms=0
    if mg and dif>0.5: ms=10
    elif mg and dif>0.2: ms=8
    elif mg: ms=6
    elif dif>0.5: ms=4
    elif dif>0: ms=2
    ps2=min(10,max(1,11-buy_c/10)) if buy_c else 0
    # 横盘历史最优: p×2.0 + MACD×0.2 + VR+6 + MA5+2 + J超卖+2 + KD金叉+2
    score = p*2.0 + cl*0.1 + ps2*0.3 + ms*0.2
    score += (2 if a5 else 0)
    score += (6 if 1.0<=vr<=1.5 else 0)   # 量比大加分(原+6)
    score += (2 if 20<=jv<=40 else 0)     # J超卖
    score += (2 if kdj_g else 0)          # KDJ金叉
    score += (2 if 5<=hsl<=7 else 0)      # 换手加分
    score += (2 if cl>80 else 0)          # CL高位加分(失败分析:+3.5)
    return round(score,1)

def score_fake_up(stock):
    p=stock['p'];cl=stock['cl'];vr=stock['vr'];hsl=stock['hsl']
    dif=stock['dif'];mg=stock['mg'];a5=stock['a5']
    buy_c=stock['buy_c']
    ms=0
    if mg and dif>0.5: ms=10
    elif mg and dif>0.2: ms=8
    elif mg: ms=6
    elif dif>0.5: ms=4
    elif dif>0: ms=2
    ps2=min(10,max(1,11-buy_c/10)) if buy_c else 0
    # 虚涨日极简: p×1.0 + MACD×0.5
    score = p*1.0 + cl*0.05 + ps2*0.3 + ms*0.5
    return round(score,1)

scorers = {
    'real_up': score_real_up,
    'down': score_down,
    'flat': score_flat,
    'fake_up': score_fake_up,
}
mk_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

for mk in ['real_up','down','flat','fake_up']:
    levels=mods[mk].LEVELS
    sf=scorers[mk]
    name=mk_names[mk]
    
    print(f'\n{"="*70}')
    print(f'{name}')
    print(f'{"="*70}')
    print(f'{"日期":<12} {"级":<3} {"候选":>4} {"池质%":>6} {"冠军":<10} {"今涨%":>6} {"评分":>5} {"买入":>8} {"次日最":>6}')
    print('-'*70)
    
    wins=fails=0; day_list=[]; total_days=0
    
    for dt in dates:
        s=data.get(dt,[]); m=cm(s)
        if m!=mk: continue
        total_days+=1
        
        pool=None; used_lvl=None
        for lv in levels:
            p=fl(s,lv)
            if len(p)>8: pool=p; used_lvl=lv['name']; break
        if not pool: continue
        
        pool_qual=sum(1 for x in pool if x['nh']>=2.5)
        pool_rate=pool_qual/len(pool)*100
        
        for x in pool: x['sc']=sf(x)
        pool.sort(key=lambda x: -x['sc'])
        c=pool[0]
        day_list.append(c)
        
        if c['nh']>=2.5: wins+=1
        else: fails+=1
    
    # 30天明细
    last30=day_list[-30:] if len(day_list)>=30 else day_list
    w30=sum(1 for d in last30 if d['nh']>=2.5)
    
    # 显示最后30天
    for d in last30:
        tag='✅' if d['nh']>=2.5 else '❌'
        print(f'{d["nm"]:<10} 今涨{d["p"]:+.1f}% 买入{d["buy_c"]:>8.2f} 次日最高{d["nh"]:+.1f}% {tag}')
    
    total=wins+fails
    print(f'\n  总: {total_days}天, 出票{total}/{total_days}天({total/total_days*100:.0f}%)')
    print(f'  冠军胜率: {wins/total*100:.1f}% ({wins}/{total})')
    print(f'  最近30天: {w30}/{len(last30)}={w30/len(last30)*100:.1f}%')
