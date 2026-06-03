"""
美股板块 → A股板块 每日传导量化分析
US Sector → A-Share Sector Daily Transmission Analysis
2026年全量数据
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

YEAR = 2026
START = f"{YEAR}-01-01"
END = datetime.now().strftime("%Y-%m-%d")
S = START.replace('-','')
E = END.replace('-','')

print("=" * 70)
print("  美股热点板块 → A股同板块 传导概率分析")
print(f"  {START} ~ {END}")
print("=" * 70)

# ========================================================
# 定义：美股核心股 → A股对应板块映射
# ========================================================
SECTOR_MAP = {
    '半导体': {
        'us_stocks': ['NVDA', 'AMD', 'INTC'],
        'cn_boards': ['半导体'],
    },
    'AI科技': {
        'us_stocks': ['MSFT', 'META', 'GOOGL'],
        'cn_boards': ['计算机设备', '软件开发', 'IT服务'],
    },
    '新能源车': {
        'us_stocks': ['TSLA', 'RIVN'],
        'cn_boards': ['汽车整车'],
    },
    '中概互联': {
        'us_stocks': ['BABA', 'JD', 'BIDU'],
        'cn_boards': ['互联网电商'],
    },
    '生物医药': {
        'us_stocks': ['UNH', 'JNJ', 'PFE'],
        'cn_boards': ['生物制品', '化学制药'],
    },
    '金融': {
        'us_stocks': ['JPM', 'GS', 'BAC'],
        'cn_boards': ['银行', '证券'],
    },
    '油气能源': {
        'us_stocks': ['XOM', 'CVX'],
        'cn_boards': ['油气开采及服务', '石油加工贸易'],
    },
    '消费': {
        'us_stocks': ['AMZN', 'WMT'],
        'cn_boards': ['食品加工制造', '饮料制造'],
    },
    '军工': {
        'us_stocks': ['LMT', 'RTX'],
        'cn_boards': ['军工装备'],
    },
    '消费电子': {
        'us_stocks': ['AAPL'],
        'cn_boards': ['消费电子'],
    },
}

# ========================================================
# 1. 下载美股数据
# ========================================================
print("\n▶ 1. 下载美股个股数据...")
us_stocks_all = set()
for s in SECTOR_MAP.values():
    us_stocks_all.update(s['us_stocks'])
us_stocks_all = sorted(list(us_stocks_all))
print(f"  总个股数: {len(us_stocks_all)}")

us_data = {}
for i, sym in enumerate(us_stocks_all):
    print(f"  [{i+1}/{len(us_stocks_all)}] {sym}...", end=" ", flush=True)
    try:
        df = ak.stock_us_daily(symbol=sym, adjust='')
        df['date'] = pd.to_datetime(df['date'])
        df = df[df['date'] >= f'{YEAR}-01-01'].copy()
        df['pct'] = df['close'].pct_change() * 100
        us_data[sym] = df[['date', 'close', 'pct']].copy()
        print(f"{len(df)}天")
    except Exception as e:
        print(f"FAILED: {e}")

print(f"\n  成功获取: {len(us_data)}/{len(us_stocks_all)} 只")

# ========================================================
# 2. 下载A股板块数据
# ========================================================
print("\n▶ 2. 下载A股THS行业板块数据...")
cn_boards_all = set()
for s in SECTOR_MAP.values():
    cn_boards_all.update(s['cn_boards'])
cn_boards_all = sorted(list(cn_boards_all))
print(f"  总板块数: {len(cn_boards_all)}")

cn_board_data = {}
for i, board_name in enumerate(cn_boards_all):
    print(f"  [{i+1}/{len(cn_boards_all)}] {board_name}...", end=" ", flush=True)
    try:
        df = ak.stock_board_industry_index_ths(symbol=board_name, start_date=S, end_date=E)
        df['date'] = pd.to_datetime(df['日期'])
        df = df.sort_values('date').reset_index(drop=True)
        df['pct'] = df['收盘价'].pct_change() * 100
        cn_board_data[board_name] = df[['date', '收盘价', 'pct']].copy()
        print(f"{len(df)}天")
    except Exception as e:
        print(f"FAILED: {e}")

print(f"\n  成功获取: {len(cn_board_data)}/{len(cn_boards_all)} 个板块")

# ========================================================
# 3. 对每个板块对计算传导
# ========================================================
print("\n" + "=" * 70)
print("  📊 板块传导分析结果")
print("=" * 70)

results = []

for sector_name, mapping in SECTOR_MAP.items():
    us_syms = mapping['us_stocks']
    cn_bnames = mapping['cn_boards']
    
    # 过滤只有成功获取的
    us_syms_ok = [s for s in us_syms if s in us_data]
    cn_bnames_ok = [b for b in cn_bnames if b in cn_board_data]
    
    if len(us_syms_ok) == 0 or len(cn_bnames_ok) == 0:
        print(f"\n  ⚠ {sector_name}: 数据不足 (US={len(us_syms_ok)}, CN={len(cn_bnames_ok)})")
        continue
    
    # 构建美股板块综合收益率（等权重）
    us_combined = None
    for sym in us_syms_ok:
        d = us_data[sym][['date', 'pct']].copy()
        d = d.rename(columns={'pct': sym})
        if us_combined is None:
            us_combined = d
        else:
            us_combined = us_combined.merge(d, on='date', how='outer')
    
    # 等权平均
    us_combined['us_sector_pct'] = us_combined[[s for s in us_syms_ok]].mean(axis=1)
    us_sector = us_combined[['date', 'us_sector_pct']].dropna()
    
    # 构建A股板块综合收益率（等权重）
    cn_combined = None
    for bname in cn_bnames_ok:
        d = cn_board_data[bname][['date', 'pct']].copy()
        d = d.rename(columns={'pct': bname})
        if cn_combined is None:
            cn_combined = d
        else:
            cn_combined = cn_combined.merge(d, on='date', how='outer')
    
    cn_combined['cn_sector_pct'] = cn_combined[[b for b in cn_bnames_ok]].mean(axis=1)
    cn_sector = cn_combined[['date', 'cn_sector_pct']].dropna()
    
    # 对齐：美股T日收盘 → A股T+1日
    us_sector = us_sector.sort_values('date')
    cn_sector = cn_sector.sort_values('date')
    
    us_dates = us_sector['date'].tolist()
    def find_prev_us(a_date):
        prev = [d for d in us_dates if d < a_date]
        return prev[-1] if prev else None
    
    cn_sector['us_date'] = cn_sector['date'].apply(find_prev_us)
    merged = cn_sector.merge(us_sector.rename(columns={'date': 'us_date', 'us_sector_pct': 'us_pct'}), on='us_date', how='inner')
    merged = merged.dropna(subset=['us_pct'])
    
    if len(merged) < 10:
        print(f"\n  ⚠ {sector_name}: 有效对齐数据仅{len(merged)}天，跳过")
        continue
    
    # ===== 计算各项指标 =====
    n = len(merged)
    corr = merged['us_pct'].corr(merged['cn_sector_pct'])
    
    # 同向率
    same_dir = ((merged['us_pct'] > 0) & (merged['cn_sector_pct'] > 0) | 
                (merged['us_pct'] < 0) & (merged['cn_sector_pct'] < 0)).mean() * 100
    
    # 美板块跌时，A板块跟跌概率
    us_neg = merged[merged['us_pct'] < 0]
    us_pos = merged[merged['us_pct'] > 0]
    
    follow_down = (us_neg['cn_sector_pct'] < 0).mean() * 100 if len(us_neg) >= 3 else 0
    follow_up = (us_pos['cn_sector_pct'] > 0).mean() * 100 if len(us_pos) >= 3 else 0
    
    # 美板块大涨(>1.5%)时，A板块同向概率
    us_big_neg = merged[merged['us_pct'] <= -1.5]
    us_big_pos = merged[merged['us_pct'] >= 1.5]
    
    big_follow_down = (us_big_neg['cn_sector_pct'] < 0).mean() * 100 if len(us_big_neg) >= 3 else float('nan')
    big_follow_up = (us_big_pos['cn_sector_pct'] > 0).mean() * 100 if len(us_big_pos) >= 3 else float('nan')
    
    # 美板块平均跌/涨时，A板块的平均响应幅度
    avg_cn_when_us_down = us_neg['cn_sector_pct'].mean() if len(us_neg) >= 3 else 0
    avg_cn_when_us_up = us_pos['cn_sector_pct'].mean() if len(us_pos) >= 3 else 0
    
    # 传导强度：美板块移动1% → A板块移动多少？
    beta = np.polyfit(merged['us_pct'], merged['cn_sector_pct'], 1)[0]
    
    # 信息增益：知道美股板块涨跌后，预测A股板块涨跌的准确率提升
    base_up_prob = (merged['cn_sector_pct'] > 0).mean() * 100
    gain_down = follow_down - (100 - base_up_prob)
    gain_up = follow_up - base_up_prob
    
    results.append({
        'sector': sector_name,
        'us_stocks': '+'.join(us_syms_ok),
        'cn_boards': '+'.join(cn_bnames_ok),
        'n_days': n,
        'corr': corr,
        'same_dir': same_dir,
        'follow_down': follow_down,
        'follow_up': follow_up,
        'big_down_follow': big_follow_down,
        'big_up_follow': big_follow_up,
        'avg_cn_when_us_down': avg_cn_when_us_down,
        'avg_cn_when_us_up': avg_cn_when_us_up,
        'beta': beta,
        'gain_down': gain_down,
        'gain_up': gain_up,
    })
    
    print(f"\n  {'='*60}")
    print(f"  📌 {sector_name}")
    print(f"    美股: {us_syms_ok}  |  A股: {cn_bnames_ok}")
    print(f"    有效交易日: {n}天")
    print(f"  {'='*60}")
    print(f"    相关系数: {corr:+.4f}")
    print(f"    同向率: {same_dir:.1f}%")
    print(f"    传导系数(β): {beta:.4f} (美1%→A{beta:+.2f}%)")
    print(f"    ──────────────────────────────")
    print(f"    美板块跌时A板块跟跌概率: {follow_down:.1f}%")
    print(f"    美板块涨时A板块跟涨概率: {follow_up:.1f}%")
    if not np.isnan(big_follow_down):
        print(f"    美大跌>1.5%时A跟跌概率: {big_follow_down:.1f}% ({len(us_big_neg)}次)")
    if not np.isnan(big_follow_up):
        print(f"    美大涨>1.5%时A跟涨概率: {big_follow_up:.1f}% ({len(us_big_pos)}次)")
    print(f"    ──────────────────────────────")
    print(f"    美跌时A板块均值: {avg_cn_when_us_down:+.2f}%")
    print(f"    美涨时A板块均值: {avg_cn_when_us_up:+.2f}%")
    print(f"    ──────────────────────────────")
    print(f"    信息增益(跌): {gain_down:+.1f}%")
    print(f"    信息增益(涨): {gain_up:+.1f}%")

# ========================================================
# 4. 汇总排名
# ========================================================
print("\n\n" + "=" * 70)
print("  🏆 板块传导力排名")
print("=" * 70)

if results:
    results_df = pd.DataFrame(results)
    
    # 按传导强度排序（同向率+相关系数综合）
    results_df['score'] = results_df['corr'].abs() * 0.5 + results_df['same_dir'] / 100 * 0.5
    results_df = results_df.sort_values('score', ascending=False)
    
    print(f"\n{'排名':>4} | {'板块':>8} | {'天数':>4} | {'相关系数':>10} | {'同向率':>8} | {'跟跌':>8} | {'跟涨':>8} | {'β系数':>8} | {'信息增益↓':>10}")
    print("-" * 85)
    
    for i, (_, r) in enumerate(results_df.iterrows()):
        print(f"  {i+1:>2}  | {r['sector']:>8} | {int(r['n_days']):>4} | {r['corr']:>+9.4f} | {r['same_dir']:>7.1f}% | {r['follow_down']:>7.1f}% | {r['follow_up']:>7.1f}% | {r['beta']:>+7.4f} | {r['gain_down']:>+9.1f}%")
    
    # 最佳和最差传导
    best = results_df.iloc[0]
    worst = results_df.iloc[-1]
    
    print(f"\n  ✅ 传导最强: {best['sector']} (同向率{best['same_dir']:.1f}%, 相关系数{best['corr']:+.4f})")
    print(f"  ❌ 传导最弱: {worst['sector']} (同向率{worst['same_dir']:.1f}%, 相关系数{worst['corr']:+.4f})")
    print(f"  ⚠ A股独立性强的板块: {', '.join(results_df[results_df['same_dir'] < 52]['sector'].tolist())}")

# ========================================================
# 5. 热点板块传导分析
# ========================================================
print("\n\n" + "=" * 70)
print("  🔥 热点板块传导深度分析")
print("  （美板块当日TOP3热门 → A股次日同板块表现）")
print("=" * 70)

for sector_name, mapping in SECTOR_MAP.items():
    us_syms_ok = [s for s in mapping['us_stocks'] if s in us_data]
    cn_bnames_ok = [b for b in mapping['cn_boards'] if b in cn_board_data]
    if len(us_syms_ok) == 0 or len(cn_bnames_ok) == 0:
        continue
    
    # 美股板块综合
    us_combined = None
    for sym in us_syms_ok:
        d = us_data[sym][['date', 'pct']].copy().rename(columns={'pct': sym})
        if us_combined is None:
            us_combined = d
        else:
            us_combined = us_combined.merge(d, on='date', how='outer')
    
    us_combined['us_sector_pct'] = us_combined[[s for s in us_syms_ok]].mean(axis=1)
    
    # A股板块综合
    cn_combined = None
    for bname in cn_bnames_ok:
        d = cn_board_data[bname][['date', 'pct']].copy().rename(columns={'pct': bname})
        if cn_combined is None:
            cn_combined = d
        else:
            cn_combined = cn_combined.merge(d, on='date', how='outer')
    
    cn_combined['cn_sector_pct'] = cn_combined[[b for b in cn_bnames_ok]].mean(axis=1)
    
    # 对齐
    us_combined = us_combined.sort_values('date')
    cn_combined = cn_combined.sort_values('date')
    us_dates_list = us_combined['date'].tolist()
    
    def prev_us(d):
        p = [x for x in us_dates_list if x < d]
        return p[-1] if p else None
    
    cn_combined['us_date'] = cn_combined['date'].apply(prev_us)
    merged2 = cn_combined.merge(us_combined[['date', 'us_sector_pct']].rename(columns={'date': 'us_date'}), on='us_date', how='inner')
    merged2 = merged2.dropna()
    
    if len(merged2) < 10:
        continue
    
    # 找"热点日": 美股该板块涨幅排名前20%的日子
    top_pct = merged2['us_sector_pct'].quantile(0.8)
    hot_days = merged2[merged2['us_sector_pct'] >= top_pct]
    
    if len(hot_days) >= 5:
        hot_follow_up = (hot_days['cn_sector_pct'] > 0).mean() * 100
        hot_avg = hot_days['cn_sector_pct'].mean()
        hot_pos_avg = hot_days[hot_days['cn_sector_pct'] > 0]['cn_sector_pct'].mean() if len(hot_days[hot_days['cn_sector_pct'] > 0]) > 0 else 0
        print(f"\n  {sector_name}:")
        print(f"    热点日(涨幅≥{top_pct:+.2f}%)共{len(hot_days)}天")
        print(f"    次日A跟涨概率: {hot_follow_up:.1f}%")
        print(f"    次日A板块平均: {hot_avg:+.2f}%")
        print(f"    跟涨日中均值: {hot_pos_avg:+.2f}%")

# ========================================================
# 6. 季度变化趋势
# ========================================================
print("\n\n" + "=" * 70)
print("  📅 传导率季度变化（部分板块）")
print("=" * 70)

for top_sector in ['半导体', 'AI科技', '中概互联', '金融']:
    mapping = SECTOR_MAP.get(top_sector)
    if not mapping:
        continue
    us_syms_ok = [s for s in mapping['us_stocks'] if s in us_data]
    cn_bnames_ok = [b for b in mapping['cn_boards'] if b in cn_board_data]
    if len(us_syms_ok) < 2 or len(cn_bnames_ok) < 2:
        continue
    
    # 美股综合
    us_c = None
    for sym in us_syms_ok:
        d = us_data[sym][['date', 'pct']].copy().rename(columns={'pct': sym})
        if us_c is None: us_c = d
        else: us_c = us_c.merge(d, on='date', how='outer')
    us_c['us_pct'] = us_c[[s for s in us_syms_ok]].mean(axis=1)
    
    # A股综合
    cn_c = None
    for b in cn_bnames_ok:
        d = cn_board_data[b][['date', 'pct']].copy().rename(columns={'pct': b})
        if cn_c is None: cn_c = d
        else: cn_c = cn_c.merge(d, on='date', how='outer')
    cn_c['cn_pct'] = cn_c[[b for b in cn_bnames_ok]].mean(axis=1)
    
    # 对齐
    us_c = us_c.sort_values('date')
    cn_c = cn_c.sort_values('date')
    us_dl = us_c['date'].tolist()
    cn_c['us_date'] = cn_c['date'].apply(lambda d: [x for x in us_dl if x < d][-1] if len([x for x in us_dl if x < d]) > 0 else None)
    m = cn_c.merge(us_c[['date', 'us_pct']].rename(columns={'date': 'us_date'}), on='us_date', how='inner').dropna()
    
    if len(m) < 15:
        continue
    
    m['month'] = m['date'].dt.month
    monthly_stats = m.groupby('month').agg(
        n=('us_pct', 'count'),
        same_dir=('us_pct', lambda x: ((x > 0) & (m.loc[x.index, 'cn_pct'] > 0) | (x < 0) & (m.loc[x.index, 'cn_pct'] < 0)).mean() * 100),
        corr=('us_pct', lambda x: x.corr(m.loc[x.index, 'cn_pct']))
    ).reset_index()
    
    print(f"\n  {top_sector}:")
    print(f"  {'月份':>4} | {'天数':>4} | {'同向率':>8} | {'相关系数':>10}")
    for _, r in monthly_stats.iterrows():
        print(f"  {int(r['month']):>2}月  | {int(r['n']):>4} | {r['same_dir']:>7.1f}% | {r['corr']:>+9.4f}")

# ========================================================
# 7. 综合评价与因子建议
# ========================================================
print("\n\n" + "=" * 70)
print("  🎯 综合评价与选股因子建议")
print("=" * 70)

print("""
【核心发现】
""")

if len(results) > 0:
    rf = results_df
    # 列出强传导板块
    strong = rf[rf['same_dir'] >= 58]
    weak = rf[rf['same_dir'] < 52]
    
    if len(strong) > 0:
        print(f"  ✅ 强传导板块（同向率≥58%）：")
        for _, r in strong.iterrows():
            print(f"     {r['sector']}: 同向率{r['same_dir']:.1f}%, β={r['beta']:+.4f}, 信息增益+gain_down={r['gain_down']:+.1f}%")
    
    print(f"""
