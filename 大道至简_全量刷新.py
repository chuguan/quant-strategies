"""
全量刷新 big_cache_full.pkl — 用已有K线缓存重新计算最新日期指标
"""
import pickle,os,sys,json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
dir=os.path.expanduser('~/AppData/Local/hermes/scripts')
cdir=os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(dir)
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']

# 找出所有有K线缓存的股票
all_codes=list(real.keys())
print(f"已有{len(all_codes)}只股票",flush=True)

# 更新实时数据（从qt.gtimg.cn）
import subprocess
def curl(u,t=10):
    try:
        r=subprocess.run(['curl','-s','--max-time',str(t),u],capture_output=True,timeout=t+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

print("刷新实时数据...",flush=True)
for i in range(0,len(all_codes),80):
    chunk=all_codes[i:i+80]
    syms=[f'sh{c}' if c.startswith(('6','9')) else f'sz{c}' for c in chunk]
    text=curl(f'https://qt.gtimg.cn/q={",".join(syms)}',8)
    for line in text.split('\n'):
        if '~' not in line:continue
        p=line.split('~')
        if len(p)<46:continue
        try:
            c=p[2]
            if c not in real:continue
            nm=p[1]
            if 'ST' in nm or '*ST' in nm or '退' in nm:continue
            hsl=0
            try: hsl=float(p[46]) if p[46] and float(p[46])<100 else 0
            except: pass
            sz=0
            try: sz=float(p[44])/1e8 if p[44] else 0
            except: pass
            pe=0
            try: pe=float(p[39]) if p[39] else 0
            except: pass
            real[c]={'hsl':hsl,'pe':pe,'shizhi':sz}
            names[c]=p[1]
        except: pass
print(f"实时数据: {len(real)}只",flush=True)

# 处理K线数据
def calc_all(code):
    """从K线JSON计算所有日期的完整指标"""
    mkt='sh' if code.startswith(('6','9')) else 'sz'
    fp=os.path.join(cdir,f'{mkt}{code}.json')
    if not os.path.exists(fp):
        fp2=os.path.join(cdir,f'{code}.json')
        if os.path.exists(fp2):fp=fp2
        else:return None
    try:
        with open(fp) as f:kdata=json.load(f)
    except:return None
    if not kdata or len(kdata)<80:return None
    
    results=[]
    for i in range(len(kdata)):
        df=kdata[:i+1];n=len(df)
        close=[r['close'] for r in df]
        high=[r['high'] for r in df]
        low=[r['low'] for r in df]
        dt=kdata[i]['date']
        
        # n = 次日最高涨幅
        nh=0
        if i+1<len(kdata):
            nh=round((kdata[i+1]['high']/kdata[i]['close']-1)*100,1)
        
        # 基础指标
        if n<60: continue
        
        ma5=sum(close[-5:])/5 if n>=5 else close[-1]
        above_ma5=1 if close[-1]>ma5 else 0
        
        # MACD
        ema12=close[-1];ema26=close[-1]
        for j in range(n-2,max(n-27,-1),-1):
            ema12=close[j]*2/13+ema12*11/13
            ema26=close[j]*2/27+ema26*25/27
        dif=ema12-ema26;dea=dif;mg=1 if dif>0 else 0
        
        # KDJ
        k_val=d_val=j_val=50;kdj_g=0
        if n>=9:
            h9=max(high[-9:]);l9=min(low[-9:])
            rsv=(close[-1]-l9)/(h9-l9+1e-10)*100
            k_val=rsv*2/3+50/3;d_val=k_val*2/3+50/3;j_val=3*k_val-2*d_val
            kdj_g=1 if k_val>d_val else 0
        
        # WR
        wr=50
        if n>=21:
            h21=max(high[-21:]);l21=min(low[-21:])
            wr=100*(h21-close[-1])/(h21-l21+1e-10)
        
        # CL
        cl=50
        if n>=20:
            h20=max(high[-20:]);l20=min(low[-20:])
            cl=(close[-1]-l20)/(h20-l20+1e-10)*100
        
        results.append({
            'date':dt,'close':close[-1],'n':nh,
            'p':round((close[-1]/kdata[i-1]['close']-1)*100,2) if i>0 else 0,
            'vol_ratio':kdata[i]['volume']/kdata[i-1]['volume'] if i>0 and kdata[i-1]['volume']>0 else 1,
            'cl':round(cl,1),'dif_val':round(dif,3),'macd_golden':mg,
            'above_ma5':above_ma5,'wr_val':round(wr,1),
            'k_val':round(k_val,1),'d_val':round(d_val,1),'j_val':round(j_val,1),
            'kdj_golden':kdj_g,'name':names.get(code,'')
        })
    return results

print("全量处理K线数据...",flush=True)
all_results={}
with ThreadPoolExecutor(max_workers=12) as pool:
    futs={pool.submit(calc_all,c):c for c in all_codes}
    done=0
    for fut in as_completed(futs):
        code=futs[fut]
        res=fut.result()
        if res:
            for r in res:
                dt=r['date']
                if dt not in all_results:
                    all_results[dt]={}
                all_results[dt][code]=r
        done+=1
        if done%300==0:
            print(f"  {done}/{len(all_codes)}",flush=True)

# 重新构造data字典
new_data={}
for dt in sorted(all_results.keys()):
    if dt<'2025-01-01':continue
    new_data[dt]=[]
    for code,r in all_results[dt].items():
        new_data[dt].append({
            'code':code,
            'p':r['p'],
            'vol_ratio':r['vol_ratio'],
            'cl':r['cl'],
            'dif_val':r['dif_val'],
            'macd_golden':r['macd_golden'],
            'above_ma5':r['above_ma5'],
            'wr_val':r['wr_val'],
            'k_val':r['k_val'],
            'd_val':r['d_val'],
            'j_val':r['j_val'],
            'kdj_golden':r['kdj_golden'],
            'n':r['n'],
            'close':r['close'],
        })

pickle.dump({'data':new_data,'real':real,'names':names},open('big_cache_full.pkl','wb'))
dates=sorted(new_data.keys())
print(f"\n✅ 缓存重建完成")
print(f"日期范围: {dates[0]} ~ {dates[-1]}")
print(f"总天数: {len(dates)}")
print(f"最新5天:")
for dt in dates[-5:]:
    ss=new_data[dt]
    ps=[s['p'] for s in ss if abs(s['p'])<15]
    ap=sum(ps)/len(ps) if ps else 0
    print(f"  {dt}: {len(ss)}只 涨幅均{ap:.2f}%")
