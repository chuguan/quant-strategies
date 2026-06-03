"""
跌日 V9最优版 — V6原版最优 实测82.8%
"""
NAME = "跌日策略 V9"
MARKET = "down"

PARAMS = {
    'p_w': 1.8,
    'cl_w': 0.2,
    'macd_w': 1.5,
    'dif_bonus': 3,
    'ma5_b': 20,
    'wr_lo': 20,
    'wr_lo_b': -15,
    'wr_hi': 80,
    'wr_hi_b': 5,
    'j_b': 5,
    'j_low_b': 5,
    'p_high_pen': -20,
    'vr_b': 0,
    'hs_bonus': 0,
    'hs_b': 0,
    'vr_bonus': 2,
    'wr_bonus': 0,
    'cl_low_b': 0,
    'p_deep_b': 0,
    'zone_b': 0,
    'cl_high_pen': 0,
    # T-4动量连续性
    'use_momentum_continuity': 1,
    'momentum_accel_bonus': 10,    # 增量持续增大（每天比前一天多涨更多）
    'momentum_decel_penalty': -15, # 增量持续减小（每天比前一天少涨）
    'peak_yesterday_penalty': -10, # 昨天已经到顶（p < d1）
    'v_bounce_penalty': -12,       # V型急弹（前两天大跌后急拉）
}

LEVELS = [
    {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90,"a5_req":1,"kdj_g_req":1},
    {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90,"a5_req":1},
    {"name":"L2","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":3,"hs_max":25,"sz_max":200,"cl_min":30,"cl_max":95},
    {"name":"L3","p_min":0,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":2,"hs_max":30,"sz_max":300,"cl_min":20,"cl_max":98},
    {"name":"L4","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"sz_max":10000,"cl_min":0,"cl_max":100}
]

BACKTEST = "auto-opt_2322_50.0%"

def score(stock):
    # ═══ 硬过滤：ST/退市股/无名股直接返回0 ═══
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm:
        return 0
    # 名字缺失（NO_NAME/代码本身）= 问题股/ST股，也过滤
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()):
        return 0
    
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
    if p.get('use_wr',1):
        if wrv<p.get('wr_lo',25): score+=p.get('wr_lo_b',0)      # 超买惩罚
        if wrv>p.get('wr_hi',75): score+=p.get('wr_hi_b',0)      # 超卖加分
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
    
    # 动力衰竭扣分
    t4s=stock.get('t4_shadow',0)
    if t4s > 50: score -= 15  # T-4超大上影
    
    # T-4 动量连续性检查
    if p.get('use_momentum_continuity', 1):
        d1 = s.get('d1', 0)    # 昨日涨幅
        d2 = s.get('d2', 0)    # 前日涨幅
        d3 = s.get('d3', 0)    # 大前日涨幅
        p_today = s.get('p', 0)
        
        # 增量序列：每天比前一天多涨了多少
        inc1 = d2 - d3   # 第2天相对于第3天的增长
        inc2 = d1 - d2   # 第1天相对于第2天的增长
        inc3 = p_today - d1  # 今天相对于昨天的增长
        
        # 持续加速：每天增量越来越大 (inc1 < inc2 < inc3)
        if inc1 < inc2 < inc3 and d1 > 0 and d2 > 0:
            score += p.get('momentum_accel_bonus', 10)
        # 持续减速：每天增量越来越小 (inc1 > inc2 > inc3)
        elif inc1 > inc2 > inc3 and inc1 > 0:
            score += p.get('momentum_decel_penalty', -15)
        
        # 昨天已经到顶（今天涨幅不如昨天）
        if d1 > 0 and p_today < d1:
            score += p.get('peak_yesterday_penalty', -10)
        
        # V型急弹（前两天大跌，昨日今日急拉）
        if (d3 < -2 or d2 < -2) and d1 > 2.5:
            score += p.get('v_bounce_penalty', -12)
    

    # V14新增：前7天有大阳+洗盘信号
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

    return round(score,1)