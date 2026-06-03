#!/usr/bin/env python3
"""
V43 US加成层 — 在V42评分基础上，叠加美股昨晚板块传导加分
不改V42任何代码，独立运行
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

# ===== V42路径 =====
V42_DIR = os.path.join(os.path.dirname(__file__), 'release', 'V42')
sys.path.insert(0, V42_DIR)

import akshare as ak
import numpy as np
from datetime import datetime

# ============================================
# 一、关键板块→个股映射库（按THS行业分类）
# ============================================
# 每个板块标注：对应的美股传导股 + 加成权重
SECTOR_MAP = {
    '半导体': {
        'us_codes': ['NVDA', 'AMD', 'INTC'],
        'bonus_weight': 1.0,
        'threshold': 1.5,  # 美涨超1.5%才加成
        'penalty_threshold': -1.0,
        'stocks': [
            '688981','002371','603986','600584','688012','603501',
            '300661','300782','600171','688041','688008','688396',
            '603893','600703','300223','002049','300474','688126',
            '688099','002156','688728','688072','300672','688234',
            '300666','688689','603005','002185','300458',
        ]
    },
    'AI科技/软件': {
        'us_codes': ['MSFT', 'META', 'GOOGL'],
        'bonus_weight': 0.8,
        'threshold': 1.0,
        'penalty_threshold': -1.5,
        'stocks': [
            '688111','002230','600588','600570','300496','002517',
            '300418','603444','002624','300033','300454','300188',
            '300624','002368','600536','603138','688568','688369',
            '300369','002410',
        ]
    },
    '新能源车/汽车': {
        'us_codes': ['TSLA', 'RIVN'],
        'bonus_weight': 0.7,
        'threshold': 2.0,
        'penalty_threshold': -2.0,
        'stocks': [
            '002594','601127','601633','000625','300750','002920',
            '002085','600733','600104','000800','601238','002050',
            '600741','002126','601689','002048','002472',
        ]
    },
    '消费电子': {
        'us_codes': ['AAPL'],
        'bonus_weight': 0.9,
        'threshold': 1.0,
        'penalty_threshold': -1.5,
        'stocks': [
            '002475','601138','300433','002241','002600','603160',
            '300136','002273','002635','601231','002387','002861',
        ]
    },
    '中概互联': {
        'us_codes': ['BABA', 'JD', 'BIDU'],
        'bonus_weight': 0.6,
        'threshold': 1.5,
        'penalty_threshold': -1.5,
        'stocks': [
            '300059','002024','300226','300295','603888',
            '002131','002555','300315','002602','300413',
        ]
    },
    '军工': {
        'us_codes': ['LMT', 'RTX'],
        'bonus_weight': 0.3,  # 负相关，权重低
        'threshold': 2.0,
        'penalty_threshold': -2.0,
        'stocks': [
            '600760','600893','600862','002179','600185','600118',
            '600879','000768','600391','002013','300699','600765',
        ]
    },
    '金融/银行': {
        'us_codes': ['JPM', 'GS', 'BAC'],
        'bonus_weight': 0.5,
        'threshold': 1.0,
        'penalty_threshold': -1.5,
        'stocks': [
            '601398','601939','601328','600036','601166','600016',
            '000001','002142','601818','600015','601009','601229',
            '601211','600030','601688','601066','002736',
        ]
    },
    '油气能源': {
        'us_codes': ['XOM', 'CVX'],
        'bonus_weight': 0.4,
        'threshold': 1.5,
        'penalty_threshold': -2.0,
        'stocks': [
            '601857','600028','600256','600759','600688','000059',
            '002554','600026','601872','600026',
        ]
    },
}

# 反向查找：股票代码→所属板块
CODE_TO_SECTOR = {}
for sector, info in SECTOR_MAP.items():
    for code in info['stocks']:
        CODE_TO_SECTOR[code] = sector

# ============================================
# 二、获取美股昨夜数据
# ============================================
def get_us_overnight():
    """获取美股关键个股昨夜的涨跌幅"""
    all_stocks = set()
    for info in SECTOR_MAP.values():
        all_stocks.update(info['us_codes'])
    
    us_data = {}
    for sym in sorted(all_stocks):
        try:
            df = ak.stock_us_daily(symbol=sym, adjust='')
            last2 = df.tail(2)
            if len(last2) >= 2:
                p1 = float(last2.iloc[-2]['close'])
                c1 = float(last2.iloc[-1]['close'])
                us_data[sym] = (c1/p1 - 1) * 100
            else:
                us_data[sym] = 0
        except:
            us_data[sym] = 0
    return us_data

# ============================================
# 三、US加成计算
# ============================================
def calc_us_bonus(stock_code, us_data):
    """
    对单只股票计算US加成分数
    返回: (bonus, reason)
    """
    sector = CODE_TO_SECTOR.get(stock_code)
    if not sector:
        return 0, ''
    
    info = SECTOR_MAP.get(sector)
    if not info:
        return 0, ''
    
    us_syms = info['us_codes']
    pcts = [us_data.get(s, 0) for s in us_syms]
    max_pct = max(pcts)  # 取最大值（只要有一只大涨就是信号）
    avg_pct = np.mean(pcts)
    
    bonus = 0
    reason_detail = ''
    
    # 板块内任何一只龙头大涨就加分（用max）
    if max_pct > info['threshold']:
        bonus = int(max_pct * info['bonus_weight'] * 7)
        if bonus > 15: bonus = 15
        if bonus < 3: bonus = 3
        pct_str = '+'.join([f'{s}{us_data.get(s,0):+.1f}%' for s in us_syms])
        reason_detail = f'🎯【US传导】{sector}：板块最高{max_pct:+.1f}%(#{pct_str}) → +{bonus}分'
    
    # 板块内整体恶化才扣分（用avg）
    elif avg_pct < info['penalty_threshold']:
        bonus = int(abs(avg_pct) * info['bonus_weight'] * 4)
        if bonus > 10: bonus = 10
        if bonus < 2: bonus = 2
        bonus = -bonus
        pct_str = '+'.join([f'{s}{us_data.get(s,0):+.1f}%' for s in us_syms])
        reason_detail = f'⚠️【US传导】{sector}：板块均值{avg_pct:+.1f}%(#{pct_str}) → {bonus}分'
    
    return bonus, reason_detail

# ============================================
# 四、对V42候选池批量加成
# ============================================
def apply_us_bonus_to_candidates(candidates):
    """
    给V42选出的候选股列表加US分
    candidates: [(code, name, score, price, pct, ...), ...]
    返回: [(code, name, original_score, us_bonus, final_score, reason, ...)]
    """
    # 获取美股数据
    print('📡 获取美股板块数据...', end=' ', flush=True)
    us_data = get_us_overnight()
    print('OK')
    
    # 输出美股板块概况
    print(f'\n  🔥 美股板块表现：')
    sectors_avg = {}
    for sector, info in SECTOR_MAP.items():
        pcts = [us_data.get(s, 0) for s in info['us_codes']]
        if pcts:
            avg = np.mean(pcts)
            mark = '🔥' if avg > 1.5 else '📊' if avg > 0 else '❄️' if avg > -1 else '⚠️'
            print(f'     {sector}: {avg:+.2f}% {mark}')
            sectors_avg[sector] = avg
    
    print()
    
    # 给每个候选股算US加分
    results = []
    for c in candidates:
        if len(c) >= 2:
            code = c[0]
            bonus, reason = calc_us_bonus(code, us_data)
            # 保持原结构不变，附加bonus和reason
            results.append((*c, bonus, reason))
        else:
            results.append((*c, 0, ''))
    
    return results

# ============================================
# 五、独立运行入口（测试用）
# ============================================
if __name__ == '__main__':
    print('='*60)
    print('  V43 US加成层测试')
    print('='*60)
    
    us_data = get_us_overnight()
    
    print(f'\n📊 美股板块传导概况：')
    print(f'{"="*50}')
    for sector, info in SECTOR_MAP.items():
        pcts = [us_data.get(s, 0) for s in info['us_codes']]
        if pcts:
            avg = np.mean(pcts)
            pct_str = ' | '.join([f'{s}{p:+.1f}%' for s, p in zip(info['us_codes'], pcts)])
            if avg > info['threshold']:
                print(f'  🔥 {sector}: {avg:+.2f}% → ✅ 传导利好')
                print(f'     {pct_str}')
            elif avg < info['penalty_threshold']:
                print(f'  ⚠️ {sector}: {avg:+.2f}% → ❌ 传导利空')
                print(f'     {pct_str}')
            else:
                print(f'  📊 {sector}: {avg:+.2f}% → ◻️ 中性')
    
    print(f'\n📌 部分个股US加成示例：')
    test_codes = ['688111', '002230', '002594', '688981', '601127', '300059']
    for code in test_codes:
        bonus, reason = calc_us_bonus(code, us_data)
        name = {'688111':'金山办公','002230':'科大讯飞','002594':'比亚迪',
                '688981':'中芯国际','601127':'赛力斯','300059':'东方财富'}.get(code, code)
        if bonus != 0:
            print(f'  {name}({code}): V42分 + US加成{bonus:+d}分')
            print(f'    {reason}')
    
    print(f'\n✅ V43 US加成层就绪')
