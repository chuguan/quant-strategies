"""分而治之 V260529 自动调优引擎 v2 — 爬山法
快速：只调一个参数→测试→保留最优→继续
自动替换策略文件，带检查点可恢复
每50次迭代写心跳，看门狗15分钟检查一次
"""
import pickle, json, os, sys, importlib, time, shutil, copy, re, ast
from collections import defaultdict
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
CHECKPOINT_FILE = os.path.join(SCRIPTS_DIR, '分而治之_调优检查点.json')
RESULT_FILE = os.path.join(SCRIPTS_DIR, '分而治之_调优结果.txt')
HEARTBEAT_FILE = os.path.join(SCRIPTS_DIR, '分而治之_调优心跳.txt')
TARGET = 85.0
MIN_DAYS = 20
MAX_ITER = 5000

MARKET_NAMES = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

# ===== 1. 预建索引 =====
INDEX_FILE = os.path.join(SCRIPTS_DIR, '分而治之_日期索引.pkl')

def build_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'rb') as f:
            di = pickle.load(f)
            if len(di.get('dates',[])) > 300:
                return di
    print("📦 建日期索引...")
    with open(os.path.join(SCRIPTS_DIR,'release','分而治之','indicator_cache.pkl'),'rb') as f:
        ic = pickle.load(f)['data']
    # K线
    ck = {}
    for fn in os.listdir(CACHE_DIR):
        if not fn.endswith('.json'): continue
        cd = fn.replace('sh','').replace('sz','').replace('.json','')
        try:
            with open(os.path.join(CACHE_DIR,fn)) as f:
                k = json.load(f)
            bd = {}
            for r in k:
                bd[r['date']] = {'h':r['high'],'c':r['close']}
                bd[r['date'].replace('-','')] = {'h':r['high'],'c':r['close']}
            ck[cd] = bd
        except: pass
    # 日期索引
    fm = {'p':'p','cl':'cl','vr':'vr','dif':'dif','mg':'mg','a5':'a5',
          'wrv':'wrv','kdj_g':'kdj_g','pos_in_day':'pos_in_day',
          'close':'buy_c','j':'jv','k':'kv','d':'dv'}
    daily = defaultdict(list)
    for code, sd in ic.items():
        dl = sd['dates']
        for i, dt in enumerate(dl):
            st = {'code':code}
            for ck2, sk in fm.items():
                arr = sd.get(ck2)
                st[sk] = arr[i] if arr and i < len(arr) else 0
            # 预取次日high
            kd = ck.get(code)
            ndh = None
            if kd:
                d8 = dt.replace('-','')
                ads = sorted([d for d in kd.keys() if len(d)==8 and d.isdigit()])
                try: idx = ads.index(d8)
                except: pass
                else:
                    if idx+1 < len(ads):
                        bc = kd.get(d8,{}).get('c',0)
                        if bc > 0:
                            ndh = round((kd[ads[idx+1]]['h']/bc-1)*100,2)
            st['_nd_high'] = ndh
            daily[dt].append(st)
    di = {'daily':dict(daily), 'dates':sorted(d for d in daily if '2025-01-01'<=d<'2026-06-01')}
    with open(INDEX_FILE,'wb') as f: pickle.dump(di,f)
    print(f"  {len(di['dates'])}交易日")
    return di

DI = build_index()

# ===== 2. 行情分类 =====
def classify(stocks):
    if not stocks: return 'flat'
    ps=[s.get('p',0) for s in stocks]; vrs=[s.get('vr',0) for s in stocks if s.get('vr',0)]
    if not ps: return 'flat'
    ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
    hot=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

# ===== 3. 策略路径 =====
STRAT_FILES = {
    'real_up': os.path.join(SCRIPTS_DIR, '分而治之_真实涨日_评分策略.py'),
    'fake_up': os.path.join(SCRIPTS_DIR, '分而治之_虚涨日_评分策略.py'),
    'down': os.path.join(SCRIPTS_DIR, '分而治之_跌日_评分策略.py'),
    'flat': os.path.join(SCRIPTS_DIR, '分而治之_横盘_评分策略.py'),
}
STRAT_NAMES = {v:k for k,v in STRAT_FILES.items()}

