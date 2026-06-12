"""
真实涨日 V10老司机版 + 蜡烛图微调(v2:轻量扣分)
"""
NAME = "真实涨日策略 V10_蜡烛图v2"
MARKET = "real_up"

PARAMS = {
    "p_w": 7, "dif_w": 5, "wr_w": 3, "cl_w": 3,
    "hsl_w": 2, "d_w": 2, "vr_w": 2, "pos_w": 1, "a5_b": 8,
    "combo_dif_p": 8, "combo_wr_cl": 5, "combo_hsl_vr": 5, "combo_mg_kg": 3,
}

LEVELS = [
    {"name":"L0","p_min":-1,"p_max":7,"vr_min":0.6,"vr_max":2.5,"hs_min":5,"hs_max":15,"sz_max":200,"cl_min":60,"cl_max":90},
    {"name":"L1","p_min":2,"p_max":7,"vr_min":0.6,"vr_max":2.5,"hs_min":3,"hs_max":20,"sz_max":200,"cl_min":50,"cl_max":95},
    {"name":"L2","p_min":1,"p_max":7,"vr_min":0.5,"vr_max":3.0,"hs_min":2,"hs_max":25,"sz_max":300,"cl_min":40,"cl_max":95}
]

BACKTEST = "candle_v2_realup"

def score(stock):
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return 0

    p=stock.get("p",0);d=stock.get("dif",0);w=stock.get("wrv",50)
    c=stock.get("cl",50);h=stock.get("hsl",0);dv=stock.get("dv",50)
    v=stock.get("vr",0);po=stock.get("pos_in_day",50);a5=stock.get("a5",0)
    mg=stock.get("mg",0);kg=stock.get("kdj_g",0)
    t4s=stock.get("t4_shadow",0); sl5=stock.get("slope5",0); cu=stock.get("cons_up",0)
    bp=stock.get("body_pct",0) or 0

    # ═══ 蜡烛图微调 v2（轻量，±1~-3分）═══
    candle_adj = 0
    if bp > 6: candle_adj -= 1           # 实体过大=透支
    if 0 < bp < 1: candle_adj -= 1        # 十字星=犹豫
    if cu >= 5: candle_adj -= 2           # 连涨5天以上=过热
    if c > 85 and bp < 1: candle_adj -= 3 # 高位十字星=黄昏之星
    if c < 30 and bp > 3: candle_adj += 2 # 低位大阳=反转锤子线
    
    s=min(p/5.0,1)*70 + min(d/0.4,1)*45 + max(0,min((50-w)/30,1))*30
    s+=min(c/80,1)*30 + min(h/8,1)*20 + min(dv/65,1)*20
    s+=min(v/1.3,1)*20 + max(0,min((100-po)/50,1))*10
    if a5: s+=8
    if d>0.3 and p>2.0: s+=8
    if w<30 and c>75: s+=5
    if h>5 and v>1.1: s+=5
    if mg and kg: s+=3
    
    s += candle_adj  # 蜡烛图微调
    
    if t4s > 50: s -= 20
    if sl5 > 15 and p < 4: s -= 15
    if sl5 > 4 and t4s > 30: s -= 8
    if v < 0.9: s -= 8
    if d > 2.0 and p < 3.0: s -= 12
    if d > 3.0: s -= 10  # DIF极端值=多方衰竭
    if stock.get("d1",0) > 8: s -= 8
    if c > 85 and w < 15 and d < 0: s -= 12
    return round(s,1)
