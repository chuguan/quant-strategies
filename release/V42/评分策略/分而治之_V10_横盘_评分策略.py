"""
横盘 V41 — CL≥88用横盘 + CL<88用虚涨日 + 强动量异常修正 + 冲顶惩罚
V40 base + 冲顶惩罚(p>5:-3, pos>70:-8) 横盘78.1%/总76%(100天)
"""
NAME = "横盘策略 V41"
MARKET = "flat"

PARAMS = {
    "use_p": 1, "p_w": 0.5,
    "use_cl": 1, "cl_w": 0.1,
    "use_vr": 1,
    "use_macd": 1, "macd_w": 1, "dif_bonus": 20, "dif_thresh": 1.5,
    "use_a5": 1, "a5_b": 8,
    "use_wr": 0, "wr_lo": 15, "wr_lo_b": 8,
    "use_kdj": 1, "j_golden_b": 8,
    "use_kdj_g": 1, "kdj_g_b": 5,
    "use_pos": 0, "pos_hi_pen": -10,
    "cl_zones": [[50, 80, 5]], "vr_zones": [[0.8, 2.0, 10]],
    "bonus_dif_03": 10, "bonus_dif_05": 8, "bonus_dif_10": 5,
    "bonus_wr_30": 8, "bonus_wr_20": 6, "bonus_wr_10": 4,
    "bonus_cl_75": 6, "bonus_cl_85": 5,
    "bonus_p_20": 5, "bonus_p_30": 3,
    "bonus_hsl_5": 3, "bonus_hsl_8": 3,
    "bonus_pos_60": 3, "bonus_pos_45": 2,
    "bonus_kdj_strong": 4,
    "bonus_flat_combo": 5,
    "bonus_resonance_1": 3, "bonus_resonance_2": 3, "bonus_resonance_3": 3,
}

LEVELS = [
    {"name":"L0","p_min":0,"p_max":7,"vr_min":0.6,"vr_max":2.5,"hs_min":3,"hs_max":20,"sz_max":200,"cl_min":40,"cl_max":95},
    {"name":"L1","p_min":-1,"p_max":7,"vr_min":0.5,"vr_max":3.0,"hs_min":2,"hs_max":25,"sz_max":200,"cl_min":30,"cl_max":95},
    {"name":"L2","p_min":-2,"p_max":7,"vr_min":0.4,"vr_max":3.5,"hs_min":1,"hs_max":30,"sz_max":300,"cl_min":20,"cl_max":98},
    {"name":"L3","p_min":-3,"p_max":7,"vr_min":0.3,"vr_max":4.0,"hs_min":0.5,"hs_max":35,"sz_max":400,"cl_min":10,"cl_max":99},
    {"name":"L4","p_min":-5,"p_max":7,"vr_min":0.2,"vr_max":5.0,"hs_min":0.3,"hs_max":40,"sz_max":500,"cl_min":0,"cl_max":100}
]

BACKTEST = "v41_peak_decay_fix"