【选股因子建议】

1️⃣ 美板块热点 → A股早盘加分项
   前一晚美股**{strong.iloc[0]['sector'] if len(strong) > 0 else '半导体'}**涨>1.5%，次日A股同板块可加分+5~10分

2️⃣ 传导分级
   第一梯队（强传导）：{', '.join(strong['sector'].tolist()) if len(strong) > 0 else '无'}
   第二梯队（中等）：{', '.join(rf[(rf['same_dir'] >= 52) & (rf['same_dir'] < 58)]['sector'].tolist()) if len(rf[(rf['same_dir'] >= 52) & (rf['same_dir'] < 58)]) > 0 else '无'}
   第三梯队（弱/独立）：{', '.join(weak['sector'].tolist()) if len(weak) > 0 else '无'}

3️⃣ 用法示例（加入评分系统）：
   if 美股_半导体 > 1.5% and 候选股 in 半导体板块:
       score += 8  # 板块共振加分
   elif 美股_半导体 > 0.5% and 候选股 in 半导体板块:
       score += 3  # 温和传导加分
   elif 美股_半导体 < -1%:
       score -= 5  # 谨慎扣分

4️⃣ 注意事项
   - 传导不是必然的，A股有独立行情日
   - 同向率50~60%意味着有参考价值但不是确定性
   - 季度间波动大，需实时校准
   - 最佳用法：组合多因子（板块+资金流+技术面）
""")

print("\n✓ 分析完成")
print(f"✓ 成功分析 {len(results)} 个板块对")
