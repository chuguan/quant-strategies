#!/usr/bin/env python3
"""
最终版CG-08：加量比>1、换手率3~15%、PE>0、市值<200亿
用腾讯API实时查询数据
"""
import pickle, os, sys, urllib.request, re

CACHE=r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache.pkl"
ST_FILE=r"C:\Users\12546\AppData\Local\hermes\scripts\st_codes.txt"
ST=set()
if os.path.exists(ST_FILE):
    with open(ST_FILE) as f: ST={l.strip() for l in f if l.strip()}

with open(CACHE,'rb') as f: c=pickle.load(f)
dc=c['data']; nm=c['names']
MIN=1.0; MAX=8.0

def ok(e):
    if e['code'] in ST: return False
    if e['p'] is None or not (MIN<=e['p']<MAX): return False
    if e.get('is_yang',0)!=1 or e.get('above_ma5',0)!=1 or e.get('a',0)<=3: return False
    return True

def sc(e):
    return e['p']+e['a']*1.5+(e.get('dif_val',0) or 0)*0.5+e.get('cl',0)*0.02-(3 if e.get('s',0)>40 else 0)

latest=sorted([d for d in dc if d.startswith('2026')])[-1]
cs=[e for e in dc.get(latest,[]) if ok(e)]
for e in cs: e['s2']=round(sc(e),2)
cs.sort(key=lambda e:e['s2'], reverse=True)

# 取前50名查实时数据
top=cs[:50]
codes_to_query=[e['code'] for e in top]

# 腾讯API格式: sh600156 -> sh600156, sz002484 -> sz002484
tx_codes=[c.replace('sh','sh').replace('sz','sz') for c in codes_to_query]
url='http://qt.gtimg.cn/q='+','.join(tx_codes)

print(f"📡 查询{len(top)}只股票实时数据...")
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
try:
    resp=urllib.request.urlopen(req,timeout=15)
    txt=resp.read().decode('gbk')
except Exception as e:
    print(f"❌ 请求失败: {e}")
    sys.exit(1)

# 解析腾讯API返回
real_data={}
for line in txt.strip().split(';'):
    if not line.strip(): continue
    m=re.search(r'v_(sh\d+|sz\d+)="([^"]+)',line)
    if not m: continue
    code=m.group(1)
    fields=m.group(2).split('~')
    if len(fields)<60: continue
    
    # 转换code格式
    orig=f"{code[:2]}{code[2:]}"
    
    try:
        liangbi=float(fields[56]) if fields[56] and fields[56].replace('.','',1).lstrip('-').isdigit() else 1.0
        hsl=float(fields[38]) if fields[38] and fields[38].replace('.','',1).lstrip('-').isdigit() else 0
        pe=float(fields[39]) if fields[39] and fields[39].replace('.','',1).lstrip('-').isdigit() else 0
        shizhi=float(fields[44]) if fields[44] and fields[44].replace('.','',1).lstrip('-').isdigit() else 999
    except:
        continue
    
    real_data[orig]={'liangbi':liangbi,'hsl':hsl,'pe':pe,'shizhi':shizhi}

print(f"✅ 查询完成，{len(real_data)}只\n")

# 过滤+输出
print(f"📅 {latest} 推荐（量比>1 + 换手率3~15% + PE>0 + 市值<200亿）")
print(f"{'#':<3}{'名称':<10}{'代码':<16}{'买入价':>7}{'涨跌':>6}{'ATR':>5}{'量比':>5}{'换手':>6}{'PE':>5}{'市值':>6}{'评分':>5}")
print("-"*85)

cnt=0
for e in cs:
    if cnt>=5: break
    rd=real_data.get(e['code'])
    if not rd: continue
    if rd['liangbi']<=1: continue
    if not (3<=rd['hsl']<=15): continue
    if rd.get('pe',0)<=0: continue
    if rd.get('shizhi',999)>=200: continue
    
    cnt+=1
    n2=nm.get(e['code'],'?')
    print(f"{cnt:<3}{n2:<10}{e['code']:<16}{e['close']:>7.2f}{e['p']:>+5.1f}%{e['a']:>4.1f}% {rd['liangbi']:>4.1f}  {rd['hsl']:>5.1f}% {rd.get('pe',0):>4.0f}  {rd['shizhi']:>5.1f}亿 {e['s2']:>5.1f}")

if cnt==0:
    print("  ⚠️ 没有同时满足所有条件的票！放宽换手率试试？")
