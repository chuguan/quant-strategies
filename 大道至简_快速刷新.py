"""
快速更新 — 只补2026-05-25/26/27三天数据
不重建全量，只追加新日期
"""
import pickle,os,sys,json
from concurrent.futures import ThreadPoolExecutor,as_completed
dir=os.path.expanduser('~/AppData/Local/hermes/scripts')
cdir=os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(dir)

d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
new_dates=['2026-05-25','2026-05-26','2026-05-27']

codes=list(real.keys())
print(f"现有{len(codes)}只股票, 最新日期: {sorted(data.keys())[-1]}",flush=True)

def calc_stock(code):
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
    
    results={}
    for i in range(len(kdata)):
        dt=kdata[i]['date']
        if dt not in new_dates:continue
        df=kdata[:i+1];n=len(df)
        close=[r['close'] for r in df]
        high=[r['high'] for r in df]
        low=[r['low'] for r in df]
        
        nh=0
        if i+1<len(kdata):
            nh=round((kdata[i+1]['high']/kdata[i]['close']-1)*100,1)
        if i<60:continue
        
        ma5=sum(close[-5:])/5
        above_ma5=1 if close[-1]>ma5 else 0
        ema12=close[-1];ema26=close[-1]
        for j in range(n-2,max(n-27,-1),-1):
            ema12=close[j]*2/13+ema12*11/13
            ema26=close[j]*2/27+ema26*25/27
        dif=ema12-ema26;mg=1 if dif>0 else 0
        
        k_val=d_val=j_val=50;kdj_g=0
        if n>=9:
            h9=max(high[-9:]);l9=min(low[-9:])
            rsv=(close[-1]-l9)/(h9-l9+1e-10)*100
            k_val=rsv*2/3+50/3;d_val=k_val*2/3+50/3;j_val=3*k_val-2*d_val
            kdj_g=1 if k_val>d_val else 0
        
        wr=50
        if n>=21:
            h21=max(high[-21:]);l21=min(low[-21:])
            wr=100*(h21-close[-1])/(h21-l21+1e-10)
        cl=50
        if n>=20:
            h20=max(high[-20:]);l20=min(low[-20:])
            cl=(close[-1]-l20)/(h20-l20+1e-10)*100
        
        p=round((close[-1]/kdata[i-1]['close']-1)*100,2) if i>0 else 0
        vr=kdata[i]['volume']/max(kdata[i-1]['volume'],1) if i>0 else 1
        
        results[dt]={
            'code':code,'p':p,'vol_ratio':vr,'cl':round(cl,1),
            'dif_val':round(dif,3),'macd_golden':mg,'above_ma5':above_ma5,
            'wr_val':round(wr,1),'k_val':round(k_val,1),'d_val':round(d_val,1),
            'j_val':round(j_val,1),'kdj_golden':kdj_g,'n':nh,'close':close[-1],
        }
    return results

print("快速处理新日期...",flush=True)
new_entries={d:{} for d in new_dates}
done=0
with ThreadPoolExecutor(max_workers=16) as pool:
    futs={pool.submit(calc_stock,c):c for c in codes}
    for fut in as_completed(futs):
        res=fut.result()
        if res:
            for dt,item in res.items():
                if dt in new_entries:
                    new_entries[dt][item['code']]=item
        done+=1
        if done%500==0:print(f"  {done}/{len(codes)}",flush=True)

# 追加到缓存
for dt in new_dates:
    entries=[v for k,v in new_entries[dt].items()]
    if entries:
        data[dt]=entries
        ps=[e['p'] for e in entries if abs(e['p'])<15]
        ap=sum(ps)/len(ps) if ps else 0
        print(f"  {dt}: {len(entries)}只 涨幅均{ap:.2f}%",flush=True)

pickle.dump({'data':data,'real':real,'names':names},open('big_cache_full.pkl','wb'))
dates=sorted(data.keys())
print(f"\n✅ 缓存更新完成")
print(f"日期范围: {dates[0]} ~ {dates[-1]}")
print(f"总天数: {len(dates)}")
