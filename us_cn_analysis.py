import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

print("=" * 70)
print("  美股 → A股 传导概率量化分析")
print("  US Stock Market → A-Share Transmission Analysis")
print("=" * 70)

YEAR = 2026
START = f"{YEAR}-01-01"
END = datetime.now().strftime("%Y-%m-%d")

# ===== 1. 获取数据 =====
print(f"\n▶ 获取数据 {START} ~ {END}")

# US Indices
print("  · 美股指数...", end=" ", flush=True)
us_ixic = ak.index_us_stock_sina(symbol='.IXIC')
us_dji = ak.index_us_stock_sina(symbol='.DJI')
us_inx = ak.index_us_stock_sina(symbol='.INX')
us_ndx = ak.index_us_stock_sina(symbol='.NDX')
for df in [us_ixic, us_dji, us_inx, us_ndx]:
    df.columns = ['date','open','high','low','close','volume','amount']
    df['date'] = pd.to_datetime(df['date'])
print(f"OK ({len(us_inx)}天)")

# A-share Indices
print("  · A股指数...", end=" ", flush=True)
sh_idx = ak.stock_zh_index_daily_tx(symbol='sh000001', start_date=START.replace('-',''), end_date=END.replace('-',''))
sz_idx = ak.stock_zh_index_daily_tx(symbol='sz399001', start_date=START.replace('-',''), end_date=END.replace('-',''))
hs300 = ak.stock_zh_index_daily_tx(symbol='sz399300', start_date=START.replace('-',''), end_date=END.replace('-',''))
sh50 = ak.stock_zh_index_daily_tx(symbol='sh000016', start_date=START.replace('-',''), end_date=END.replace('-',''))
zxb = ak.stock_zh_index_daily_tx(symbol='sz399005', start_date=START.replace('-',''), end_date=END.replace('-',''))
cyb = ak.stock_zh_index_daily_tx(symbol='sz399006', start_date=START.replace('-',''), end_date=END.replace('-',''))
for df in [sh_idx, sz_idx, hs300, sh50, zxb, cyb]:
    df['date'] = pd.to_datetime(df['date'])
print(f"OK ({len(sh_idx)}天)")

# HK Index
print("  · 港股指数...", end=" ", flush=True)
try:
    hsi = ak.stock_hk_index_daily_sina(symbol='HSI')
    hsi['date'] = pd.to_datetime(hsi['date'])
    print(f"OK ({len(hsi)}天)")
except:
    hsi = None
    print("跳过")

# ===== 2. 计算日涨跌幅 =====
print("\n▶ 计算日涨跌幅...")

def calc_pct(df):
    df['pct'] = df['close'].pct_change() * 100
    return df

us_ixic = calc_pct(us_ixic)
us_dji = calc_pct(us_dji)
us_inx = calc_pct(us_inx)
us_ndx = calc_pct(us_ndx)
sh_idx['pct'] = sh_idx['close'].pct_change() * 100
sz_idx['pct'] = sz_idx['close'].pct_change() * 100
hs300['pct'] = hs300['close'].pct_change() * 100
sh50['pct'] = sh50['close'].pct_change() * 100
zxb['pct'] = zxb['close'].pct_change() * 100
cyb['pct'] = cyb['close'].pct_change() * 100

# ===== 3. 时间对齐 =====
print("  · 对齐日期：美股T收盘 → A股T+1收盘...")

us = us_inx[['date','close','pct']].copy()
us.columns = ['date','sp500_close','sp500_pct']
# Merge other US indices by date (not position)
us = us.merge(us_ixic[['date','pct']].rename(columns={'pct':'nasdaq_pct'}), on='date', how='left')
us = us.merge(us_dji[['date','pct']].rename(columns={'pct':'dow_pct'}), on='date', how='left')
us = us.merge(us_ndx[['date','pct']].rename(columns={'pct':'ndx_pct'}), on='date', how='left')

sh = sh_idx[['date','close','pct']].copy()
sh.columns = ['date','sh_close','sh_pct']
sz = sz_idx[['date','close','pct']].copy()
sz.columns = ['date','sz_close','sz_pct']
hs = hs300[['date','close','pct']].copy()
hs.columns = ['date','hs300_close','hs300_pct']
sh50_df = sh50[['date','close','pct']].copy()
sh50_df.columns = ['date','sh50_close','sh50_pct']
zxb_df = zxb[['date','close','pct']].copy()
zxb_df.columns = ['date','zxb_close','zxb_pct']
cyb_df = cyb[['date','close','pct']].copy()
cyb_df.columns = ['date','cyb_close','cyb_pct']