def score(stock):
    # ═══ 硬过滤 ═══
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return 0
    
    cl = stock.get('cl', 50)
    sl5 = stock.get('slope5', 0)
    dif = stock.get('dif', 0)
    
    # ═══ CL<88 但强动量 → 走横盘评分 ═══
    # 修正航天电器案例：低CL但有强动量(sl5>10,dif>2)时，虚涨日评分会低估它
    if cl < 88 and sl5 > 10 and dif > 2:
        pass  # 继续往下走横盘评分
    # ═══ CL<88 → 走虚涨日评分 ═══
    elif cl < 88:
        p_ = stock.get('p', 0)
        dif_ = dif
        mg_ = stock.get('mg', 0)
        wrv_ = stock.get('wrv', 50)
        hsl_ = stock.get('hsl', 0)
        a5_ = stock.get('a5', 0)
        
        bs = 0
        bs += p_ * 2.0
        bs += cl * 0.05
        ms = 0
        if mg_ and dif_ > 0.5: ms = 10
        elif mg_ and dif_ > 0.2: ms = 8
        elif mg_: ms = 6
        elif dif_ > 0.5: ms = 4
        elif dif_ > 0: ms = 2
        bs += ms * 0.5
        if dif_ > 0.5: bs += 3
        if a5_ > 0: bs += 0
        if wrv_ < 15: bs += 0
        if wrv_ > 50: bs -= 5
        if hsl_ > 12: bs -= 8
        t4s = stock.get('t4_shadow', 0)
        if sl5 > 5 and t4s > 20: bs -= 5
        # 冲顶惩罚：横盘低位股涨太多或拉到位=明天没空间
        if p_ > 5: bs -= 3
        if stock.get('pos_in_day',50) > 70: bs -= 8
        
        return round(bs, 1)
    
    # ═══ CL≥88 或 低CL但强动量 → 横盘评分 ═══
    p=stock; PARAMS=globals()["PARAMS"]
    bs=0
    if PARAMS.get("use_p",1): bs+=p.get("p",0)*PARAMS.get("p_w",1)
    cl=p.get("cl",50)
    if PARAMS.get("use_cl",1):
        bs+=cl*PARAMS.get("cl_w",0.05)
        for z in PARAMS.get("cl_zones",[]):
            if len(z)==3 and z[0]<=cl<=z[1]: bs+=z[2]
    vr=p.get("vr",1)
    if PARAMS.get("use_vr",1):
        for z in PARAMS.get("vr_zones",[]):
            if len(z)==3 and z[0]<=vr<=z[1]: bs+=z[2]
    dif=p.get("dif",0); mg=p.get("mg",0)
    if PARAMS.get("use_macd",1):
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        bs+=ms*PARAMS.get("macd_w",0.3)
        if dif>PARAMS.get("dif_thresh",0.5): bs+=PARAMS.get("dif_bonus",0)
    if PARAMS.get("use_a5",0) and p.get("a5",0): bs+=PARAMS.get("a5_b",0)
    wrv=p.get("wrv",50)
    if PARAMS.get("use_wr",0):
        if wrv<PARAMS.get("wr_lo",25): bs+=PARAMS.get("wr_lo_b",0)
        if wrv>PARAMS.get("wr_hi",75): bs+=PARAMS.get("wr_hi_b",0)
    jv=p.get("jv",50); kv=p.get("kv",50); dv=p.get("dv",50)
    if PARAMS.get("use_kdj",0):
        if jv>kv>dv: bs+=PARAMS.get("j_golden_b",0)
        if PARAMS.get("j_lo",20)<=jv<=PARAMS.get("j_hi",40): bs+=PARAMS.get("j_zone_b",0)
        if jv<PARAMS.get("j_super_lo",15): bs+=PARAMS.get("j_super_b",0)
    if PARAMS.get("use_kdj_g",0) and p.get("kdj_g",0): bs+=PARAMS.get("kdj_g_b",0)
    pos=p.get("pos_in_day",50)
    if PARAMS.get("use_pos",0):
        if pos>PARAMS.get("pos_hi",85): bs+=PARAMS.get("pos_hi_pen",-2)
        if pos<PARAMS.get("pos_lo",30): bs+=PARAMS.get("pos_lo_b",0)
    
    d=dif; w=wrv; c=cl; pp=p.get("p",0); h=p.get("hsl",0)
    po=pos; kv_=p.get("kv",50); dv_=p.get("dv",50); v=vr; a5=p.get("a5",0)
    
    if d>0.3: bs+=10
    if d>0.5: bs+=8
    if d>1.0: bs+=5
    if w>80: bs+=5
    if c>75: bs+=6
    if c>85: bs+=5
    if pp>2.0: bs+=5
    if pp>3.0: bs+=3
    if h>5: bs+=3
    if h>8: bs+=3
    if po<60: bs+=3
    if po<45: bs+=2
    if kv_>65 and dv_>60: bs+=4
    if pp>2.0 and d>0.3: bs+=5
    if d>0.3 and w>50: bs+=3
    if c>75 and h>5: bs+=3
    if pp>2.0 and v>1.1: bs+=3
    
    t4s=stock.get('t4_shadow',0)
    if sl5 > 5 and t4s > 20: bs -= 5
    # 冲顶惩罚：横盘涨太多或拉到位=明天没空间
    if pp > 5: bs -= 3
    if po > 70: bs -= 8
    
    return round(bs,1)
