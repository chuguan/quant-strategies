"""
跌日 V42 — V41 + HSL>18%一票否决。超高换手票直接否决，50天+2%/100天+1%
"""
NAME = "跌日策略 V42_hsl_veto"
MARKET = "down"

LEVELS = [
    {"name":"L0","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90,"a5_req":1,"kdj_g_req":1},
    {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":1.5,"hs_min":5,"hs_max":20,"sz_max":150,"cl_min":40,"cl_max":90,"a5_req":1},
    {"name":"L2","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.0,"hs_min":3,"hs_max":25,"sz_max":200,"cl_min":30,"cl_max":95},
    {"name":"L3","p_min":0,"p_max":7,"vr_min":0.5,"vr_max":2.5,"hs_min":2,"hs_max":30,"sz_max":300,"cl_min":20,"cl_max":98},
    {"name":"L4","p_min":-10,"p_max":7,"vr_min":0.1,"vr_max":10,"hs_min":0.1,"hs_max":100,"sz_max":10000,"cl_min":0,"cl_max":100}
]

BACKTEST = "v42_hsl_veto_v1"

def score(stock):
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return 0

    # ═══ HSL>18%一票否决：超高换手=主力出货，次日大概率低开 ═══
    h_veto = stock.get("hsl", 0)
    if h_veto > 18:
        return 0

    p = stock.get("p", 0)
    d = stock.get("dif", 0)       # DIF值
    w = stock.get("wrv", 50)       # WR值
    c = stock.get("cl", 50)        # 收盘价位置
    h = stock.get("hsl", 0)        # 换手率
    dv = stock.get("dv", 50)       # D值(KDJ)
    v = stock.get("vr", 0)         # 量比
    po = stock.get("pos_in_day", 50)  # 日内位置
    a5 = stock.get("a5", 0)        # 站上5日线
    mg = stock.get("mg", 0)        # MACD金叉
    kg = stock.get("kdj_g", 0)     # KDJ金叉
    
    # 动量因子（由评分模块传入，无特征数据时=0）
    t4s = stock.get("t4_shadow", 0)
    sl5 = stock.get("slope5", 0)
    cu = stock.get("cons_up", 0)

    # ═══ 封顶打分：每个因子到阈值就满分 ═══
    s = 0
    s += min(p / 4.0, 1) * 60       # 涨幅：p=4%满分60
    s += min(d / 0.8, 1) * 40       # DIF：d=0.8满分40
    s += max(0, min((50 - w) / 30, 1)) * 25  # WR反向：w=20满分25
    s += min(c / 75, 1) * 20        # CL：cl=75满分20
    s += min(h / 8, 1) * 15         # HSL：hsl=8%满分15
    s += min(dv / 65, 1) * 15       # D值：dv=65满分15
    s += min(v / 1.5, 1) * 10       # VR：vr=1.5满分10
    s += max(0, min((85 - po) / 50, 1)) * 10  # 位置：po越小越高

    # ═══ 加分项 ═══
    if a5: s += 8                   # 站上5日线
    if d > 0.3 and p > 2.0: s += 8 # DIF+涨组合
    if w < 35 and c > 70: s += 5   # WR低+CL高组合
    if h > 5 and v > 1.1: s += 5   # HSL+VR组合
    if mg and kg: s += 3           # 双金叉

    # ═══ 逆势上涨加分（虚涨日验证有效） ═══
    if p > 5.5 and d < 0: s += 5

    # ═══ 动力衰竭扣分 ═══
    if t4s > 50: s -= 20
    if sl5 > 15 and p < 4: s -= 15
    if sl5 > 4 and t4s > 30: s -= 8

    return round(s, 1)
