#!/usr/bin/env python3
"""V13_日报.py 完整回测框架 + V14评分策略 对比"""
import os, sys

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# 导入V13_日报.py的全部逻辑
import V13_日报 as V13_MODULE

# 用V14的评分模块替换V13的
import importlib
V14_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V14')
V14_STRATS = {}
for n in ['真实涨日','虚涨日','跌日','横盘']:
    fp = os.path.join(V14_DIR, '评分策略', f'分而治之_V10_{n}_评分策略.py')
    spec = importlib.util.spec_from_file_location(n, fp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    V14_STRATS[n] = m

# 重写backtest_30d使用V14评分
def backtest_v14():
    """同V13_日报.py的backtest_30d，但用V14评分模块"""
    import sqlite3
    from datetime import datetime, timedelta
    
    DB_PATH = os.path.join(SCRIPTS_DIR, 'v13_quant.db')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    
    # 数据源只用 tencent:1450 或 big_cache（过滤掉测试数据）
    c.execute('SELECT DISTINCT date FROM data_cache WHERE close>0 ORDER BY date')
    all_dates = [r[0] for r in c.fetchall()]
    recent = all_dates[-30:]
    extended = all_dates[all_dates.index(recent[0])-6:all_dates.index(recent[-1])+1] if len(recent)>0 else []
    
    data = {}
    for dt in extended:
        c.execute('SELECT * FROM data_cache WHERE date=?', (dt,))
        cols = [d[0] for d in c.description]
        data[dt] = [dict(zip(cols, row)) for row in c.fetchall()]
    
    features = {}
    for dt in recent:
        c.execute('SELECT * FROM features_cache WHERE date=?', (dt,))
        fcols = [d[0] for d in c.description]
        for row in c.fetchall():
            f = dict(zip(fcols, row))
            features[(f['code'], dt)] = f
    
    c.execute('SELECT code, hsl, shizhi FROM data_stock_info')
    stock_info = {r[0]: {'hsl': r[1] or 0, 'shizhi': r[2] or 0} for r in c.fetchall()}
    conn.close()
    
    def mkt_class(ss):
        if not ss: return 'flat'
        ps=[s.get('p',0) or 0 for s in ss]
        vrs=[s.get('vr',0) or 1 for s in ss if s.get('vr',0)]
        ap=sum(ps)/len(ps); av=sum(vrs)/len(vrs) if vrs else 0
        hot=sum(1 for p in ps if 5<=p<=8)
        if ap>0.5: return 'fake_up' if hot<15 or av<0.9 else 'real_up'
        if ap<-0.5: return 'down'
        return 'flat'
    
    # ===== V13原版6条动量衰竭规则 =====
    def is_momentum_exhausted(s,code,dt):
        feats=features.get((code,dt),{})
        if not feats: return False
        sl5=feats.get('slope5',0); t4s=feats.get('t4_shadow',0); cu=feats.get('cons_up',0)
        pk=feats.get('peak_decay',0); pv=s.get('p',0) or 0
        if sl5>8 and t4s>25: return True
        if sl5>10 and t4s>18: return True
        if cu>=5 and sl5>15: return True
        if pk>5 and sl5>5 and pv<6: return True
        if sl5>5 and t4s>30: return True
        if cu>=4 and sl5>10 and pv<7: return True
        return False
    
    # ===== V13原版7天衰减扣分 =====
    def compute_7day_penalty(code,dt,p_today):
        ad=sorted(data.keys())
        try: idx=ad.index(dt)
        except: return 0
        prev=ad[max(0,idx-6):idx]
        gains=[]
        for pd in prev:
            found=False
            for s in data.get(pd,[]):
                if s['code']==code: gains.append(s.get('p',0) or 0); found=True; break
            if not found: gains.append(0)
        gains.append(p_today)
        n=len(gains)
        if n<5: return 0
        d6,d5,d4,d3,d2,d1,p=gains[-7:] if n>=7 else [0]*(7-n)+gains[-n:]
        p_is_max=p>=max(gains[:-1]); avg_7d=sum(gains)/n
        penalty=0; wrv=50
        for s in data.get(dt,[]):
            if s['code']==code: wrv=s.get('wr_val',50) or s.get('wrv',50); break
        if wrv<10 and p_is_max and avg_7d<2.0 and p<6: penalty-=8
        if p_is_max and avg_7d<0.8 and p<8:
            if avg_7d<0: penalty-=15
            elif avg_7d<0.3: penalty-=12
            elif avg_7d<0.7: penalty-=8
            else: penalty-=5
        if d1<-1.5 and d2<-1.0 and p>3 and avg_7d<1.0: penalty-=8
        if max(d4,d3,d2)>5 and d1<0 and d2<0: penalty-=10
        if n>=5 and d5>d1 and d5>d2 and p<=d5:
            recent_sum=(d4+d3+d2+d1) if n>=6 else (d3+d2+d1)
            if recent_sum<=2: penalty-=8
        if n>=5:
            last5=gains[-5:]
            if all(last5[i]>=last5[i+1] for i in range(len(last5)-1)): penalty-=10
        return penalty
    
    def score_v14(s,code,dt,mk_cn):
        """用V14评分 + V13的7天衰减扣分"""
        mod=V14_STRATS[mk_cn]
        stock={}
        stock['p']=s.get('p',0) or 0; stock['cl']=s.get('cl',50)
        stock['vr']=s.get('vr',1) or s.get('vol_ratio',1)
        stock['dif']=s.get('dif_val',0) or s.get('dif',0)
        stock['mg']=s.get('macd_golden',0) or s.get('mg',0)
        stock['wrv']=s.get('wr_val',0) or s.get('wrv',50)
        stock['jv']=s.get('j_val',0) or s.get('jv',50)
        stock['kv']=s.get('k_val',0) or s.get('kv',50)
        stock['dv']=s.get('d_val',0) or s.get('dv',50)
        stock['a5']=s.get('above_ma5',0); stock['kdj_g']=s.get('kdj_golden',0) or s.get('kdj_g',0)
        stock['pos_in_day']=s.get('pos_in_day',50)
        stock['nm']=s.get('name','') or ''
        si=stock_info.get(code,{}); stock['hsl']=si.get('hsl',0) or 0
        feats=features.get((code,dt),{})
        stock['t4_shadow']=feats.get('t4_shadow',0); stock['slope5']=feats.get('slope5',0)
        stock['cons_up']=feats.get('cons_up',0)
        stock['d1']=feats.get('d1',0); stock['d2']=feats.get('d2',0); stock['d3']=feats.get('d3',0)
        penalty=compute_7day_penalty(code,dt,s.get('p',0) or 0)
        return round(mod.score(stock)+penalty,1)
    
    MK_MAP = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}
    LO = ['L0','L1','L2','L3','L4']
    
    wi=0; ta=0; mk_s={'real_up':[0,0],'fake_up':[0,0],'down':[0,0],'flat':[0,0]}
    
    for dt in recent:
        ss=data.get(dt,[]); ss=[s for s in ss if (s.get('p',0) or 0)<15]
        if not ss: continue
        mk=mkt_class(ss); mk_cn=MK_MAP.get(mk,'横盘')
        mod=V14_STRATS[mk_cn]; levels=mod.LEVELS
        lm={l['name']:i for i,l in enumerate(levels)}
        pool=None
        for ln in LO:
            if ln not in lm: continue
            i=lm[ln]; lv=levels[i]; cand=[]
            for s in ss:
                p=s.get('p',0) or 0
                if p<lv['p_min'] or p>min(lv.get('p_max',10),8): continue
                vr=s.get('vr',0) or s.get('vol_ratio',0) or 0
                if vr<lv['vr_min'] or vr>lv['vr_max']: continue
                si=stock_info.get(s['code'],{}); hsl=si.get('hsl',0) or 0
                if hsl<lv.get('hs_min',0) or hsl>lv.get('hs_max',99): continue
                if (si.get('shizhi',0) or 0)>=lv.get('sz_max',9999): continue
                nm=s.get('name','')
                if 'ST' in nm or '*ST' in nm or '退' in nm: continue
                cl=s.get('cl',0)
                if cl<lv.get('cl_min',0) or cl>lv.get('cl_max',100): continue
                if is_momentum_exhausted(s,s['code'],dt): continue
                cand.append(s)
            if len(cand)>=10: pool=cand; break
        if not pool: continue
        
        scored=[(score_v14(s,s['code'],dt,mk_cn),s) for s in pool]
        scored.sort(key=lambda x:-x[0])
        champ=scored[0][1]; nh=champ.get('n',0) or 0
        ta+=1; mk_s[mk][1]+=1
        if nh>=2.5: wi+=1; mk_s[mk][0]+=1
    
    return wi, ta, mk_s, recent[-1]

