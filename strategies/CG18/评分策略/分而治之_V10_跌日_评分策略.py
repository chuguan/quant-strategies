"""
跌日 V42 + 蜡烛图微调(v2:轻量扣分)
"""
NAME = "跌日策略 V42_蜡烛图v2"
MARKET = "down"

LEVELS = [
    {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90,"a5_req":1,"kdj_g_req":1},
    {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90,"a5_req":1},
    {"name":"L2","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":3,"hs_max":25,"sz_max":200,"cl_min":30,"cl_max":95},
    {"name":"L3","p_min":2,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":2,"hs_max":30,"sz_max":300,"cl_min":20,"cl_max":98},
    {"name":"L4","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"sz_max":10000,"cl_min":0,"cl_max":100}
]

BACKTEST = "candle_v2_down"

def score(stock):
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return 0
    if stock.get("hsl", 0) > 18: return 0

    p = stock.get("p", 0); d = stock.get("dif", 0); w = stock.get("wrv", 50)
    c = stock.get("cl", 50); h = stock.get("hsl", 0); dv = stock.get("dv", 50)
    v = stock.get("vr", 0); po = stock.get("pos_in_day", 50); a5 = stock.get("a5", 0)
    mg = stock.get("mg", 0); kg = stock.get("kdj_g", 0)
    t4s = stock.get("t4_shadow", 0); sl5 = stock.get("slope5", 0)
    cu = stock.get("cons_up", 0); bp = stock.get("body_pct", 0) or 0

    # 蜡烛图微调 v2
    candle_adj = 0
    if bp > 6: candle_adj -= 1
    if 0 < bp < 1: candle_adj -= 1
    if cu >= 5: candle_adj -= 2
    if c > 85 and bp < 1: candle_adj -= 3
    if c < 30 and bp > 3: candle_adj += 2

    s = 0
    s += min(p / 4.0, 1) * 60
    s += min(d / 0.8, 1) * 40
    s += max(0, min((50 - w) / 30, 1)) * 25
    s += min(c / 75, 1) * 20
    s += min(h / 8, 1) * 15
    s += min(dv / 65, 1) * 15
    s += min(v / 1.5, 1) * 10
    s += max(0, min((85 - po) / 50, 1)) * 10
    if a5: s += 8
    if d > 0.3 and p > 2.0: s += 8
    if w < 35 and c > 70: s += 5
    if h > 5 and v > 1.1: s += 5
    if mg and kg: s += 3
    if p > 5.5 and d < 0: s += 5
    
    s += candle_adj
    
    if t4s > 50: s -= 20
    if sl5 > 15 and p < 4: s -= 15
    if sl5 > 4 and t4s > 30: s -= 8
    if h > 12 or po > 75: s -= 8
    ms5 = stock.get('ma5_slope', 0) or 0
    if ms5 > 5: s += 10
    if v < 0.9: s -= 8
    if d > 2.0 and p < 3.0: s -= 12
    if stock.get("d1",0) > 8: s -= 8
    if c > 85 and w < 15 and d < 0: s -= 12
    return round(s, 1)
