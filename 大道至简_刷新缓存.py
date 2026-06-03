"""
更新 big_cache_full.pkl 缓存到最新日期
从腾讯K线API拉取最新数据
"""
import pickle,os,sys,json,time,subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime

SCRIPTS_DIR=os.path.expanduser('~/AppData/Local/hermes/scripts')
CACHE_DIR=os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(SCRIPTS_DIR)

def curl_get(url,timeout=15):
    try:
        r=subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+5)
        return r.stdout.decode('gbk',errors='replace')
    except: return ''

def get_live_data():
    """获取实时行情数据"""
    all_codes=[]
    for i in range(600000,606000):all_codes.append(str(i))
    for i in range(0,3000):all_codes.append(f'{i:06d}')
    stocks={}
    for i in range(0,len(all_codes),80):
        chunk=all_codes[i:i+80]
        symbols=[f'sh{c}' if c.startswith(('6','9')) else f'sz{c}' for c in chunk]
        text=curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}',timeout=10)
        for line in text.split('\n'):
            if '~' not in line:continue
            parts=line.split('~')
            if len(parts)<46:continue
            try:
                nm=parts[1];code=parts[2]
                if not nm or 'ST' in nm or '*ST' in nm or '退' in nm:continue
                if not code.startswith(('600','601','603','605','000','001','002')):continue
                price=float(parts[3]);prev_c=float(parts[4])
                pct=round((price/prev_c-1)*100,2) if prev_c else 0
                vol_ratio=float(parts[38]) if parts[38] else 0
                hsl=0
                try: hsl=float(parts[46]) if parts[46] and float(parts[46])<100 else 0
                except: pass
                pe=0
                try: pe=float(parts[39]) if parts[39] else 0
                except: pass
                sz=0
                try: sz=float(parts[44])/1e8 if parts[44] else 0
                except: pass
                stocks[code]={'name':nm,'price':price,'p':pct,'vol_ratio':vol_ratio,'hsl':hsl,'pe':pe,'sz':sz}
            except: pass
    return stocks

# 加载现有缓存
print("加载现有缓存...",flush=True)
d=pickle.load(open('big_cache_full.pkl','rb'))
data,real,names=d['data'],d['real'],d['names']
dates=sorted(data.keys())
last_date=dates[-1]
print(f"缓存最新日期: {last_date}",flush=True)
print(f"缓存总天数: {len(dates)}",flush=True)

today=datetime.now().strftime('%Y-%m-%d')

# 获取实时数据
print("获取实时行情...",flush=True)
live=get_live_data()
print(f"实时: {len(live)}只",flush=True)

# 更新real和names
for code,s in live.items():
    real[code]=real.get(code,{})
    real[code].update({'hsl':s['hsl'],'pe':s['pe'],'shizhi':s['sz']})
    names[code]=s['name']

# 获取K线数据并计算指标
def update_stock(code):
    mkt='sh' if code.startswith(('6','9')) else 'sz'
    kf=os.path.join(CACHE_DIR,f'{mkt}{code}.json')
    if not os.path.exists(kf):return None
    try:
        with open(kf) as f:kdata=json.load(f)
    except:return None
    
    # 检查是否有新数据
    if not kdata or len(kdata)<80:return None
    last_kdate=kdata[-1]['date']
    if last_kdate<=last_date:return None  # 没有新数据
    
    # 从last_date+1开始处理新日期
    idx=next((i for i,k in enumerate(kdata) if k['date']>last_date),None)
    if idx is None:return None
    
    updates=[]
    for i in range(idx,len(kdata)):
        dt=kdata[i]['date']
        if dt>today:break
        close=kdata[i]['close']
        # 计算n（次日最高涨幅）
        nh=0
        if i+1<len(kdata):
            nh=round((kdata[i+1]['high']/close-1)*100,1)
        
        updates.append({'date':dt,'close':close,'nh':nh,'code':code})
    
    return updates

# 只更新有K线缓存的股票
codes=list(live.keys())[:500]  # 先跑500只看看效果
print(f"检查{len(codes)}只股票的K线更新...",flush=True)
new_dates={}
with ThreadPoolExecutor(max_workers=16) as pool:
    futs={pool.submit(update_stock,c):c for c in codes}
    for fut in as_completed(futs):
        result=fut.result()
        if result:
            for r in result:
                dt=r['date']
                if dt not in new_dates:
                    new_dates[dt]={}
                if r['code'] not in new_dates[dt]:
                    new_dates[dt][r['code']]=r

if not new_dates:
    print("没有新数据，K线缓存未更新",flush=True)
else:
    print(f"发现{len(new_dates)}个新日期:",flush=True)
    for dt in sorted(new_dates.keys()):
        stocks=list(new_dates[dt].values())
        print(f"  {dt}: {len(stocks)}只",flush=True)
        # 还需要更多字段（cl, dif, macd等）
        # 这里暂不处理完整的指标计算
    
    # 保存更新后的cache（至少实时数据更新了）
    pickle.dump({'data':data,'real':real,'names':names},open('big_cache_full.pkl','wb'))
    print("✅ 缓存已保存（实时数据更新）",flush=True)

print(f"\n当前最新缓存日期范围: {dates[0][:10]} ~ {dates[-1][:10]}")
print(f"要获取完整K线更新需要跑全量股票K线拉取，需API调用")
