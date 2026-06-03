"""
🎭 虚涨日子策略 — 大道至简
选股条件 + 评分公式一对一
"""
NAME = "虚涨日子策略"
MARKET = "fake_up"  # 大盘涨>0.5% 但 热门股<15只 或 量比<0.9

# ===== 选股条件（L0严格级） =====
SELECT = {
    'p_min': 0, 'p_max': 6,       # 涨幅0%~6%（<8%限制）
    'vr_min': 0.6, 'vr_max': 2.5, # 量比0.6~2.5
    'hs_min': 5, 'hs_max': 20,    # 换手5%~20%
    'sz_max': 200,                 # 市值<200亿
    'cl_min': 30, 'cl_max': 95,   # CL 30%~95%
}

# ===== 评分公式权重 =====
SCORE = {
    'p_w': 1.0,    # 涨幅权重
    'cl_w': 0.05,  # CL权重
    'macd_w': 0.5, # MACD权重
    'ma5_b': 0,    # 站上MA5加分
    'vr_b': 0,     # 量比加分
    'hs_b': 0,     # 换手加分
    'wr_b': 0,     # WR加分
    'j_b': 0,      # J>70加分
    'j_low_b': 0,  # J<20加分
}

# 评分公式说明
# score = p×1.0 + CL×0.05 + 价格分×0.3 + MACD×0.5
# 价格分 = min(10, max(1, 11-买入价/10))

# 分级放宽阶梯（L0~L4）
LEVELS = [
    {'name':'L1','p_min':4,'p_max':7,'vr_min':0.6,'vr_max':2.0,'hs_min':5,'hs_max':20,'sz_max':200,'cl_min':30,'cl_max':90},
    {'name':'L2','p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':20,'sz_max':200,'cl_min':30,'cl_max':95},
    {'name':'L3','p_min':2,'p_max':7,'vr_min':0.5,'vr_max':2.5,'hs_min':3,'hs_max':25,'sz_max':300,'cl_min':20,'cl_max':95},
    {'name':'L4','p_min':0,'p_max':7,'vr_min':0.3,'vr_max':5.0,'hs_min':1,'hs_max':40,'sz_max':500,'cl_min':5,'cl_max':98},
    {'name':'L5','p_min':-10,'p_max':7,'vr_min':0.1,'vr_max':10,'hs_min':0.1,'hs_max':100,'sz_max':10000,'cl_min':0,'cl_max':100},
]

# ===== 独立评分函数 =====
def 虚涨日_评分(stock):
    """虚涨日评分函数：极简，只靠MACD+涨幅，不加任何多余因子"""
    p = stock['p']; cl = stock['cl']; vr = stock['vr']; hsl = stock['hsl']
    dif = stock['dif']; mg = stock['mg']; a5 = stock['a5']
    buy_c = stock['buy_c']; w = SCORE
    
    ms = 0
    if mg and dif > 0.5: ms = 10
    elif mg and dif > 0.2: ms = 8
    elif mg: ms = 6
    elif dif > 0.5: ms = 4
    elif dif > 0: ms = 2
    
    ps2 = min(10, max(1, 11 - buy_c / 10)) if buy_c else 0
    score = p * w['p_w'] + cl * w['cl_w'] + ps2 * 0.3 + ms * w['macd_w']
    return round(score, 1)

# 回测战绩
BACKTEST = "17天 冠军88.2% Top3100.0%"