# 跑V13原版 和 V14(原版框架)
print('▶ 回测中（30天）...')

# V13原版（直接用V13_日报.py的backtest_30d）
v13_wi, v13_ta, v13_mk_s, _, v13_t3, _ = V13_MODULE.backtest_30d()
v13_w = sum(v13_mk_s[k][0] for k in v13_mk_s)
v13_t = sum(v13_mk_s[k][1] for k in v13_mk_s)

# V14 + V13完整框架
v14_wi, v14_ta, v14_mk_s, v14_last = backtest_v14()
v14_w = sum(v14_mk_s[k][0] for k in v14_mk_s)
v14_t = sum(v14_mk_s[k][1] for k in v14_mk_s)

print()
print(f'{"版本":>15} | {"30天胜率":>15} | {"冠军":>12} | {"亚军":>12} | {"季军":>12}')
print('-' * 70)
mk_names = {'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

# Show V13 results
v13_wins = [sum(1 for r in v13_t3 if r['nh']>=2.5)]
v13_tot = len(v13_t3)
print(f'{"V13(原版)":>15} | {v13_w*100//v13_t}% ({v13_w}/{v13_t})')
for k, cn in mk_names.items():
    w = v13_mk_s[k][0]; t = v13_mk_s[k][1]
    if t>0: print(f'{"":>15}   {cn}: {w}/{t}={w*100//t}%')

# Show V14 results (we don't have per-rank from V14 backtest, just total)
print(f'{"V14+原版框架":>15} | {v14_w*100//v14_t}% ({v14_w}/{v14_t})')
for k, cn in mk_names.items():
    w = v14_mk_s[k][0]; t = v14_mk_s[k][1]
    if t>0: print(f'{"":>15}   {cn}: {w}/{t}={w*100//t}%')

print(f'\n✅ 完成 (数据截至 {v14_last})')
