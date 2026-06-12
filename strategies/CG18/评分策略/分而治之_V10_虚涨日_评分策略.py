"""虚涨日 V18 — 双模式：强用CG04原版，弱用专用评分"""
NAME = "虚涨日策略 V18_DUAL"
MARKET = "fake_up"

# ═══ 强虚涨日参数（CG04原版）══════════════════════
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

LEVELS_WEAK = [
    {"name":"W1","p_min":2,"p_max":6.5,"vr_min":0.5,"vr_max":3.0,"hs_min":3,"hs_max":30,"cl_min":20,"cl_max":95},
    {"name":"W2","p_min":0,"p_max":6.5,"vr_min":0.4,"vr_max":4.0,"hs_min":2,"hs_max":40,"cl_min":10,"cl_max":98},
]

BACKTEST = "v18_dual"

def is_weak_fake_up(stocks):
    """弱虚涨日判断：大盘涨幅≤1%或下跌>1000"""
    ps = [s.get('p',0) or 0 for s in stocks if abs(s.get('p',0) or 0) < 15]
    if not ps: return False
    avg_p = sum(ps)/len(ps)
    down = sum(1 for s in stocks if (s.get('p',0) or 0) < 0)
    return avg_p <= 1.0 or down > 1000

# ═══ A) 强虚涨日评分（CG04原版 + sl5衰减扣分）══════
def score(stock):
    nm = stock.get('nm', '') or stock.get('name', '')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm == 'NO_NAME' or (len(nm) == 6 and nm.isdigit()): return 0
    s=stock; p=PARAMS; sc=0
    if p.get('use_p',1): sc+=s.get('p',0)*p.get('p_w',1)
    cl=s.get('cl',50)
    if p.get('use_cl',1):
        sc+=cl*p.get('cl_w',0.05)
        for z in p.get('cl_zones',[]):
            if len(z)==3 and z[0]<=cl<=z[1]: sc+=z[2]
    vr=s.get('vr',1)
    if p.get('use_vr',1):
        for z in p.get('vr_zones',[]):
            if len(z)==3 and z[0]<=vr<=z[1]: sc+=z[2]
    hsl=s.get('hsl',0) or 0
    if p.get('use_hsl',1) and hsl>p.get('hsl_hi',15): sc+=p.get('hsl_hi_pen',-5)
    dif=s.get('dif',0); mg=s.get('mg',0)
    if p.get('use_macd',1):
        ms=0
        if mg and dif>0.5: ms=10
        elif mg and dif>0.2: ms=8
        elif mg: ms=6
        elif dif>0.5: ms=4
        elif dif>0: ms=2
        sc+=ms*p.get('macd_w',0.3)
        if dif>p.get('dif_thresh',0.5): sc+=p.get('dif_bonus',0)
    if p.get('use_a5',0) and s.get('a5',0): sc+=p.get('a5_b',0)
    wrv=s.get('wrv',50)
    if p.get('use_wr',0):
        if wrv<p.get('wr_lo',25): sc+=p.get('wr_lo_b',0)
        if wrv>p.get('wr_hi',75): sc+=p.get('wr_hi_b',0)
    jv=s.get('jv',50); kv=s.get('kv',50); dv=s.get('dv',50)
    if p.get('use_kdj',0):
        if jv>kv>dv: sc+=p.get('j_golden_b',0)
        if p.get('j_lo',20)<=jv<=p.get('j_hi',40): sc+=p.get('j_zone_b',0)
        if jv<p.get('j_super_lo',15): sc+=p.get('j_super_b',0)
    if p.get('use_kdj_g',0) and s.get('kdj_g',0): sc+=p.get('kdj_g_b',0)
    pos=s.get('pos_in_day',50)
    if p.get('use_pos',0):
        if pos>p.get('pos_hi',85): sc+=p.get('pos_hi_pen',-2)
        if pos<p.get('pos_lo',30): sc+=p.get('pos_lo_b',0)
    d1=stock.get("d1",0); d2=stock.get("d2",0); d3=stock.get("d3",0)
    pt=stock.get("p",0); mx=max(pt,d1,d2,d3)
    mn=min(d1,d2,d3) if min(d1,d2,d3)<0 else 0
    if mx>=9.5: sc+=8
    elif mx>=7.0: sc+=5
    elif mx>=5.0: sc+=3
    if mn<=-7.0: sc+=5
    elif mn<=-5.0: sc+=3
    elif mn<=-3.0: sc+=1
    clv=stock.get("cl",50)
    if 40<=clv<=75: sc+=3
    if stock.get("p",0)>5.5 and (stock.get("dif",0) or 0)<0:
        sc+=5
        if s.get("vr",1)<0.9: sc-=8
    if s.get("cl",50)>85 and s.get("wrv",50)<15 and s.get("dif",0)<0: sc-=12
    sl5=stock.get('slope5',0) or 0
    if sl5>15: sc-=15
    elif sl5>10: sc-=8
    return round(sc,1)

# ═══ B) 弱虚涨日专用评分 ═══════════════════════════
def score_weak(stock):
    nm=stock.get('nm','') or stock.get('name','')
    if 'ST' in nm or '*ST' in nm or '退' in nm: return 0
    if not nm or nm=='NO_NAME' or (len(nm)==6 and nm.isdigit()): return 0
    s=0
    s+=(stock.get('p',0) or 0)*0.3
    cl=stock.get('cl',50); s+=cl*0.03
    if 40<=cl<=80: s+=3
    if cl>85: s-=5
    dif=stock.get('dif',0) or 0; mg=stock.get('mg',0) or 0
    if dif>2: s+=8
    if mg and dif>0.5: s+=12
    elif mg and dif>0: s+=8
    elif mg: s+=4
    elif dif>0.5: s+=3
    elif dif>0: s+=1
    if dif<0 and (stock.get('p',0) or 0)>3: s+=2
    wrv=stock.get('wrv',50)
    if 15<=wrv<=50: s+=4
    if wrv<10: s-=8
    sl5=stock.get('slope5',0) or 0; t4s=stock.get('t4_shadow',0) or 0
    if sl5>10: s-=20
    elif sl5>8: s-=10
    elif sl5>5: s-=4
    if t4s>35: s-=15
    elif t4s>25: s-=5
    hsl=stock.get('hsl',0) or 0
    if hsl>15: s-=5
    if (stock.get('vr',1) or 1)<0.85: s-=8
    if stock.get('a5',0): s+=3
    return round(s,1)
