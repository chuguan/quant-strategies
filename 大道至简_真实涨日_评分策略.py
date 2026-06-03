"""
💹 真实涨日子策略 V260528 — 大道至简
p_w=3.0 纯版（无透支惩罚）
"""
NAME = "真实涨日子策略"
MARKET = "real_up"

SELECT = {
    'p_min': 3, 'p_max': 7,
    'vr_min': 0.6, 'vr_max': 2.5,
    'hs_min': 5, 'hs_max': 15,
    'sz_max': 200,
    'cl_min': 60, 'cl_max': 90,
}

SCORE = {
    'p_w': 3.0,
    'cl_w': 0.05,
    'macd_w': 0.3,
    'ma5_b': 3,
    'vr_b': 1,
    'hs_b': 0.3,
    'wr_b': 2,
    'j_b': 2,
    'j_low_b': 2,
}

LEVELS = [
    {'name':'L0','p_min':3,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':5,'hs_max':15,'sz_max':200,'cl_min':60,'cl_max':90},
    {'name':'L1','p_min':2,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':3,'hs_max':20,'sz_max':200,'cl_min':50,'cl_max':95},
    {'name':'L2','p_min':1,'p_max':7,'vr_min':0.5,'vr_max':3.0,'hs_min':2,'hs_max':25,'sz_max':300,'cl_min':40,'cl_max':95},
]
LEVEL_PENALTY = [0, -1, -2]

BACKTEST = "V260528 p_w=3.0纯版"

def 真实涨日_评分(stock):
    p = stock['p']; cl = stock['cl']; vr = stock['vr']; hsl = stock['hsl']
    dif = stock['dif']; mg = stock['mg']; a5 = stock['a5']
    wrv = stock['wrv']; jv = stock['jv']; kv = stock['kv']; dv = stock['dv']
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
    score += (w['vr_b'] * 1.5 if 1.0 <= vr <= 1.5 else 0)
    score += (w['hs_b'] * 2 if 5 <= hsl <= 7 else 0)
    score += (w['wr_b'] if wrv < 25 else 0)
    score += (w['j_b'] if jv > kv > dv else 0)
    score += (w['j_low_b'] if 20 <= jv <= 40 else 0)
    
    # 附加奖励: CL甜蜜区+VR量比确认
    if 65 <= cl <= 83: score += 3
    if 1.0 <= vr <= 1.3: score += 3
    
    return round(score, 1)
