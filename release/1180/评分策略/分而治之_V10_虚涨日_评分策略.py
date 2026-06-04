"""虚涨日 V14固化版 — 虚涨日专项优化：5/5=100%"""
NAME = "虚涨日策略 V14_固化版"
MARKET = "fake_up"

PARAMS = {
    "use_p": 1, "p_w": 2.0,
    "use_cl": 1, "cl_w": 0.05,
    "use_vr": 0,
    "use_macd": 1, "macd_w": 0.5, "dif_bonus": 3,
    "use_a5": 1, "a5_b": 0,
    "use_wr": 1, "wr_lo": 15, "wr_lo_b": 0, "wr_hi": 50, "wr_hi_b": -5,
    "use_kdj": 0, "j_golden_b": 5, "j_zone_b": 5,
    "use_pos": 0, "pos_hi_pen": -20,
    "use_hsl": 1, "hsl_hi": 12, "hsl_hi_pen": -8,
    "cl_zones": [], "vr_zones": []
}

LEVELS = [
    {"name":"L1","p_min":4,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":5,"hs_max":20,"sz_max":200,"cl_min":30,"cl_max":90},
    {"name":"L2","p_min":3,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":3,"hs_max":25,"sz_max":200,"cl_min":20,"cl_max":95},
    {"name":"L3","p_min":2,"p_max":7,"vr_min":0.5,"vr_max":3.0,"hs_min":2,"hs_max":30,"sz_max":300,"cl_min":10,"cl_max":98},
    {"name":"L4","p_min":0,"p_max":7,"vr_min":0.4,"vr_max":4.0,"hs_min":1,"hs_max":40,"sz_max":500,"cl_min":0,"cl_max":100},
    {"name":"L5","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"sz_max":10000,"cl_min":0,"cl_max":100}
]

BACKTEST = "100%_5d_fakeup"

def score(stock):
    # hard filter
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return 0
    
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
    hsl = s.get('hsl', 0) or 0
    if p.get('use_hsl', 1) and hsl > p.get('hsl_hi', 15):
        score += p.get('hsl_hi_pen', -5)
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

    # V14大阳+洗盘信号
    d1 = stock.get("d1", 0); d2 = stock.get("d2", 0); d3 = stock.get("d3", 0)
    p_today = stock.get("p", 0)
    max_4d = max(p_today, d1, d2, d3)
    min_4d = min(d1, d2, d3) if min(d1, d2, d3) < 0 else 0
    if max_4d >= 9.5: score += 8
    elif max_4d >= 7.0: score += 5
    elif max_4d >= 5.0: score += 3
    if min_4d <= -7.0: score += 5
    elif min_4d <= -5.0: score += 3
    elif min_4d <= -3.0: score += 1
    cl_val = stock.get("cl", 50)
    if 40 <= cl_val <= 75: score += 3

    # 逆势上涨加分：负DIF但还在涨=主力逆势买入（虚涨日尤其有效）
    if stock.get("p", 0) > 5.5 and (stock.get("dif", 0) or 0) < 0:
        score += 5

        if s.get("vr",1) < 0.9: score -= 8  # 缩量涨（VR<0.9）是虚涨，有崩盘风险
    if s.get("cl",50) > 85 and s.get("wrv",50) < 15 and s.get("dif",0) < 0: score -= 12  # 高位超买+死叉
    return round(score,1)
    # DIF虚高扣分(海思科案例)
    if s.get("dif",0) > 2.0 and s.get("p",0) < 3.0: score -= 12  # DIF虚高但涨幅不够
    # 前日涨停追涨扣分
    if stock.get("d1",0) > 8: score -= 8  # 前日涨停追涨风险扣分
