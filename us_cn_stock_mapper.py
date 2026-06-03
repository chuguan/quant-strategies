#!/usr/bin/env python3
"""
美股→A股个股映射 + 好心态股票池
输出：基于美股表现的A股具体个股建议
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import akshare as ak
import numpy as np
from datetime import datetime

# ============================
# 一、美股→A股直接映射库
# ============================
# 每只美股对应最直接相关的A股个股（代码+名称+理由）
US_TO_CN_MAP = {
    # === AI/软件 ===
    'MSFT': {
        'name': '微软',
        'cn_stocks': [
            ('688111', '金山办公', 'A股最接近微软Office的产品'),
            ('002230', '科大讯飞', 'AI语音+大模型龙头'),
            ('600588', '用友网络', '企业级软件龙头'),
            ('600570', '恒生电子', '金融IT+AI应用'),
            ('300496', '中科创达', 'AI终端操作系统'),
        ]
    },
    'META': {
        'name': 'Meta',
        'cn_stocks': [
            ('002517', '恺英网络', 'AI+游戏/社交'),
            ('300418', '昆仑万维', 'AI+社交/大模型'),
            ('603444', '吉比特', '游戏+AI应用'),
        ]
    },
    # === 半导体 ===
    'NVDA': {
        'name': '英伟达',
        'cn_stocks': [
            ('688041', '海光信息', '国产GPU/AI芯片龙头'),
            ('603986', '兆易创新', '存储芯片+MCU'),
            ('002371', '北方华创', '半导体设备龙头'),
            ('688012', '中微公司', '刻蚀设备龙头'),
        ]
    },
    'AMD': {
        'name': 'AMD',
        'cn_stocks': [
            ('688981', '中芯国际', '晶圆代工龙头'),
            ('600584', '长电科技', '芯片封装龙头'),
            ('300661', '圣邦股份', '模拟芯片设计'),
        ]
    },
    'INTC': {
        'name': '英特尔',
        'cn_stocks': [
            ('688981', '中芯国际', '晶圆代工'),
            ('600171', '上海贝岭', 'IDM芯片'),
            ('300782', '卓胜微', '射频芯片'),
        ]
    },
    # === 新能源车 ===
    'TSLA': {
        'name': '特斯拉',
        'cn_stocks': [
            ('002594', '比亚迪', '国内新能源车绝对龙头'),
            ('601127', '赛力斯', '问界系列+华为合作'),
            ('603786', '科博达', '汽车电子零部件'),
        ]
    },
    'RIVN': {
        'name': 'Rivian',
        'cn_stocks': [
            ('601633', '长城汽车', 'SUV/皮卡+海外布局'),
            ('002920', '德赛西威', '智能座舱+自动驾驶'),
            ('300750', '宁德时代', '动力电池全球龙头'),
        ]
    },
    # === 中概互联 ===
    'BABA': {
        'name': '阿里巴巴',
        'cn_stocks': [
            ('300059', '东方财富', '互联网券商+基金'),
            ('688111', '金山办公', '云计算+SaaS'),
            ('002024', 'ST易购', '但ST的不能买... 换'),
        ]
    },
    'JD': {
        'name': '京东',
        'cn_stocks': [
            ('002024', 'ST易购', '但别买'),
            ('603708', '家家悦', '零售/超市'),
        ]
    },
    # === 消费电子 ===
    'AAPL': {
        'name': '苹果',
        'cn_stocks': [
            ('002475', '立讯精密', '苹果供应链核心'),
            ('601138', '工业富联', '苹果代工+AI服务器'),
            ('300433', '蓝思科技', '玻璃盖板+外观件'),
        ]
    },
    # === 科技综合 ===
    'GOOGL': {
        'name': '谷歌',
        'cn_stocks': [
            ('002230', '科大讯飞', 'AI+搜索技术'),
            ('688111', '金山办公', '云服务'),
        ]
    },
    # === AI基础设施 ===
    'AVGO': {
        'name': '博通',
        'cn_stocks': [
            ('603501', '韦尔股份', '芯片设计+模拟'),
            ('300782', '卓胜微', '射频前端'),
        ]
    },
}

# ============================
# 二、好心态股票池（防御/高分红）
# ============================
DEFENSIVE_STOCKS = [
    ('600900', '长江电力', '水电龙头，股息率~3.5%，每年稳定分红', '高股息防御'),
    ('601088', '中国神华', '煤炭+电力，股息率~5%+，央企分红王', '高股息防御'),
    ('601398', '工商银行', '宇宙行，股息率~6%，稳定分红20年', '银行高息'),
    ('601939', '建设银行', '大行龙头，股息率~5.5%', '银行高息'),
    ('600941', '中国移动', '电信龙头+AI算力，股息率~4%', '电信稳定'),
    ('600519', '贵州茅台', 'A股股王，业绩确定性强，分红逐年增加', '消费龙头'),
    ('000858', '五粮液', '浓香白酒老二，分红稳定', '消费龙头'),
    ('600887', '伊利股份', '乳业龙头，股息率~3.5%', '消费稳定'),
    ('601006', '大秦铁路', '铁路运输垄断，股息率~6%', '高股息防御'),
    ('600585', '海螺水泥', '水泥龙头，股息率~5%', '周期高息'),
    ('601857', '中国石油', '能源央企，股息率~4%', '能源高息'),
    ('600028', '中国石化', '石化央企，股息率~5%', '能源高息'),
    ('601328', '交通银行', '股息率~5.5%', '银行高息'),
    ('000002', '万科A', '地产龙头（但需注意行业风险）', '地产周期'),
    ('600036', '招商银行', '股份行龙头，股息率~4%', '银行优质'),
    ('601166', '兴业银行', '股份行，股息率~5%', '银行高息'),
    ('600690', '海尔智家', '家电龙头，股息率~3%，全球化布局', '消费稳定'),
    ('000333', '美的集团', '家电龙头，股息率~3.5%', '消费稳定'),
    ('601225', '陕西煤业', '煤炭，股息率~6%+', '高股息防御'),
    ('600809', '山西汾酒', '清香白酒龙头，业绩增长稳定', '消费成长'),
]

# ============================
# 三、板块分类索引
# ============================
SECTOR_TO_STOCKS = {
    'AI软件': ['002230','688111','600588','600570','300496'],
    '半导体': ['688981','002371','603986','600584','688012','603501'],
    '新能源车': ['002594','601127','601633','300750'],
    '消费电子': ['002475','601138','300433'],
    '银行高息': ['601398','601939','601328','600036','601166'],
    '高股息防御': ['600900','601088','601006','601225'],
    '消费稳定': ['600519','000858','600887','600690','000333'],
}

def get_us_stock_data():
    """获取实时美股数据"""
    result = {}
    for sym in US_TO_CN_MAP.keys():
        try:
            df = ak.stock_us_daily(symbol=sym, adjust='')
            last2 = df.tail(2)
            if len(last2) >= 2:
                p1 = float(last2.iloc[-2]['close'])
                c1 = float(last2.iloc[-1]['close'])
                result[sym] = (c1/p1 - 1) * 100
            else:
                result[sym] = 0
        except:
            result[sym] = 0
    return result

def recommend_stocks(us_data):
    """
    基于美股表现推荐A股个股
    返回: {利好: [(code, name, reason)], 利空: [(code, name, reason)]}
    """
    bullish = []
    bearish = []
    
    for sym, pct in us_data.items():
        if sym not in US_TO_CN_MAP:
            continue
        info = US_TO_CN_MAP[sym]
        
        if pct > 1.5:
            # 大涨→传导利好
            for code, name, reason in info['cn_stocks']:
                bullish.append((code, name, f'{info["name"]} +{pct:.1f}% → {reason}'))
        elif pct < -1.5:
            # 大跌→传导利空
            for code, name, reason in info['cn_stocks']:
                bearish.append((code, name, f'{info["name"]} {pct:.1f}% → {reason}'))
    
    # 去重（同一只股票可能被多个US股绑定）
    seen_bullish = {}
    for code, name, reason in bullish:
        if code not in seen_bullish:
            seen_bullish[code] = (name, reason)
    
    seen_bearish = {}
    for code, name, reason in bearish:
        if code not in seen_bearish:
            seen_bearish[code] = (name, reason)
    
    return list(seen_bullish.values()), list(seen_bearish.values())

def get_top_defensive(n=5):
    """获取Top N个好心态股票"""
    return DEFENSIVE_STOCKS[:n]

if __name__ == '__main__':
    print('=== 获取美股数据 ===')
    us_data = get_us_stock_data()
    for sym, pct in sorted(us_data.items(), key=lambda x: -abs(x[1])):
        name = US_TO_CN_MAP.get(sym, {}).get('name', sym)
        arrow = '📈' if pct > 0 else '📉'
        mark = '🔥' if pct > 1.5 else '⚠️' if pct < -1.5 else ''
        print(f'  {name} {sym}: {pct:+.2f}% {arrow} {mark}')
    
    print(f'\n=== 推荐个股分析 ===')
    bullish, bearish = recommend_stocks(us_data)
    
    print(f'\n✅ 利好个股（美股大涨传导）：')
    if bullish:
        for i, (name, reason) in enumerate(bullish[:10], 1):
            print(f'  {i}. {name}')
            print(f'     理由: {reason}')
    else:
        print(f'  今日无明显传导利好')
    
    print(f'\n⚠️ 利空个股（美股大跌传导）：')
    if bearish:
        for i, (name, reason) in enumerate(bearish[:10], 1):
            print(f'  {i}. {name}')
            print(f'     理由: {reason}')
    else:
        print(f'  今日无明显传导利空')
    
    print(f'\n🛡️ 好心态股票（高股息+防御）：')
    for i, (code, name, desc, tag) in enumerate(get_top_defensive(8), 1):
        print(f'  {i}. {name} ({code}) — {desc}')
    
    print(f'\n📊 综合预测：')
    if 'MSFT' in us_data and us_data['MSFT'] > 3:
        print(f'  ▶ MSFT暴涨+{us_data["MSFT"]:.1f}% → AI软件重点关注！')
        print(f'    金山办公、科大讯飞、用友网络')
    if 'NVDA' in us_data and us_data['NVDA'] < -1:
        print(f'  ▶ NVDA跌{us_data["NVDA"]:.1f}% → 半导体短期谨慎')
        print(f'    海光信息、北方华创短期回避')
    if 'RIVN' in us_data and us_data['RIVN'] > 3:
        print(f'  ▶ RIVN暴涨+{us_data["RIVN"]:.1f}% → 新能源车关注')
        print(f'    比亚迪、赛力斯')