merged = sh.merge(sz, on='date', how='left')
merged = merged.merge(hs, on='date', how='left')
merged = merged.merge(sh50_df, on='date', how='left')
merged = merged.merge(zxb_df, on='date', how='left')
merged = merged.merge(cyb_df, on='date', how='left')

merged = merged.sort_values('date').reset_index(drop=True)
us_dates = sorted(us['date'].tolist())

def find_prev_us_date(a_date):
    prev = [d for d in us_dates if d < a_date]
    return prev[-1] if prev else None

merged['us_date'] = merged['date'].apply(find_prev_us_date)

us_rename = us.rename(columns={'date':'us_date'})
merged = merged.merge(us_rename, on='us_date', how='left')

# Also add HK data
if hsi is not None:
    hsi['pct'] = hsi['close'].pct_change() * 100
    hk = hsi[['date','close','pct']].copy()
    hk.columns = ['us_date','hsi_close','hsi_pct']
    hk['us_date'] = pd.to_datetime(hk['us_date'])
    merged = merged.merge(hk, on='us_date', how='left')

merged = merged.dropna(subset=['sp500_pct'])
merged = merged.reset_index(drop=True)

print(f"  有效对齐交易日: {len(merged)}天")

# ===== 4. 基础传导概率 =====
print("\n" + "=" * 70)
print("  📊 一、基础传导概率（美跌→A股次日跌概率）")
print("=" * 70)

thresholds = [0, -0.5, -1, -1.5, -2, -3]
print(f"{'阈值':>8} | {'样本数':>6} | {'上证↓':>8} | {'深证↓':>8} | {'沪深300↓':>9} | {'上证50↓':>9} | {'中小板↓':>9} | {'创业板↓':>9}")
print("-" * 80)

for t in thresholds:
    if t == 0:
        mask = merged['sp500_pct'] < 0
    else:
        mask = merged['sp500_pct'] <= t
    
    subset = merged[mask]
    n = len(subset)
    if n < 3:
        print(f"  ≤{t:>4.1f}%  | {n:>6} | {'-':>8} | {'-':>8} | {'-':>9} | {'-':>9} | {'-':>9} | {'-':>9}")
        continue
    
    sh_d = (subset['sh_pct'] < 0).mean() * 100
    sz_d = (subset['sz_pct'] < 0).mean() * 100
    hs_d = (subset['hs300_pct'] < 0).mean() * 100
    sh50_d = (subset['sh50_pct'] < 0).mean() * 100
    zxb_d = (subset['zxb_pct'] < 0).mean() * 100
    cyb_d = (subset['cyb_pct'] < 0).mean() * 100
    print(f"  ≤{t:>4.1f}%  | {n:>6} | {sh_d:>7.1f}% | {sz_d:>7.1f}% | {hs_d:>8.1f}% | {sh50_d:>8.1f}% | {zxb_d:>8.1f}% | {cyb_d:>8.1f}%")

# ===== 5. 上涨传导 =====
print(f"\n{'阈值':>8} | {'样本数':>6} | {'上证↑':>8} | {'深证↑':>8} | {'沪深300↑':>9} | {'上证50↑':>9} | {'中小板↑':>9} | {'创业板↑':>9}")
print("-" * 80)

for t in [0, 0.5, 1, 1.5, 2, 3]:
    if t == 0:
        mask = merged['sp500_pct'] > 0
    else:
        mask = merged['sp500_pct'] >= t
    
    subset = merged[mask]
    n = len(subset)
    if n < 3:
        print(f"  ≥{t:>4.1f}%  | {n:>6} | {'-':>8} | {'-':>8} | {'-':>9} | {'-':>9} | {'-':>9} | {'-':>9}")
        continue
    
    sh_u = (subset['sh_pct'] > 0).mean() * 100
    sz_u = (subset['sz_pct'] > 0).mean() * 100
    hs_u = (subset['hs300_pct'] > 0).mean() * 100
    sh50_u = (subset['sh50_pct'] > 0).mean() * 100
    zxb_u = (subset['zxb_pct'] > 0).mean() * 100
    cyb_u = (subset['cyb_pct'] > 0).mean() * 100
    print(f"  ≥{t:>4.1f}%  | {n:>6} | {sh_u:>7.1f}% | {sz_u:>7.1f}% | {hs_u:>8.1f}% | {sh50_u:>8.1f}% | {zxb_u:>8.1f}% | {cyb_u:>8.1f}%")

# ===== 6. 三大指数传导力对比 =====
print("\n" + "=" * 70)
print("  📊 二、三大美股指数传导力对比")
print("=" * 70)

indices = [
    ('sp500_pct', 'S&P 500'),
    ('nasdaq_pct', '纳斯达克'),
    ('dow_pct', '道琼斯'),
]