# ===== 4. 回测（核心） =====
def load_strategy(regime):
    """从.py文件解析SCORE或PARAMS字典 + LEVELS（使用ast.literal_eval安全解析）"""
    fp = STRAT_FILES[regime]
    with open(fp) as f:
        c = f.read()
    # 优先解析PARAMS，回退到SCORE
    score = {}
    for key in ('PARAMS', 'SCORE'):
        m = re.search(rf'{key}\s*=\s*(\{{[^}}]+\}})', c, re.DOTALL)
        if m:
            raw = m.group(1)
            cleaned = re.sub(r'#[^\n]*', '', raw)
            try:
                score = ast.literal_eval(cleaned)
                break
            except Exception as e:
                print(f"  ⚠️ {key}解析失败: {e}")
    if not score:
        print(f"  ❌ 未找到PARAMS或SCORE字典")
    # 解析LEVELS
    m2 = re.search(r'LEVELS\s*=\s*(\[.*?\])', c, re.DOTALL)
    levels = []
    if m2:
        raw = re.sub(r'#[^\n]*', '', m2.group(1))
        try:
            levels = ast.literal_eval(raw)
        except:
            try:
                levels = ast.literal_eval('[' + m2.group(1) + ']')
            except:
                print(f"  ⚠️ LEVELS解析失败")
    return score, levels, c

def make_score_fn(regime, w):
    w = copy.copy(w)
    def ru(s):
        p=s['p'];cl=s['cl'];vr=s['vr'];dif=s['dif'];mg=s['mg'];a5=s['a5']
        wrv=s['wrv'];jv=s['jv'];kv=s['kv'];dv=s['dv'];bc=s['buy_c']
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        ps2=min(10,max(1,11-bc/10)) if bc else 0
        sc=p*w['p_w']+cl*w['cl_w']+ps2*0.3+ms*w['macd_w']
        sc+=(w.get('ma5_b',0) if a5 else 0)+(w.get('vr_b',0)*1.5 if 1<=vr<=1.5 else 0)
        sc+=(w.get('wr_b',0) if wrv<25 else 0)+(w.get('j_b',0) if jv>kv>dv else 0)+(w.get('j_low_b',0) if 20<=jv<=40 else 0)
        if 65<=cl<=83: sc+=3
        if 1<=vr<=1.3: sc+=3
        return round(sc,1)
    def fu(s):
        p=s['p'];cl=s['cl'];dif=s['dif'];mg=s['mg'];bc=s['buy_c']
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        ps2=min(10,max(1,11-bc/10)) if bc else 0
        return round(p*w['p_w']+cl*w['cl_w']+ps2*0.3+ms*w['macd_w'],1)
    def dn(s):
        p=s['p'];cl=s['cl'];vr=s['vr'];dif=s['dif'];mg=s['mg'];a5=s['a5']
        wrv=s['wrv'];jv=s['jv'];bc=s['buy_c'];hsl=s.get('hsl',0)
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        ps2=min(10,max(1,11-bc/10)) if bc else 0
        sc=p*w['p_w']+cl*w['cl_w']+ps2*0.3+ms*w['macd_w']
        sc+=(w.get('ma5_b',0) if a5 else 0)+(w.get('hs_bonus',0) if hsl>=5 else 0)
        sc+=(w.get('vr_bonus',0) if 0.6<=vr<=1.0 else 0)+(w.get('wr_bonus',0) if wrv>75 else 0)
        sc+=(w.get('cl_low_b',0) if cl<15 else 0)+(w.get('p_deep_b',0) if p<-3 else 0)
        sc+=(w.get('zone_b',0) if 50<=cl<=75 else 0)+(w.get('cl_high_pen',0) if cl>85 else 0)
        sc+=(w.get('p_high_pen',0) if p>=6.5 else 0)
        return round(sc,1)
    def fl(s):
        p=s['p'];cl=s['cl'];vr=s['vr'];dif=s['dif'];mg=s['mg'];a5=s['a5']
        jv=s['jv'];kv=s['kv'];dv=s['dv'];kdj_g=s['kdj_g'];bc=s['buy_c'];hsl=s.get('hsl',0)
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        ps2=min(10,max(1,11-bc/10)) if bc else 0
        sc=p*w['p_w']+cl*w['cl_w']+ps2*0.3+ms*w['macd_w']
        sc+=(w.get('ma5_b',0) if a5 else 0)+(w.get('vr_b',0)*1.5 if 1<=vr<=1.5 else 0)
        sc+=(w.get('j_low_b',0) if 20<=jv<=40 else 0)+(2 if kdj_g else 0)
        if dif>0.5: sc+=3
        if mg: sc+=3
        return round(sc,1)
    return {'real_up':ru,'fake_up':fu,'down':dn,'flat':fl}[regime]

