#!/usr/bin/env python3
"""
重写缓存 — 含10+维度特征
新增: 量比(vr), KDJ-J值(j), MA5斜率(ms), DIF值(dif), 振幅(amp), 换手比(tvr)
放宽M1部分条件（ATR>2% 替代 ATR>3%，取消站MA5和阳线硬过滤改为评分项）
"""
import json, os, time, sys, urllib.request, re, pickle
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"
OUTPUT = r"C:\Users\12546\AppData\Local\hermes\scripts\big_cache_full.pkl"

def calc_ma(s,pd_list):
    n=len(s); r={}
    for pd in pd_list:
        ma=[None]*n
        for i in range(pd-1,n): ma[i]=sum(s[i-pd+1:i+1])/pd
        r[pd]=ma
    return r

def calc_macd(ps):
    n=len(ps); dif=[None]*n; dea=[None]*n
    if n<26: return dif,dea
    e12=[ps[0]]; e26=[ps[0]]
    for i in range(1,n):
        e12.append(e12[-1]*11/13+ps[i]*2/13); e26.append(e26[-1]*25/27+ps[i]*2/27)
        dif[i]=e12[i]-e26[i]
    dea[0]=dif[0] if dif[0] else 0
    for i in range(1,n): dea[i]=dea[i-1]*8/10+(dif[i] if dif[i] else 0)*2/10
    return dif,dea

def calc_kdj(h,l,c,n=9):
    L=len(c); k=[50.0]*L; d=[50.0]*L; j=[50.0]*L
    if L<n: return k,d,j
    for i in range(n-1,L):
        hh=max(h[i-n+1:i+1]); ll=min(l[i-n+1:i+1])
        rsv=50.0 if hh==ll else (c[i]-ll)/(hh-ll)*100
        if i>n-1:
            k[i]=2/3*k[i-1]+1/3*rsv; d[i]=2/3*d[i-1]+1/3*k[i]
            j[i]=3*k[i]-2*d[i]
    return k,d,j