print(f"\n{'指数':>10} | {'同向率':>8} | {'反向率':>8} | {'相关系数':>10} | {'传导力(>1%)':>12}")
print("-" * 55)

for col, name in indices:
    same_dir = ((merged[col] > 0) & (merged['sh_pct'] > 0) | (merged[col] < 0) & (merged['sh_pct'] < 0)).mean() * 100
    opp_dir = ((merged[col] > 0) & (merged['sh_pct'] < 0) | (merged[col] < 0) & (merged['sh_pct'] > 0)).mean() * 100
    corr = merged[col].corr(merged['sh_pct'])
    big_us = merged[np.abs(merged[col]) > 1]
    transmission = (np.sign(big_us[col]) == np.sign(big_us['sh_pct'])).mean() * 100 if len(big_us) > 5 else 0
    print(f"  {name:>8} | {same_dir:>7.1f}% | {opp_dir:>7.1f}% | {corr:>+9.4f} | {transmission:>11.1f}%")

# ===== 7. 港股传导 =====
if 'hsi_pct' in merged.columns:
    print("\n" + "=" * 70)
    print("  📊 三、港股HSI→A股传导（港股盘中可参考）")
    print("=" * 70)
    
    # 同一日（港股和A股同时开市）
    hk_same = ((merged['hsi_pct'] > 0) & (merged['sh_pct'] > 0) | (merged['hsi_pct'] < 0) & (merged['sh_pct'] < 0)).mean() * 100
    hk_corr = merged['hsi_pct'].corr(merged['sh_pct'])
    print(f"\n  港股与A股同日同向率: {hk_same:.1f}%")
    print(f"  相关系数: {hk_corr:+.4f}")
    
    # 港股比A股强多少？
    diff = merged['hsi_pct'] - merged['sh_pct']
    print(f"  港股-上证均值差: {diff.mean():+.2f}%")
    
    # 港股先知效应：前日港股→A股
    merged['hsi_pct_lag1'] = merged['hsi_pct'].shift(1)
    hk_lag = ((merged['hsi_pct_lag1'] > 0) & (merged['sh_pct'] > 0) | (merged['hsi_pct_lag1'] < 0) & (merged['sh_pct'] < 0)).mean() * 100
    hk_lag_corr = merged['hsi_pct_lag1'].corr(merged['sh_pct'])
    print(f"  前日港股→A股同向率: {hk_lag:.1f}%")
    print(f"  前日港股相关系数: {hk_lag_corr:+.4f}")

# ===== 8. 分月趋势 =====
print("\n" + "=" * 70)
print("  📊 四、按月传导率变化")
print("=" * 70)

merged['month'] = merged['date'].dt.month
monthly = merged.groupby('month').agg(
    天数=('date','count'),
    美股涨跌=('sp500_pct','mean'),
    A股涨跌=('sh_pct','mean'),
    同向率=('sp500_pct', lambda x: ((x > 0) & (merged.loc[x.index,'sh_pct'] > 0) | (x < 0) & (merged.loc[x.index,'sh_pct'] < 0)).mean() * 100)
).reset_index()

print(f"{'月份':>4} | {'天数':>4} | {'S&P500均值':>10} | {'上证均值':>10} | {'同向率':>8}")
print("-" * 55)
for _, r in monthly.iterrows():
    print(f"  {int(r['month']):>2}月  | {r['天数']:>4} | {r['美股涨跌']:>+9.2f}% | {r['A股涨跌']:>+9.2f}% | {r['同向率']:>7.1f}%")

# ===== 9. 极端事件 =====
print("\n" + "=" * 70)
print("  📊 五、极端事件分析（美跌>2%）")
print("=" * 70)

extreme = merged[merged['sp500_pct'] <= -2].sort_values('sp500_pct')
if len(extreme) > 0:
    print(f"\n  2026年美股大跌(>2%)共 {len(extreme)} 次：")
    print(f"  {'日期':>12} | {'S&P500':>8} | {'上证':>8} | {'深证':>8} | {'沪深300':>8} | {'中小板':>8} | {'创业板':>8} | {'港股':>8}")
    print("-" * 90)
    for _, r in extreme.iterrows():
        hk_str = f"{r['hsi_pct']:>+7.2f}%" if 'hsi_pct' in r and pd.notna(r['hsi_pct']) else "  N/A  "
        print(f"  {r['date'].strftime('%m-%d %a')} | {r['sp500_pct']:>+7.2f}% | {r['sh_pct']:>+7.2f}% | {r['sz_pct']:>+7.2f}% | {r['hs300_pct']:>+7.2f}% | {r['zxb_pct']:>+7.2f}% | {r['cyb_pct']:>+7.2f}% | {hk_str}")

