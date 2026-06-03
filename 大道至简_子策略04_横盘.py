"""
➖ 横盘子策略 — 大道至简
选股条件 + 评分公式一对一
"""
NAME = "横盘子策略"
MARKET = "flat"  # 大盘平均涨幅-0.5%~0.5%（非涨非跌）

# ===== 选股条件（L0严格级） =====
SELECT = {
    'p_min': 0, 'p_max': 7,       # 涨幅0%~7%（<8%限制）
    'vr_min': 0.6, 'vr_max': 2.5, # 量比0.6~2.5
    'hs_min': 3, 'hs_max': 20,    # 换手3%~20%
    'sz_max': 200,                 # 市值<200亿
    'cl_min': 40, 'cl_max': 95,   # CL 40%~95%
}

# ===== 评分公式权重 =====
SCORE = {
    'p_w': 1.5,    # 涨幅权重
    'cl_w': 0.05,  # CL权重
    'macd_w': 0.3, # MACD权重
    'ma5_b': 2,    # 站上MA5加分
    'vr_b': 1,     # 量比1~1.5加分系数
    'hs_b': 0.3,   # 换手5~7%加分系数
    'wr_b': 0,     # WR加分
    'j_b': 0,      # J>70加分
    'j_low_b': 2,  # J<20加分
}

# 评分公式说明
# score = p×1.5 + CL×0.05 + 价格分×0.3 + MACD×0.3
#       + (MA5站上? +2 : 0)
#       + (VR 1.0~1.5? +1.5 : 0)
#       + (换手5~7%? +0.6 : 0)
#       + (J<20? +2 : 0)  ← 超卖反转信号
# 价格分 = min(10, max(1, 11-买入价/10))

# 分级放宽阶梯（L0~L4）
LEVELS = [
    {'name':'L0','p_min':0,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':3,'hs_max':20,'sz_max':200,'cl_min':40,'cl_max':95},
    {'name':'L1','p_min':-1,'p_max':7,'vr_min':0.5,'vr_max':3.0,'hs_min':2,'hs_max':25,'sz_max':200,'cl_min':30,'cl_max':95},
    {'name':'L2','p_min':-2,'p_max':7,'vr_min':0.4,'vr_max':3.5,'hs_min':1,'hs_max':30,'sz_max':300,'cl_min':20,'cl_max':98},
    {'name':'L3','p_min':-3,'p_max':7,'vr_min':0.3,'vr_max':4.0,'hs_min':0.5,'hs_max':35,'sz_max':400,'cl_min':10,'cl_max':99},
    {'name':'L4','p_min':-5,'p_max':7,'vr_min':0.2,'vr_max':5.0,'hs_min':0.3,'hs_max':40,'sz_max':500,'cl_min':0,'cl_max':100},
]
LEVEL_PENALTY = [0, -1, -2, -3, -5]

# 回测战绩
BACKTEST = "124天 冠军64.5% Top390.3%"
