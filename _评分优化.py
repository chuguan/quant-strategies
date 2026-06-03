"""
评分优化: 对4行情逐个测试最优评分权重
输出: 最佳评分参数 + 30天逐日明细
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

def classify_mkt(stocks):
    ps=[s.get('p',0) or 0 for s in stocks]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps)
    vrs=[s.get('vol_ratio',0) or 0 for s in stocks if s.get('vol_ratio',0)]
    av=sum(vrs)/len(vrs) if vrs else 0
    ht=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if ht<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

# 加载子策略
mods = {
    'real_up': importlib.import_module('大道至简_真实涨日_评分策略'),
    'fake_up': importlib.import_module('大道至简_虚涨日_评分策略'),
    'down': importlib.import_module('大道至简_跌日_评分策略'),
    'flat': importlib.import_module('大道至简_横盘_评分策略'),
}

def filter_level(s_list, lv):
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

def test_scoring(mk, score_fn, label):
    """用指定评分函数跑全量回测"""
    levels=mods[mk].LEVELS
    wins=fails=0
    day_list=[]
    
    for dt in dates:
        s=data.get(dt,[])
        m=classify_mkt(s)
        if m!=mk: continue
        
        pool=None
        for lv in levels:
            p=filter_level(s, lv)
            if len(p)>8: pool=p; break
        
        if not pool: continue
        
        for x in pool: x['sc']=score_fn(x)
        pool.sort(key=lambda x: -x['sc'])
        c=pool[0]
        
        if c['nh']>=2.5:
            wins+=1
        else:
            fails+=1
        day_list.append(c)
    
    total=wins+fails
    rate=wins/total*100 if total else 0
    
    # 30天明细
    last30=day_list[-30:] if len(day_list)>=30 else day_list
    w30=sum(1 for d in last30 if d['nh']>=2.5)
    
    return rate, wins, total, last30

# ===== 跌日评分优化 =====
print('=== 跌日 评分优化 ===')
from 大道至简_跌日_评分策略 import 跌日_评分 as orig_down_fn
# 测试权重调整
best_rate=0; best_fn=None; best_label=''
# 测试改变权重
for p_w in [1.0, 1.5]:
    for cl_w in [0.1, 0.2]:
        for ma5_b in [2, 4]:
            for hs_bonus in [2, 4]:
                for cl_high_pen in [-3, -5]:
                    # 构建新评分函数
                    def make_down(pw,clw,m5b,hsb,chp):
                        def fn(stock):
                            p=stock['p']; cl=stock['cl']; vr=stock['vr']; hsl=stock['hsl']
                            dif=stock['dif']; mg=stock['mg']; a5=stock['a5']
                            wrv=stock['wrv']; jv=stock['jv']
                            buy_c=stock['buy_c']
                            ms=0
                            if mg and dif>0.5: ms=10
                            elif mg and dif>0.2: ms=8
                            elif mg: ms=6
                            elif dif>0.5: ms=4
                            elif dif>0: ms=2
                            ps2=min(10,max(1,11-buy_c/10)) if buy_c else 0
                            score=p*pw + cl*cl_w + ps2*0.3 + ms*0.3
                            score+=(m5b if a5 else 0)
                            score+=(hsb if hsl>=5 else 0)
                            score+=(3 if 0.6<=vr<=1.0 else 0)
                            score+=(3 if wrv>75 else 0)
                            score+=(3 if cl<15 else 0)
                            score+=(2 if p<-3 else 0)
                            score+=(3 if 50<=cl<=75 else 0)
                            score+=(chp if cl>85 else 0)
                            if p>=6.5: score-=1
                            return round(score,1)
                        return fn
                    fn=make_down(pw,pw,m5b,hsb,chp)
                    lbl=f'p{pw}_cl{cl_w}_m5{m5b}_hs{hsb}_pen{chp}'
                    rate,w,t,last30=test_scoring('down',fn,lbl)
                    if rate>best_rate:
                        best_rate=rate; best_fn=fn; best_label=lbl
                        print(f'  新最佳: {rate:.1f}%  {w}/{t}  {lbl}')

# 跌日最终结果
rate_dn,w_dn,t_dn,last30_dn=test_scoring('down',best_fn,'最佳')
print(f'\n跌日最终: {rate_dn:.1f}% ({w_dn}/{t_dn})')
for d in last30_dn:
    tag='✅' if d['nh']>=2.5 else '❌'
    print(f'  {d["nm"]:<10} 今涨{d["p"]:+.1f}% 买入{d["buy_c"]:>8.2f} 次日最高{d["nh"]:+.1f}% {tag}')