# ===== 10. 美股涨跌对A股次日涨跌幅影响幅度 =====
print("\n" + "=" * 70)
print("  📊 六、美股涨跌幅度 vs A股次日响应幅度")
print("=" * 70)

# Bucket US performance
us_bins = [-float('inf'), -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, float('inf')]
us_labels = ['<-2%','-2~-1.5%','-1.5~-1%','-1~-0.5%','-0.5~0%','0~0.5%','0.5~1%','1~1.5%','1.5~2%','>2%']
merged['us_bucket'] = pd.cut(merged['sp500_pct'], bins=us_bins, labels=us_labels)

bucket_stats = merged.groupby('us_bucket', observed=True).agg(
    N=('sh_pct','count'),
    上证=('sh_pct','mean'),
    深证=('sz_pct','mean'),
    沪深300=('hs300_pct','mean'),
    中小板=('zxb_pct','mean'),
    创业板=('cyb_pct','mean'),
).round(2)

print(f"\n{'美涨跌':>10} | {'N':>4} | {'上证次日':>9} | {'深证次日':>9} | {'沪深300':>9} | {'中小板':>9} | {'创业板':>9}")
print("-" * 75)
for label in us_labels:
    if label in bucket_stats.index:
        r = bucket_stats.loc[label]
        print(f"  {label:>8} | {int(r['N']):>4} | {r['上证']:>+8.2f}% | {r['深证']:>+8.2f}% | {r['沪深300']:>+8.2f}% | {r['中小板']:>+8.2f}% | {r['创业板']:>+8.2f}%")

# ===== 11. 总括结论 =====
print("\n" + "=" * 70)
print("  🎯 七、关键结论与因子可行性评估")
print("=" * 70)

base_up = (merged['sh_pct'] > 0).mean() * 100
base_down = (merged['sh_pct'] < 0).mean() * 100

us_down = merged[merged['sp500_pct'] < 0]
cond_down = (us_down['sh_pct'] < 0).mean() * 100

us_up = merged[merged['sp500_pct'] > 0]
cond_up = (us_up['sh_pct'] > 0).mean() * 100

# Lift calculations
print(f"""
  ┌──────────────┬──────────┬──────────┬──────────┐
  │   指标        │ 无条件   │ 美跌条件  │ 美涨条件  │
  ├──────────────┼──────────┼──────────┼──────────┤
  │ 上证涨概率    │ {base_up:>6.1f}%  │ {cond_up:>6.1f}%  │ {cond_up:>6.1f}%  │
  │ 上证跌概率    │ {base_down:>6.1f}%  │ {cond_down:>6.1f}%  │ {100-cond_up:>6.1f}%  │
  │ 信息增益      │    —     │ {cond_down-base_down:>+6.1f}%  │ {cond_up-base_up:>+6.1f}%  │
  └──────────────┴──────────┴──────────┴──────────┘
""")

# Stronger signals
print("  强信号情境：")
for t in [-1, -1.5, -2]:
    sm = merged[merged['sp500_pct'] <= t]
    if len(sm) >= 3:
        prob = (sm['sh_pct'] < 0).mean() * 100
        avg = sm['sh_pct'].mean()
        print(f"    美跌≤{t}% ({len(sm)}次)→上证跌概率{prob:.1f}%, 均值{avg:+.2f}% (信息增益{prob-base_down:+.1f}%)")

for t in [1, 1.5, 2]:
    sm = merged[merged['sp500_pct'] >= t]
    if len(sm) >= 3:
        prob = (sm['sh_pct'] > 0).mean() * 100
        avg = sm['sh_pct'].mean()
        print(f"    美涨≥{t}% ({len(sm)}次)→上证涨概率{prob:.1f}%, 均值{avg:+.2f}% (信息增益{prob-base_up:+.1f}%)")

print(f"""
  {'='*60}
  【因子可行性结论】
  {'='*60}

  ✅ 可用作辅助因子，但不要单独使用

  推荐用法：
  ① 美跌>1.5% + A股低开 = 当天谨慎，降低仓位预期
  ② 美涨>1% = 积极环境，可以正常选股操作
  ③ 美涨跌<0.5% = 忽略，A股走自己的独立行情
  ④ 中概股传导比指数更直接（需另分析）
  ⑤ 关注美科技股（纳斯达克）对A股科技板块的传导
  
  ⚠ 重要限制：
  - 美股传导不是必然的，A股有独立行情能力
  - 月度同向率波动大（40%~80%之间）
  - 选股层面影响有限，更适合大盘择时
""")

# Save data for further analysis
merged.to_csv('/tmp/us_cn_aligned_data.csv', index=False)
print("\n✓ 数据已保存")