print("📡 扫描文件..."); t0=time.time()
all_files=[f for f in os.listdir(CACHE_DIR) if f.endswith('.json') and 
           (f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2'))]
print(f"📦 {len(all_files)}个文件")

all_recs_by_date=defaultdict(list)
code_names={}

for idx,fn in enumerate(all_files):
    try:
        with open(os.path.join(CACHE_DIR,fn),'rb') as f: recs=json.loads(f.read().decode('utf-8'))
        if len(recs)<100: continue  # need enough data for indicators
        code=fn.replace('.json','')
        c=[r['close'] for r in recs]; h=[r['high'] for r in recs]; l=[r['low'] for r in recs]
        o=[r['open'] for r in recs]; v=[r['volume'] for r in recs]
        
        # 基础指标
        mas=calc_ma(c,[5,10,20,60])
        dif,dea=calc_macd(c)
        k,d,j=calc_kdj(h,l,c)
        
        # 涨跌幅序列
        pct=[0.0]
        for i in range(1,len(c)): pct.append((c[i]/c[i-1]-1)*100)
        
        # ATR
        atr=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                tr_l=[max(h[t]-l[t],abs(h[t]-c[t-1]),abs(l[t]-c[t-1])) for t in range(i-13,i+1)]
                atr[i]=sum(tr_l)/14
        
        # 5日均量
        ma5_v=calc_ma(v,[5])[5]
        
        # WR指标(14日)
        wrv=[None]*len(c)
        if len(c)>=15:
            for i in range(14,len(c)):
                h14=max(h[i-13:i+1]); l14=min(l[i-13:i+1])
                wrv[i]=(h14-c[i])/(h14-l14+0.001)*100 if h14!=l14 else 50
        
        for di in range(100, len(recs)):
            dt=recs[di]['date']
            if dt<'2025-01-01': continue
            
            cl=c[di]; op=o[di]; hi=h[di]; lo=l[di]
            if cl>=80: continue
            
            # ═══ 放宽的M1条件 ═══
            m=mas
            # 股价<80 ✓
            # 均线多头——放宽到 MA5>MA60 即可（长期趋势向上）
            if not (m[5][di] and m[60][di] and m[5][di]>m[60][di]): continue
            # MACD零轴上 DIF>0且DIF>DEA
            if not (dif[di] and dea[di] and dif[di]>0 and dif[di]>dea[di]): continue
            # ATR放宽到>2%
            a_v=atr[di]
            if not (a_v and cl>0 and a_v/cl*100>2): continue
            # 站上MA60
            if not (m[60][di] and cl>m[60][di]): continue
            # ❌ 不再硬过滤阳线（改为评分用）
            # ❌ 不再硬过滤站MA5（改为评分用）
            
            # 涨跌幅1~8%
            pct_v=round(pct[di],2)
            if not (1 <= pct_v < 8): continue
            
            rng=hi-lo
            shadow=(hi-max(cl,op))/(rng+0.001)*100 if rng>0 else 0
            body=abs(cl-op)/op*100 if op>0 else 0
            atr_p=round(a_v/cl*100,2) if a_v and cl>0 else 0
            
            # 20日位置
            pos20=0
            if di>=20:
                h20=max(h[di-19:di+1]); l20=min(l[di-19:di+1])
                pos20=round((cl-l20)/(h20-l20+0.001)*100,1)
            
            # ═══ 新维度 ═══
            # 量比（当前成交量/5日均量）
            vol_ratio=round(v[di]/ma5_v[di],2) if ma5_v[di] and ma5_v[di]>0 else 1.0
            
            # KDJ-J值
            j_val=round(j[di],1) if j[di] is not None else 50.0
            
            # KDJ-K和KDJ-D
            k_val=round(k[di],1) if k[di] is not None else 50.0
            d_val=round(d[di],1) if d[di] is not None else 50.0
            
            # KDJ金叉
            kdj_golden=1 if di>=9 and k[di] and d[di] and k[di-1] and d[di-1] and k[di]>d[di] and k[di-1]<=d[di-1] else 0
            
            # MACD金叉（mg）
            macd_golden=1 if di>=1 and dif[di] and dea[di] and dif[di-1] and dea[di-1] and dif[di]>dea[di] and dif[di-1]<=dea[di-1] else 0
            
            # MA5斜率（当前MA5相比5天前涨了百分之几）
            ma5_slope=round((m[5][di]/m[5][di-5]-1)*100,2) if di>=5 and m[5][di] and m[5][di-5] and m[5][di-5]>0 else 0
            
            # DIF值
            dif_val=round(dif[di],3) if dif[di] is not None else 0
            
            # 振幅%
            amplitude=round((hi-lo)/op*100,2) if op>0 else 0
            
            # 今日总成交量（供参考）
            vol_val=v[di]
            
            # ═══ 次日验证数据 ═══
            next_h=round((recs[di+1]["high"]/cl-1)*100,2) if di+1<len(recs) else None
            next_c=round((recs[di+1]["close"]/cl-1)*100,2) if di+1<len(recs) else None
            
            # ═══ 存入 ═══
            all_recs_by_date[dt].append({
                'code':code,
                # 原有特征（用原key保持兼容）
                'p':pct_v,        # 涨跌幅%
                'b':round(body,2),# 实体%
                's':round(shadow,1), # 上影%
                'a':atr_p,        # ATR%
                'cl':pos20,       # 收盘位置%
                # 新特征（用全名key）
                'vol_ratio':vol_ratio,  # 量比
                'j_val':j_val,         # KDJ-J值
                'ma5_slope':ma5_slope, # MA5斜率(%)
                'dif_val':dif_val,     # MACD DIF值
                'amplitude':amplitude, # 振幅%
                'vol':vol_val,         # 成交量
                'close':round(cl,2),   # 收盘价
                'body_pct':round(body,2), # 实体%(全称)
                # 新增特征（评分用）
                'macd_golden':macd_golden, # MACD金叉
                'mg':macd_golden,         # 别名mg
                'k_val':k_val,            # KDJ-K
                'kv':k_val,
                'd_val':d_val,            # KDJ-D
                'dv':d_val,
                'kdj_golden':kdj_golden,  # KDJ金叉
                'kdj_g':kdj_golden,
                'wr_val':round(wrv[di],1) if wrv[di] is not None else 50,  # WR值
                'wrv':round(wrv[di],1) if wrv[di] is not None else 50,
                'pos_in_day':round((cl[di]-lo[di])/(hi[di]-lo[di]+0.001)*100,1),  # 盘中位置
                # 额外过滤信息（留作评分用，不硬过滤）
                'is_yang':1 if cl>op else 0,    # 是否阳线
                'above_ma5':1 if (m[5][di] and cl>m[5][di]) else 0, # 是否站MA5
                'above_ma10':1 if (m[10][di] and cl>m[10][di]) else 0, # 是否站MA10
                'above_ma20':1 if (m[20][di] and cl>m[20][di]) else 0, # 是否站MA20
                # 次日数据
                'n':next_h,  # 次日最高（兼容旧key）
                'next_close':next_c, # 次日收盘
                'next_high':next_h,
            })
    except:
        pass
    if (idx+1)%500==0:
        total=sum(len(v) for v in all_recs_by_date.values())
        print(f"  {idx+1}/{len(all_files)} -> {total}条")

# 股票名称
all_codes=list(set(r['code'] for v in all_recs_by_date.values() for r in v))
print(f"📡 获取{len(all_codes)}只股票名称...")
for i in range(0,len(all_codes),50):
    batch=all_codes[i:i+50]
    sina_codes=[f"sh{c[2:]}" if c.startswith('sh') else f"sz{c[2:]}" for c in batch]
    try:
        req=urllib.request.Request(f"https://hq.sinajs.cn/list={','.join(sina_codes)}",
                                   headers={'Referer':'https://finance.sina.com.cn'})
        resp=urllib.request.urlopen(req,timeout=5)
        text=resp.read().decode('gbk')
        for line in text.strip().split('\n'):
            m=re.search(r'var hq_str_(sh\d+|sz\d+)="([^,]+)',line)
            if m:
                ck=m.group(1); orig=f"sh{ck[2:]}" if ck.startswith('sh') else f"sz{ck[2:]}"
                code_names[orig]=m.group(2)
    except: pass

cache={'data':dict(all_recs_by_date),'names':code_names,'build_time':time.time()-t0}
# 添加real数据（换手率/市值默认值）
all_codes=set()
for recs in all_recs_by_date.values():
    for r in recs:
        if 'code' in r: all_codes.add(r['code'])
cache['real']={code:{'hsl':5.0,'shizhi':100.0} for code in all_codes}
with open(OUTPUT,'wb') as f: pickle.dump(cache,f)
print(f"\n✅ 保存完成: {OUTPUT}")
print(f"📅 {len(all_recs_by_date)}个交易日")
total=sum(len(v) for v in all_recs_by_date.values())
print(f"📊 {total}条候选项（含{len(all_codes)}只股票）")
print(f"🏷️ {len(code_names)}只名称")
print(f"⏱ {time.time()-t0:.0f}秒")
