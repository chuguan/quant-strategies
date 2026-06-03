#!/usr/bin/env python3
"""V42 vs V46 最近30个交易日对比"""
import sys,os,importlib,sqlite3
import numpy as np

SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0,SCRIPTS_DIR)

def load(d,label):
    s={}
    for n in ['真实涨日','虚涨日','跌日','横盘']:
        fp=os.path.join(d,f'分而治之_V10_{n}_评分策略.py')
        spec=importlib.util.spec_from_file_location(f'{label}_{n}',fp)
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        s[n]=m
    return s

v42s=load(os.path.join(SCRIPTS_DIR,'release','V42','评分策略'),'V42')
v46s=load(os.path.join(SCRIPTS_DIR,'release','V46','评分策略'),'V46')
MK={'real_up':'真实涨日','fake_up':'虚涨日','down':'跌日','flat':'横盘'}

def cm(ps,vrs):
    ap=sum(ps)/len(ps) if ps else 0
    av=sum(vrs)/len(vrs) if vrs else 0
    h=sum(1 for p in ps if 5<=p<=8)
    if ap>0.5: return 'fake_up' if h<15 or av<0.9 else 'real_up'
    if ap<-0.5: return 'down'
    return 'flat'

conn=sqlite3.connect(os.path.join(SCRIPTS_DIR,'v13_quant.db'),timeout=5)
all_dates=[r[0] for r in conn.execute('SELECT DISTINCT date FROM data_cache WHERE n IS NOT NULL AND n!=0 ORDER BY date').fetchall()]
recent_30=all_dates[-30:]
print(f'最近30个交易日: {len(recent_30)}天 ({recent_30[0]} ~ {recent_30[-1]})')

v42w=0;v46w=0;v42t=0;v46t=0;td=0
for d in recent_30:
    rows=conn.execute('SELECT code,name,p,vr,cl,wr_val,dif_val,macd_golden,kdj_golden,j_val,k_val,d_val,above_ma5,close,n FROM data_cache WHERE date=? AND p<9 AND n IS NOT NULL AND n!=0',(d,)).fetchall()
    if not rows: continue
    ps=[r[2] for r in rows if abs(r[2])<15]
    vrs=[r[3] for r in rows if r[3]>0 and r[3]<5]
    mk_cn=MK.get(cm(ps,vrs),'横盘')
    vm=v42s.get(mk_cn);vm2=v46s.get(mk_cn)
    if not vm or not vm2: continue
    
    v42sc=[];v46sc=[]
    for r in rows:
        code,name,p,vr,cl,wr,dif,mg,kg,jv,kv,dv,a5,close,n=r
        st={'p':p or 0,'vr':vr or 0,'cl':cl or 50,'wrv':wr or 50,'dif':dif or 0,'mg':mg or 0,'kdj_g':kg or 0,'jv':jv or 50,'kv':kv or 50,'dv':dv or 50,'a5':a5 or 0,'close':close or 0,'hsl':0,'pos_in_day':50,'nm':name,'name':name,'t4_shadow':0,'slope5':0,'cons_up':0}
        t=1 if n>=2.5 else 0
        s1=vm.score(st);s2=vm2.score(st)
        if s1>0: v42sc.append({'n':name,'s':s1,'t':t})
        if s2>0: v46sc.append({'n':name,'s':s2,'t':t})
    if len(v42sc)<3 or len(v46sc)<3: continue
    
    v42sc.sort(key=lambda x:x['s'],reverse=True)
    v46sc.sort(key=lambda x:x['s'],reverse=True)
    td+=1
    if v42sc[0]['t']: v42w+=1
    if v46sc[0]['t']: v46w+=1
    if any(x['t'] for x in v42sc[:3]): v42t+=1
    if any(x['t'] for x in v46sc[:3]): v46t+=1

print()
print(f'===== 最近{td}个交易日 V42 vs V46 =====')
print(f'数据源: data_cache')
print()
h1='#1冠军胜率'
h2='TOP3至少1达标'
print(f'{"指标":<20}  {"V42":>16}  {"V46":>16}  {"差异":>8}')
print('-'*68)
print(f'{h1:<20}  {v42w:>3}/{td:<3} ={v42w/td*100:>5.1f}%  {v46w:>3}/{td:<3} ={v46w/td*100:>5.1f}%  {v46w/td*100-v42w/td*100:+>+5.1f}%')
print(f'{h2:<20}  {v42t:>3}/{td:<3} ={v42t/td*100:>5.1f}%  {v46t:>3}/{td:<3} ={v46t/td*100:>5.1f}%  {v46t/td*100-v42t/td*100:+>+5.1f}%')

conn.close()