def run_bt(regime, score_weights, levels):
    """30天回测"""
    daily=DI['daily']; dates=DI['dates']
    fn=make_score_fn(regime,score_weights)
    mkt_dates=[]
    for dt in dates:
        ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
        if ss and classify(ss)==regime:
            mkt_dates.append(dt)
    target=mkt_dates[-30:] if len(mkt_dates)>=30 else mkt_dates
    if len(target)<MIN_DAYS: return 0,0,0.0,target
    wins=total=0
    for dt in target:
        ss=[s for s in daily.get(dt,[]) if abs(s.get('p',0))<9.98]
        if not ss: continue
        cands=[]
        for lv in levels:
            pmax=lv.get('p_max',8)
            pool=[s for s in ss if lv.get('p_min',-10)<=s.get('p',0)<=pmax and s.get('p',0)<8]
            if len(pool)>=8:
                cands=pool[:200]; break
        if not cands: cands=[s for s in ss if -10<=s.get('p',0)<8][:200]
        if not cands: continue
        scored=[(fn(s),s) for s in cands]
        scored.sort(key=lambda x:-x[0])
        if not scored: continue
        nh=scored[0][1].get('_nd_high')
        if nh is not None and nh>=2.5: wins+=1
        total+=1
    return wins,total,round(wins/total*100,1) if total else 0,target

# ===== 5. 爬山法优化 =====
def hill_climb(regime, base_w, levels, max_iter=MAX_ITER):
    print(f"\n{'='*60}")
    print(f"  🎯 {MARKET_NAMES[regime]}: 爬山法优化")
    print(f"{'='*60}")
    
    best_w=copy.deepcopy(base_w)
    _,_,best_rate,td=run_bt(regime,best_w,levels)
    print(f"  基线: {best_rate}% ({len(td)}天)")
    
    if best_rate>=TARGET:
        return best_w,best_rate,True
    
    # 参数调优范围
    adj_ranges={}
    for k,v in base_w.items():
        if isinstance(v,(int,float)):
            if k in ['p_w','macd_w','cl_w']:
                adj_ranges[k]=[round(v*0.5,1),round(v*0.75,1),v,round(v*1.25,1),round(v*1.5,1),
                              round(v*2,1),round(v*3,1),round(v*4,1)]
            elif k in ['vr_b','ma5_b','wr_b','j_b','j_low_b','hs_b']:
                adj_ranges[k]=[0,1,2,3,5,8]
            elif 'pen' in k or 'bonus' in k:
                adj_ranges[k]=[0,2,3,5,8]
                if v<0:
                    adj_ranges[k]=[-8,-5,-3,-2,0]
            else:
                adj_ranges[k]=[max(0,int(v)-2),max(0,int(v)-1),int(v),int(v)+1,int(v)+2,int(v)+5]
    
    it=0
    improved=True
    while improved and it<max_iter:
        improved=False
        it+=1
        
        for param,values in adj_ranges.items():
            for val in values:
                if val==best_w.get(param): continue
                test=copy.deepcopy(best_w)
                test[param]=val
                _,_,rate,_=run_bt(regime,test,levels)
                if rate>best_rate:
                    best_w[param]=val
                    best_rate=rate
                    improved=True
                    print(f"  ⬆️ [{it}] {param}={val} → {rate}%")
                    if rate>=TARGET:
                        print(f"  🎉 达标! {rate}%")
                        return best_w,best_rate,True
                    break  # 调下一个参数
        
        # 心跳
        if it%10==0:
            with open(HEARTBEAT_FILE,'w') as f:
                f.write(f"{datetime.now().isoformat()}|{regime}|{it}|{best_rate}")
    
    print(f"  结束: {best_rate}% ({it}次)")
    return best_w,best_rate,best_rate>=TARGET

# ===== 6. 写入策略文件 =====
def write_strat(regime, new_w, rate):
    fp=STRAT_FILES[regime]
    with open(fp) as f: c=f.read()
    
    # 替换 PARAMS 或 SCORE 字典
    items=[]
    for k,v in new_w.items():
        if isinstance(v,float):
            items.append(f"    '{k}': {v}")
        else:
            items.append(f"    '{k}': {v}")
    new_dict = "{\n"+",\n".join(items)+",\n}"
    # 优先替换PARAMS，回退到SCORE
    if re.search(r'PARAMS\s*=', c):
        c = re.sub(r'PARAMS\s*=\s*\{[^}]+\}', f'PARAMS = {new_dict}', c, flags=re.DOTALL)
    else:
        c = re.sub(r'SCORE\s*=\s*\{[^}]+\}', f'SCORE = {new_dict}', c, flags=re.DOTALL)
    
    # 更新BACKTEST
    ver=f"auto-opt_{datetime.now().strftime('%H%M')}_{rate}%"
    c=re.sub(r'BACKTEST\s*=\s*"[^"]*"', f'BACKTEST = "{ver}"', c)
    
    with open(fp,'w') as f: f.write(c)
    # 清缓存
    pyc=os.path.join(SCRIPTS_DIR,'__pycache__')
    for fn in os.listdir(pyc):
        if os.path.basename(fp).replace('.py','') in fn:
            os.remove(os.path.join(pyc,fn))
    print(f"  📝 已更新: {os.path.basename(fp)} → {ver}")

