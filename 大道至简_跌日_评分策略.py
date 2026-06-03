"""
📉 跌日子策略 V260529-11 — 大道至简（v2）
突破：重构评分方向——跌日选"反弹票"而非"强势票"
核心发现：跌日冠军n=10%的都是p=1-3% cl=18-71%的冷门票
         评分冠军反而n=1-3%（高p高CL已透支）
修正：降低p_w权重 + CL中区奖励 + 超卖/超跌保留
"""
NAME = "跌日子策略"
MARKET = "down"

# ===== 选股条件（L0严格级） =====
SELECT = {
    'p_min': -3, 'p_max': 7,
    'vr_min': 0.4, 'vr_max': 3.5,
    'hs_min': 1, 'hs_max': 30,
    'sz_max': 300,
    'cl_min': 10, 'cl_max': 98,
}

# ===== 评分公式权重 =====
# 核心逻辑：跌日追反弹而非追强势
SCORE = {
    'p_w': 1.0,     # 涨幅权重（历史最优p_w=1.0）
    'cl_w': 0.1,    # CL权重（提升区分度）
    'macd_w': 0.3,  # MACD权重
    'ma5_b': 2,     # 站上MA5加分
    'hs_bonus': 4,  # HSL≥5加分（失败分析：换手高+1.8）
    'vr_bonus': 3,  # VR0.6-1.0加分
    'wr_bonus': 3,  # WR>75超卖加分
    'cl_low_b': 3,  # CL<15超跌加分
    'p_deep_b': 2,  # p<-3深跌加分
    'zone_b': 3,    # CL中区50-75%加分
    'cl_high_pen': -5, # CL>85高区惩罚（加强！输家CL 71.8）
    'p_high_pen': -2,  # p>=6透支惩罚（加强）
    'mg_bonus': 3,  # MACD金叉加分（赢家47% vs 输家35%）
}

LEVELS = [
    {'name':'L1','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'hs_min':5,'hs_max':20,'sz_max':150,'cl_min':40,'cl_max':90,'a5_req':1,'kdj_g_req':1},
    {'name':'L2','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':1.5,'hs_min':5,'hs_max':20,'sz_max':150,'cl_min':40,'cl_max':90,'a5_req':1},
    {'name':'L3','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':2.0,'hs_min':3,'hs_max':25,'sz_max':200,'cl_min':30,'cl_max':95},
    {'name':'L4','p_min':0,'p_max':7,'vr_min':0.5,'vr_max':2.5,'hs_min':2,'hs_max':30,'sz_max':300,'cl_min':20,'cl_max':98},
    {'name':'L5','p_min':-10,'p_max':7,'vr_min':0.1,'vr_max':10,'hs_min':0.1,'hs_max':100,'sz_max':10000,'cl_min':0,'cl_max':100},
]

def 跌日_评分(stock):
    """跌日评分 V260529-11v2：反弹票优先+CL中区+超卖确认"""
    p = stock['p']; cl = stock['cl']; vr = stock['vr']; hsl = stock['hsl']
    dif = stock['dif']; mg = stock['mg']; a5 = stock['a5']
    wrv = stock['wrv']; jv = stock['jv']
    buy_c = stock['buy_c']
    w = SCORE

    ms = 0
    if mg and dif > 0.5: ms = 10
    elif mg and dif > 0.2: ms = 8
    elif mg: ms = 6
    elif dif > 0.5: ms = 4
    elif dif > 0: ms = 2

    ps2 = min(10, max(1, 11 - buy_c / 10)) if buy_c else 0

    score = p * w['p_w'] + cl * w['cl_w'] + ps2 * 0.3 + ms * w['macd_w']
    score += (w['ma5_b'] if a5 else 0)
    score += (w['hs_bonus'] if hsl >= 5 else 0)
    score += (w['vr_bonus'] if 0.6 <= vr <= 1.0 else 0)
    score += (w['wr_bonus'] if wrv > 75 else 0)
    score += (w['cl_low_b'] if cl < 15 else 0)
    score += (w['p_deep_b'] if p < -3 else 0)
    score += (w['zone_b'] if 50 <= cl <= 75 else 0)        # CL中区反弹最佳！n=10%的票CL都在50-75%
    score += (w['cl_high_pen'] if cl > 85 else 0)           # CL>85透支惩罚
    score += (w['p_high_pen'] if p >= 6.5 else 0)

    return round(score, 1)
