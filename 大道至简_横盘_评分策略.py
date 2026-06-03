"""
📊 横盘子策略 V260529-07 — 大道至简
macd_w=0.2 + vr_b=4 + KDJ金叉
"""
NAME = "横盘子策略"
MARKET = "flat"

SELECT = {
    'p_min': 0, 'p_max': 7,
    'vr_min': 0.6, 'vr_max': 2.5,
    'hs_min': 3, 'hs_max': 20,
    'sz_max': 200,
    'cl_min': 40, 'cl_max': 95,
}

SCORE = {
    'p_w': 2.0,
    'cl_w': 0.05,
    'macd_w': 0.2,
    'ma5_b': 2,
    'vr_b': 6,
    'hs_b': 0.3,
    'wr_b': 0,
    'j_b': 0,
    'j_low_b': 2,
}

LEVELS = [
    {'name':'L0','p_min':0,'p_max':7,'vr_min':0.6,'vr_max':2.5,'hs_min':3,'hs_max':20,'sz_max':200,'cl_min':40,'cl_max':95},
    {'name':'L1','p_min':-1,'p_max':7,'vr_min':0.5,'vr_max':3.0,'hs_min':2,'hs_max':25,'sz_max':200,'cl_min':30,'cl_max':95},
    {'name':'L2','p_min':-2,'p_max':7,'vr_min':0.4,'vr_max':3.5,'hs_min':1,'hs_max':30,'sz_max':300,'cl_min':20,'cl_max':98},
    {'name':'L3','p_min':-3,'p_max':7,'vr_min':0.3,'vr_max':4.0,'hs_min':0.5,'hs_max':35,'sz_max':400,'cl_min':10,'cl_max':99},
    {'name':'L4','p_min':-5,'p_max':7,'vr_min':0.2,'vr_max':5.0,'hs_min':0.3,'hs_max':40,'sz_max':500,'cl_min':0,'cl_max':100},
]
LEVEL_PENALTY = [0, -1, -2, -3, -5]

BACKTEST = "V260529-07"

def 横盘_评分(stock):
    p = stock['p']; cl = stock['cl']; vr = stock['vr']; hsl = stock['hsl']
    dif = stock['dif']; mg = stock['mg']; a5 = stock['a5']
    jv = stock['jv']; kv = stock['kv']; dv = stock['dv']
    kdj_g = stock['kdj_g']; buy_c = stock['buy_c']
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
    score += (w['j_low_b'] if 20 <= jv <= 40 else 0)
    score += (2 if kdj_g else 0)
    
    # V260528: MACD势头加分
    if dif > 0.5: score += 3
    if mg: score += 3
    
    return round(score, 1)