# ===== 6a. PARAMS标准化 =====
KEY_MAP = {
    'a5_b': 'ma5_b',
    'wr_lo_b': 'wr_b',
    'wr_hi_b': 'wr_hi_b',
    'j_golden_b': 'j_b',
    'j_zone_b': 'j_low_b',
    'j_super_b': 'j_super_b',
    'dif_bonus': 'dif_bonus',
    'pos_hi_pen': 'p_high_pen',
    'pos_lo_b': 'pos_lo_b',
    'vr_zones': None,
    'cl_zones': None,
}

def normalize_params(sc):
    """将PARAMS格式的键名映射到optimizer期望的键名，补全缺失键"""
    out = {}
    for k, v in sc.items():
        # 跳过非权重键
        if k in ('use_p','use_cl','use_vr','use_macd','use_a5','use_wr','use_kdj','use_kdj_g','use_pos',
                 'cl_zones','vr_zones'):
            continue
        mapped = KEY_MAP.get(k, k)
        if mapped:  # None means skip
            out[mapped] = v
    # 为optimizer补全默认值（防止KeyError）
    defaults = {
        'p_w': 0, 'cl_w': 0, 'macd_w': 0, 'ma5_b': 0, 'vr_b': 0,
        'wr_b': 0, 'j_b': 0, 'j_low_b': 0, 'hs_bonus': 0, 'hs_b': 0,
        'vr_bonus': 0, 'wr_bonus': 0, 'cl_low_b': 0, 'p_deep_b': 0,
        'zone_b': 0, 'cl_high_pen': 0, 'p_high_pen': 0,
    }
    for k, v in defaults.items():
        if k not in out:
            out[k] = v
    return out

# ===== 7. 主循环 =====
def main():
    print(f"{'='*60}")
    print(f"  分而治之 自动调优 v2")
    print(f"  目标: 4行情 × {TARGET}%")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    # 写心跳
    with open(HEARTBEAT_FILE,'w') as f:
        f.write(f"{datetime.now().isoformat()}|start")
    
    results={}
    all_done=True
    
    for regime in ['real_up','fake_up','down','flat']:
        print(f"\n{'─'*50}")
        print(f"  📊 {MARKET_NAMES[regime]}")
        
        sc, levels, _ = load_strategy(regime)
        if not sc:
            print(f"  ❌ 无法解析策略文件")
            all_done=False; continue
        
        # 将PARAMS格式标准化为optimizer期望格式
        sc = normalize_params(sc)
        
        _,_,base_rate,td=run_bt(regime,sc,levels)
        print(f"  当前: {base_rate}% ({len(td)}天) 目标={TARGET}%")
        
        if base_rate>=TARGET:
            print(f"  ✅ 已达标!")
            results[regime]=base_rate
            continue
        
        all_done=False
        best_w, best_rate, achieved = hill_climb(regime, sc, levels)
        
        if best_rate>base_rate:
            write_strat(regime, best_w, best_rate)
        results[regime]=best_rate
        
        # 检查点
        cp={}
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE) as f: cp=json.load(f)
        cp[regime]={'rate':best_rate,'time':datetime.now().isoformat(),'achieved':achieved}
        with open(CHECKPOINT_FILE,'w') as f: json.dump(cp,f,ensure_ascii=False,indent=2)
    
    # 总结
    print(f"\n{'='*60}")
    print(f"  结果汇总")
    print(f"{'='*60}")
    for k,v in results.items():
        print(f"  {MARKET_NAMES[k]}: {v}%{' ✅' if v>=TARGET else ' ❌'}")
    
    total_ok=sum(1 for v in results.values() if v>=TARGET)
    print(f"\n  达标: {total_ok}/4行情")
    
    with open(RESULT_FILE,'w') as f:
        f.write(f"{datetime.now().isoformat()}\n")
        f.write(f"达标: {total_ok}/4\n")
        for k,v in results.items():
            f.write(f"{k}: {v}%\n")
    
    return total_ok==4

if __name__=='__main__':
    done=main()
    # 让外部看门狗(watchdog)负责重启
    sys.exit(0 if done else 1)
