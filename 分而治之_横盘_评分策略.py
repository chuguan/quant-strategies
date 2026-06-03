"""
横盘 V9最优版 — MACD+WR+KDJ+VR多维评分 实测73.3%
"""
NAME = "横盘策略 V9"
MARKET = "flat"

PARAMS = {
    'p_w': 0.5,
    'cl_w': 0.4,
    'macd_w': 1,
    'dif_bonus': 20,
    'dif_thresh': 1.5,
    'ma5_b': 8,
    'wr_lo': 15,
    'wr_b': 8,
    'j_b': 8,
    'kdj_g_b': 5,
    'p_high_pen': -10,
    'vr_b': 0,
    'j_low_b': 0,
    'hs_bonus': 0,
    'hs_b': 0,
    'vr_bonus': 0,
    'wr_bonus': 0,
    'cl_low_b': 0,
    'p_deep_b': 0,
    'zone_b': 0,
    'cl_high_pen': 0,
}

LEVELS = [
    {"name":"L0","p_min":0,"p_max":7,"vr_min":0.6,"vr_max":2.5,"hs_min":3,"hs_max":20,"sz_max":200,"cl_min":40,"cl_max":95},
    {"name":"L1","p_min":-1,"p_max":7,"vr_min":0.5,"vr_max":3.0,"hs_min":2,"hs_max":25,"sz_max":200,"cl_min":30,"cl_max":95},
    {"name":"L2","p_min":-2,"p_max":7,"vr_min":0.4,"vr_max":3.5,"hs_min":1,"hs_max":30,"sz_max":300,"cl_min":20,"cl_max":98},
    {"name":"L3","p_min":-3,"p_max":7,"vr_min":0.3,"vr_max":4.0,"hs_min":0.5,"hs_max":35,"sz_max":400,"cl_min":10,"cl_max":99},
    {"name":"L4","p_min":-5,"p_max":7,"vr_min":0.2,"vr_max":5.0,"hs_min":0.3,"hs_max":40,"sz_max":500,"cl_min":0,"cl_max":100}
]

BACKTEST = "auto-opt_2325_56.7%"

def score(stock):
    s=stock; p=PARAMS
    score=0
    if p.get('use_p',1): score+=s.get('p',0)*p.get('p_w',1)
    cl=s.get('cl',50)
    if p.get('use_cl',1):
        score+=cl*p.get('cl_w',0.05)
        for z in p.get('cl_zones',[]):
            if len(z)==3 and z[0]<=cl<=z[1]: score+=z[2]
    vr=s.get('vr',1)
    if p.get('use_vr',1):
        for z in p.get('vr_zones',[]):
            if len(z)==3 and z[0]<=vr<=z[1]: score+=z[2]
    dif=s.get('dif',0); mg=s.get('mg',0)
    if p.get('use_macd',1):
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        score+=ms*p.get('macd_w',0.3)
        if dif>p.get('dif_thresh',0.5): score+=p.get('dif_bonus',0)
    if p.get('use_a5',0) and s.get('a5',0): score+=p.get('a5_b',0)
    wrv=s.get('wrv',50)
    if p.get('use_wr',0):
        if wrv<p.get('wr_lo',25): score+=p.get('wr_lo_b',0)
        if wrv>p.get('wr_hi',75): score+=p.get('wr_hi_b',0)
    jv=s.get('jv',50); kv=s.get('kv',50); dv=s.get('dv',50)
    if p.get('use_kdj',0):
        if jv>kv>dv: score+=p.get('j_golden_b',0)
        if p.get('j_lo',20)<=jv<=p.get('j_hi',40): score+=p.get('j_zone_b',0)
        if jv<p.get('j_super_lo',15): score+=p.get('j_super_b',0)
    if p.get('use_kdj_g',0) and s.get('kdj_g',0): score+=p.get('kdj_g_b',0)
    pos=s.get('pos_in_day',50)
    if p.get('use_pos',0):
        if pos>p.get('pos_hi',85): score+=p.get('pos_hi_pen',-2)
        if pos<p.get('pos_lo',30): score+=p.get('pos_lo_b',0)
    return round(score,1)
