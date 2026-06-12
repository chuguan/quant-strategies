#!/usr/bin/env python3
"""V50+四维v2展示版 — 读取V50选股结果，四维v2模板展示"""
import sys, os, json, time, subprocess, sqlite3, urllib.parse, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

sys.path.insert(0, os.path.expanduser('~/AppData/Local/hermes/prod'))
sys.path.insert(0, os.path.join(os.path.expanduser('~/AppData/Local/hermes/prod'), 'strategies', 'V50'))
SRC = os.path.expanduser('~/AppData/Local/hermes/prod')
TODAY = time.strftime('%Y-%m-%d')
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'
DB = os.path.join(SRC, 'data', 'df04_prices.db')

from V51_日报 import get_live_stocks, classify_market, STRATS, LO
from v51_analysis import get_stock_industry
from risk_tags import get_risk_tags

# ═══ 0. 加载行业映射 ═══
def load_industry_map():
    """加载行业映射（东方财富行业分类）"""
    imap = {}
    try:
        db = os.path.join(SRC, 'v13_quant.db')
        c = sqlite3.connect(db, timeout=5)
        cur = c.cursor()
        cur.execute('SELECT code, industry FROM stock_industry')
        for row in cur.fetchall():
            imap[row[0]] = row[1]
        c.close()
    except: pass
    return imap

industry_map = load_industry_map()
print(f'[0] 行业映射:{len(industry_map)}只')

# ═══ 1. 读取V50 TOP10 ═══
_db = sqlite3.connect(os.path.join(SRC, 'v13_quant.db'), timeout=5)
_cur = _db.execute("SELECT date, market_type, used_level FROM selection_candidates WHERE version='V50' AND date<=? ORDER BY date DESC, run_time DESC LIMIT 1", (TODAY,))
_row = _cur.fetchone()
if not _row:
    print('❌ 没有V50选股记录')
    sys.exit(0)
v50_date, mk_cn, ul = _row
print(f'[V50] 行情: {mk_cn} / {ul}级 ({v50_date})')

# 读最新一次运行的TOP10
_latest = _db.execute("SELECT MAX(run_time) FROM selection_candidates WHERE version='V50' AND date=?", (v50_date,)).fetchone()[0]
_cur = _db.execute("SELECT rank, code, name, price, pct, score, cl, vr, hsl, wr, dif FROM selection_candidates WHERE version='V50' AND date=? AND run_time=? ORDER BY rank LIMIT 10", (v50_date, _latest))
top10_raw = []
for r in _cur.fetchall():
    top10_raw.append({'rank':r[0],'code':r[1],'name':r[2],'price':float(r[3] or 0),'pct':float(r[4] or 0),'score':float(r[5] or 0),'cl':float(r[6] or 50),'vr':float(r[7] or 1),'hsl':float(r[8] or 0),'wr':float(r[9] or 50),'dif':float(r[10] or 0)})
_db.close()
print(f'[1] V50 TOP10: #1={top10_raw[0]["name"]}({top10_raw[0]["code"]})')

# 构造四维需要的stock字典(从实时API取最新价格)
stocks = get_live_stocks()
TOP10_STOCKS = set(s['code'] for s in top10_raw)
stocks = {k:v for k,v in stocks.items() if k in TOP10_STOCKS}
# 补充实时数据中缺失的指标
if any('cl' not in s for s in stocks.values()):
    _db2 = sqlite3.connect(os.path.join(SRC, 'v13_quant.db'), timeout=5)
    _r2 = _db2.execute("SELECT DISTINCT date FROM data_cache WHERE close>0 AND date<=? ORDER BY date DESC LIMIT 1", (TODAY,)).fetchone()
    if _r2:
        for r3 in _db2.execute("SELECT code, cl, wr_val, dif_val FROM data_cache WHERE date=? AND close>0", (_r2[0],)).fetchall():
            if r3[0] in stocks:
                stocks[r3[0]]['cl'] = r3[1]; stocks[r3[0]]['wr_val'] = r3[2]; stocks[r3[0]]['dif_val'] = r3[3]
    _db2.close()

# 用V50 DB的指标补充(确保每个stock都有完整数据)
for s in top10_raw:
    code = s['code']
    if code not in stocks:
        # 构造一个半虚拟股票对象
        stocks[code] = {'name':s['name'],'p':s['price'],'cl':s['cl'],'vol_ratio':s['vr'],'hsl':s['hsl'],'wr_val':s['wr'],'dif_val':s['dif'],'price':s['price']}
        continue
    # 补充V50 DB里的指标到实时数据
    if 'cl' not in stocks[code] or not stocks[code].get('cl'):
        stocks[code]['cl'] = s['cl']
    if 'wr_val' not in stocks[code] or not stocks[code].get('wr_val'):
        stocks[code]['wr_val'] = s['wr']
    if 'dif_val' not in stocks[code] or not stocks[code].get('dif_val'):
        stocks[code]['dif_val'] = s['dif']

# 行情分类
if not mk_cn:
    mk = classify_market(stocks)
    mk_cn = {'real_up':'真实涨日','fake_up':'虚假涨日','down':'跌日','flat':'横盘'}[mk]
mod = STRATS.get(mk_cn, list(STRATS.values())[0])
LEVELS = mod.LEVELS; lm = {l['name']:i for i,l in enumerate(LEVELS)}
inds = {}
for code,s in stocks.items():
    if 'cl'in s and 'wr_val'in s:
        dv=s.get('dif_val',0) or 0
        inds[code]={'dif':dv,'macd_golden':1 if dv>0 else 0,'k_val':50,'d_val':50,'j_val':50,'kdj_golden':1,'wr':s.get('wr_val',50) or 50,'cl':s.get('cl',50) or 50}

# 用V50的评分排序
scored = []
for s in top10_raw:
    code = s['code']
    stk = stocks.get(code, {})
    ind = inds.get(code, {'dif':0,'macd_golden':1,'k_val':50,'d_val':50,'j_val':50,'kdj_golden':1,'wr':50,'cl':50})
    st={'p':stk.get('p',s['price']),'cl':ind['cl'],'vr':stk.get('vol_ratio',s['vr']),'dif':ind['dif'],'mg':ind['macd_golden'],'wrv':ind['wr'],'jv':ind['j_val'],'kv':ind['k_val'],'dv':ind['d_val'],'a5':1,'kdj_g':ind['kdj_golden'],'pos_in_day':50,'nm':s['name'],'hsl':stk.get('hsl',s['hsl']),'ma5_slope':0,'t4_shadow':0,'slope5':0,'cons_up':0,'d1':0,'d2':0,'d3':0,'close':stk.get('close',0) or stk.get('price',0) or s['price']}
    sc = mod.score(st) if hasattr(mod,'score') else s['score']
    scored.append((sc,[],stk,ind,code))
scored.sort(key=lambda x:-x[0])
top10 = scored[:10]

# ═══ 2. 预计算行业热度和参考值 ═══
# 从data_cache计算每个行业的平均涨幅
industry_stocks = defaultdict(list)
for code,s in stocks.items():
    ind = industry_map.get(code, '未知')
    industry_stocks[ind].append(s.get('p', 0))

industry_avg_pct = {}
for ind, pcts in industry_stocks.items():
    industry_avg_pct[ind] = sum(pcts)/len(pcts) if pcts else 0

# 排序行业热度（前十）
sorted_industries = sorted(industry_avg_pct.items(), key=lambda x:-x[1])
hot_industry_names = {ind for ind, pct in sorted_industries[:10]}
print(f'[2a] 行业热度: {len(hot_industry_names)}个热门行业')

# 所有股票的量比均值（参考线）
all_vr = [s.get('vol_ratio',1) for s in stocks.values() if s.get('vol_ratio',1) > 0]
avg_market_vr = sum(all_vr)/len(all_vr) if all_vr else 1.0

# ═══ 新闻获取（东方财富API，3秒超时，失败跳过）═══
POS_KW = ['涨停','大涨','拉升','走强','中标','合同','增持','回购','分红','新高','增长','突破','放量','受益','利好','绩优','盈利','订单','投产','扩张','合作','主力','景气','政策','利润']
NEG_KW = ['跌停','大跌','减持','立案','亏损','下跌','风险','利空','下调','索赔','处罚','监管','降级','跌超','走低','回调','出货','警告','警示']

def fetch_news(name, code, timeout=3):
    """获取新闻+公告，返回{pos:[], neg:[]}，每条含{text,date}，超时返回空"""
    result = {'pos':[], 'neg':[]}
    try:
        # 新闻
        enc = urllib.parse.quote(name)
        url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{enc}%22%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A5%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D'
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url],capture_output=True,timeout=timeout+2)
        text = r.stdout.decode('utf-8','replace').strip().lstrip('\ufeff')
        if text.startswith('jQuery(') and text.endswith(')'):
            text = text[7:-1]
        data = json.loads(text)
        articles = data.get('result',{}).get('cmsArticleWebOld',[])
        for a in articles:
            t = (a.get('title','') + ' ' + a.get('content',''))[:200]
            dt = (a.get('date','') or a.get('showDate','') or '')[:10]
            ps = sum(1 for kw in POS_KW if kw in t)
            ns = sum(1 for kw in NEG_KW if kw in t)
            item = {'text': t[:60], 'date': dt}
            if ps > ns: result['pos'].append(item)
            elif ns > ps: result['neg'].append(item)
    except: pass
    
    # 公告
    try:
        url2 = f'https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=5&page_index=1&ann_type=A&stock_list={code}&f_node=0&s_node=0'
        r2 = subprocess.run(['curl','-s','--max-time',str(timeout),url2],capture_output=True,timeout=timeout+2)
        text2 = r2.stdout.decode('utf-8','replace')
        data2 = json.loads(text2) if text2.strip().startswith('{') else {}
        skip_kw = ['管理办法','制度','议事规则','委员会','任命','聘任','秘书']
        items = data2.get('data',{}).get('list',[])
        for a in items:
            t = a.get('title','')
            if any(k in t for k in skip_kw): continue
            dt = (a.get('notice_date','') or '')[:10]
            ps = sum(1 for kw in POS_KW if kw in t)
            ns = sum(1 for kw in NEG_KW if kw in t)
            item = {'text': f'[公告]{t[:50]}', 'date': dt}
            if ps > ns: result['pos'].append(item)
            elif ns > ps: result['neg'].append(item)
    except: pass
    
    # 按日期排序：最新在前面（无日期的放最后）
    def sort_by_date(items):
        return sorted(items, key=lambda x: x.get('date', '') or '', reverse=True)
    result['pos'] = sort_by_date(result['pos'])
    result['neg'] = sort_by_date(result['neg'])
    
    return result

def check_stock(item):
    sc,ws,s,ind,code = item
    mkt = PREFIX(code)
    result = {'item':item, 'kl':[], 'veto':False, 'reason':'',
              'sector_pct':0, 'sector_hot':False, 'money_flow':0,
              'iq_score':sc, 'iq_ok':sc>=60,
              'chip_ok':True, 'chip_note':'良好'}
    
    # ① 查K线（放量否决+K线摘要）
    url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,20,qfq'
    try:
        r=subprocess.run(['curl','-s','--max-time','5',url],capture_output=True,timeout=8)
        text=r.stdout.decode('utf-8',errors='replace')
        d=json.loads(text) if text.strip().startswith('{') else {}
        kl=d.get('data',{}).get(mkt+code,{}).get('day',[]) or d.get('data',{}).get(mkt+code,{}).get('qfqday',[])
        kdata=[]
        for item in kl[-15:]:  # 保留15日K线
            if len(item)<6: continue
            close=float(item[2]); prev=float(item[1])
            pct=round((close/prev-1)*100,2) if prev else 0
            kdata.append({'date':str(item[0])[:10],'pct':pct,'vol':float(item[5]),'close':close})
        result['kl']=kdata
        if len(kdata)>=3:
            vols=[k['vol'] for k in kdata[:-1]]
            avg5=sum(vols[-5:])/min(len(vols[-5:]),5) if vols else 0
            if avg5>0:
                reasons=[]
                for k in kdata[-3:-1]:
                    if k['pct']<0 and k['vol']/avg5>=1.3:
                        reasons.append(f'{k["date"]}跌{k["pct"]:.1f}%量{k["vol"]/avg5:.1f}x')
                if reasons:
                    result['veto']=True
                    result['reason']=' | '.join(reasons)
    except: pass
    
    # ② 板块热度引擎（基于行业平均涨幅）
    ind_name = industry_map.get(code, s.get('name','')[:4])
    ind_pct = industry_avg_pct.get(ind_name, 0)
    result['sector_pct'] = round(ind_pct, 1)
    result['sector_hot'] = ind_pct >= 1.0  # 行业涨1%+算热
    result['ind_name'] = ind_name  # 存储行业名称
    # 如果没有行业数据，基于个股涨幅判断
    if ind_name == '未知':
        result['sector_hot'] = s.get('p', 0) >= 2.0  # 个股涨幅高=板块可能强
    
    # ③ 资金流入引擎（基于量比+涨幅推断）
    vr = s.get('vol_ratio', 1)
    p = s.get('p', 0)
    # 放量上涨 = 主力流入
    if p > 0 and vr > 1.3:
        # 估算流入金额（成交量×价格×涨幅/量比修正）
        vol = s.get('vol', 0) or s.get('volume', 0)
        price = s.get('price', 0)
        est_inflow = vol * price * (p/100) * (vr/2) / 100000000  # 估算亿
        result['money_flow'] = round(min(est_inflow, 5), 2)  # 封顶5亿防异常
        result['money_ok'] = est_inflow > 0
    elif p > 0:
        result['money_flow'] = round(p * 0.05, 2)  # 小额正向
        result['money_ok'] = True
    else:
        result['money_flow'] = 0
        result['money_ok'] = False
    
    # ④ 筹码结构引擎（基于技术指标）
    wr = ind.get('wr', 50)
    cl = ind.get('cl', 50)
    dif = ind.get('dif', 0)
    
    issues = []
    if wr < 10:
        issues.append('严重超买')
        result['chip_ok'] = False
    elif wr < 20:
        issues.append('偏超买')
    if cl > 90:
        issues.append('高位')
        result['chip_ok'] = False
    elif cl > 80:
        issues.append('偏高')
    if dif < -0.3:
        issues.append('DIF弱势')
        result['chip_ok'] = False
    
    if not issues:
        result['chip_note'] = '良好'
    elif result['chip_ok']:
        result['chip_note'] = ' | '.join(issues) + '(轻微)'
    else:
        result['chip_note'] = ' | '.join(issues)
    
    # ⑤ 成交量分析（K线量价关系判定好坏）
    kdata = result.get('kl', [])
    vr = s.get('vol_ratio', 1)  # 今日量比
    p = s.get('p', 0)  # 今日涨跌
    
    if len(kdata) >= 5:
        avg_vol_recent = sum(k['vol'] for k in kdata[-3:]) / min(3, len(kdata))
        avg_vol_older = sum(k['vol'] for k in kdata[:-3]) / max(len(kdata)-3, 1)
        vol_trend = avg_vol_recent / avg_vol_older if avg_vol_older > 0 else 1
    else:
        vol_trend = 1  # 数据不足按正常处理
    
    # 量比<0.8或近3日<前期的0.8=缩量，量比≥1.3且近3日>前期1.2=放量
    is_shrink = (vr < 0.8) or (vol_trend < 0.8)
    is_expand = (vr >= 1.3) and (vol_trend > 1.2)
    
    if p < 0 and is_expand:
        result['vol_label'] = '放量下跌'
        result['vol_ok'] = False
        result['vol_color'] = '#16a34a'  # 🟢坏
    elif p > 0 and is_expand:
        result['vol_label'] = '放量上涨'
        result['vol_ok'] = False
        result['vol_color'] = '#16a34a'  # 🟢坏（放量=坏）
    elif p > 0 and is_shrink:
        result['vol_label'] = '缩量上涨'
        result['vol_ok'] = True
        result['vol_color'] = '#dc2626'  # 🔴好
    elif p < 0 and is_shrink:
        result['vol_label'] = '缩量回调'
        result['vol_ok'] = True
        result['vol_color'] = '#dc2626'  # 🔴好
    else:
        result['vol_label'] = '量价正常'
        result['vol_ok'] = True
        result['vol_color'] = '#dc2626'  # 🔴中性
    
    result['vol_info'] = f'{p:+.1f}%×{vr:.1f}x'
    
    # ⑥ 新闻检测（3秒超时，失败跳过）
    result['news'] = {'pos':[], 'neg':[]}
    try:
        news = fetch_news(s.get('name',''), code, timeout=3)
        result['news'] = news
    except:
        pass
    
    return result

checks=[None]*10
with ThreadPoolExecutor(max_workers=10) as ex:
    fmap={ex.submit(check_stock,item):i for i,item in enumerate(top10)}
    for f in as_completed(fmap):
        i=fmap[f]
        try: checks[i]=f.result(timeout=12)
        except: checks[i]={'item':top10[i],'kl':[],'veto':False,'reason':'','sector_pct':0,'sector_hot':False,'money_flow':0,'iq_score':0,'iq_ok':False,'chip_ok':True,'chip_note':'数据不足','news':{'pos':[],'neg':[]}}
print('[2b] 数据完成:10/10')

# 主线程算行业排名
for i, r in enumerate(checks):
    ind_name = r.get('ind_name', '未知')
    rank = 999
    for rank_idx, (ind, _) in enumerate(sorted_industries):
        if ind == ind_name:
            rank = rank_idx + 1
            break
    r['ind_rank'] = rank

# ═══ 3. 四维判定 ═══
def dim4_bar(r):
    """四维+放量下跌：全黑文字，额外维度🟢绿"""
    items = []
    
    sp = r['sector_pct']
    sp_str = f'{sp:+.1f}%' if sp != 0 else '独立'
    items.append(f'板块热度  {sp_str}')
    
    mf = r.get('money_flow', 0)
    mf_str = f'{mf:.2f}亿' if mf > 0 else '正常'
    items.append(f'资金流入  {mf_str}')
    
    iq = r['iq_score']
    items.append(f'个股IQ  {iq:.0f}分')
    
    note = r['chip_note'][:12]  # 筹码结构
    items.append(f'筹码结构  {note}')
    
    # ⑤ 成交量分析
    vl = r.get('vol_label', '量价正常')
    vi = r.get('vol_info', '')
    items.append(f'成交量  {vl} {vi}')
    
    ok4 = sum([r['sector_hot'], r.get('money_flow',0)>=0, r.get('iq_ok', True), r['chip_ok']])
    total = f'⭐总评  {ok4}/4'
    line = '\n'.join(items) + '\n' + total
    
    return line, ok4
def get_recommend(r, ok4, is_heji=False, is_jili=False):
    """返回(推荐等级, 标签文本, 文本颜色, 背景色)
    1鹤立鸡群 2极力购买🟢金色 3推荐购买 4观望 5拒绝
    成交量放量 → 最高只能观望
    """
    vol_ok = r.get('vol_ok', True)  # 成交量健康
    vol_good = r.get('vol_label', '') in ('缩量上涨', '缩量回调')  # 缩量=极品
    if r['veto']:
        return 5, '🚫 拒绝购买', '#2e7d32', '#e8f5e9'
    if r.get('news',{}).get('neg',[]):
        return 5, '🚫 拒绝购买', '#2e7d32', '#e8f5e9'
    if is_heji:
        return 1, '🔥🔥🔥 鹤立鸡群 🔥🔥🔥', '#b71c1c', '#ffebee'
    if is_jili and vol_good:
        return 2, '⭐⭐ 极力购买 ⭐⭐', '#c62828', '#fce4ec'
    elif ok4 >= 3 and vol_ok:
        return 3, '✅ 推荐购买', '#c62828', '#fce4ec'
    else:
        return 4, '⚠️ 观望', '#e65100', '#fff3e0'

# ═══ 4. 鹤立鸡群×1 + 极力购买(金色) ═══
# 从非拒绝(无否决+无利空)中选最高的
good = [(i, r) for i,r in enumerate(checks) if get_recommend(r, dim4_bar(r)[1])[0] < 5 and r.get('vol_ok', True)]
good.sort(key=lambda x: -x[1]['item'][0])
heji_idx = good[0][0] if good else 0

# 统计各等级数量
def get_jili_flag(i, r, ok4):
    """极力购买：排名2-3 + ok4>=3 + 无否决利空"""
    if i == heji_idx: return False
    if i > 2: return False  # 只给2、3名
    if r['veto'] or r.get('news',{}).get('neg',[]): return False
    return ok4 >= 3

lvls = []
for i,r in enumerate(checks):
    ok4_val = dim4_bar(r)[1]
    jili = get_jili_flag(i, r, ok4_val)
    lvls.append(get_recommend(r, ok4_val, is_heji=i==heji_idx, is_jili=jili)[0])
heji_cnt = lvls.count(1)
jili_cnt = lvls.count(2)
tj_cnt = lvls.count(3)
wg_cnt = lvls.count(4)
jj_cnt = lvls.count(5)
print(f'📊 推荐分布: 🦩鹤立鸡群{heji_cnt} | ✅极力{jili_cnt} | ✅推荐{tj_cnt} | ⚠️观望{wg_cnt} | 🚫拒绝{jj_cnt}')
MEDALS = {0:'🥇',1:'🥈',2:'🥉'}
PCT_C = lambda p: '🟢' if p<0 else '🔴'
SEP = '━'*36

print(f'\n{SEP}')
print(f'  当天选股 · {TODAY}')
print(f'  {mk_cn} / {ul}级')
# 清理行业名：去掉编号前缀（如 "49建筑" → "建筑"）
def clean_ind_name(name):
    """去掉行业名中的数字编号前缀"""
    m = re.match(r'^[\d\s]+(.+)', name)
    return m.group(1).strip() if m else name.strip()

print(f'  🔥热点板块TOP3:')
for rank_i, (ind, pct) in enumerate(sorted_industries[:3]):
    cn = clean_ind_name(ind)
    pc = PCT_C(pct)
    print(f'    {rank_i+1}. {cn} {pc}{pct:+.1f}%')
print(SEP)

for i,r in enumerate(checks):
    sc,_,s,_,code=r['item']
    dim4_str,ok4=dim4_bar(r)
    jili_flag = get_jili_flag(i, r, ok4)
    level, tag_text, tag_color, tag_bg = get_recommend(r, ok4, is_heji=i==heji_idx, is_jili=jili_flag)
    medal = MEDALS.get(i, f'{i+1}.')

    # 第一行：奖牌+名称
    pct_icon = PCT_C(s['p'])
    print(f'\n{medal} {s["name"]} ({code})')
    print(f'  价格¥{s["price"]:.2f}  {pct_icon}{s["p"]:+.1f}%  评分{sc:.0f}')
    print(f'  {tag_text}')
    
    # 四维：每行独立显示
    print(dim4_str)
    
    # K线
    kline = ' '.join(f'{"📈" if k["pct"]>0 else "📉"}{k["date"][5:]}{k["pct"]:+.1f}%' for k in r['kl'][-2:])
    print(f'  {kline}')
    
    if r['veto']:
        print(f'  ⛔ {r["reason"]}')
    
    # 新闻（有才显示）
    news = r.get('news', {'pos':[],'neg':[]})
    if news['pos']:
        for n in news['pos'][:2]:
            dt = f'[{n["date"]}] ' if n.get('date') else ''
            print(f'  🔴{dt}{n["text"]}')
    if news['neg']:
        for n in news['neg'][:2]:
            dt = f'[{n["date"]}] ' if n.get('date') else ''
            print(f'  🟢{dt}{n["text"]}')

# ═══ 5. 生成邮件HTML（5维+走势用表格）═══
def dim_table_html(r):
    """返回5维两列表格的HTML"""
    sp = r['sector_pct']; sp_color = '#dc2626' if sp>=0 else '#16a34a'
    sp_str = f'{sp:+.1f}%' if sp != 0 else '独立'
    hot_badge = ' 🔥热点板块' if r['sector_hot'] and sp>=0 else ''
    
    mf = r.get('money_flow', 0); mf_color = '#dc2626' if mf>0 else '#16a34a'
    mf_str = f'{mf:.2f}亿' if mf > 0 else '正常'
    mf_label = '放量上涨' if r.get('money_ok') and mf>0 else '正常'
    
    iq = r['iq_score']; iq_color = '#dc2626' if r['iq_ok'] else '#16a34a'
    iq_label = '✅' if r['iq_ok'] else '⚠️'
    
    chip_note = r['chip_note']; chip_ok = r['chip_ok']
    chip_color = '#16a34a' if chip_ok else '#e67e22'
    chip_label = '✅' if chip_ok else '⚠️'
    
    # 成交量分析（从check_stock读取）
    vl = r.get('vol_label', '量价正常')
    vi = r.get('vol_info', '')
    vc = r.get('vol_color', '#555')
    vo = r.get('vol_ok', True)
    vol_label = '✅' if vo else '⚠️'
    
    ok4 = sum([r['sector_hot'], r.get('money_flow',0)>=0, r.get('iq_ok', True), r['chip_ok']])
    total_color = '#dc2626' if ok4>=3 else ('#e67e22' if ok4>=2 else '#16a34a')
    
    # 行业名称+排名
    ind_name = r.get('ind_name', '未知')
    ind_rank = r.get('ind_rank', 999)
    rank_str = f' ⭐排名{ind_rank}' if sp>=0 else ''

    rows = ''
    pairs = [
        ('板块', f'<span style="color:#000;font-weight:bold">{ind_name}</span> (<span style="color:{sp_color}">{sp_str}</span>{rank_str}{hot_badge})'),
        ('资金流入', f'<span style="color:{mf_color}">{mf_str}</span> ({mf_label})'),
        ('个股IQ', f'<span style="color:{iq_color}">{iq:.0f}分</span> {iq_label}'),
        ('筹码结构', f'<span style="color:{chip_color}">{chip_note}</span> {chip_label}'),
        ('成交量', f'<span style="color:{vc}">{vl}</span> {vi} {vol_label}'),
    ]
    for idx, (dim_name, dim_val) in enumerate(pairs):
        bg = '#f9f9f9' if idx%2 else '#fff'
        rows += f'''<tr style="background:{bg}">
    <td style="padding:3px 6px;color:#555;font-size:11px;border-bottom:1px solid #f0f0f0">{dim_name}</td>
    <td style="padding:3px 6px;color:#000;font-size:11px;border-bottom:1px solid #f0f0f0">{dim_val}</td>
  </tr>'''
    rows += f'''<tr style="background:#fff8e1;font-weight:bold">
    <td style="padding:3px 6px;color:#555;font-size:11px">⭐总评</td>
    <td style="padding:3px 6px;color:{total_color};font-size:11px">{ok4}/4 {"✅" if ok4>=3 else "⚠️"}</td>
  </tr>'''
    return f'<table style="width:100%;border-collapse:collapse;margin:3px 0">{rows}</table>'

def kline_table_html(kl):
    """返回K线走势表格（近2日），空数据返回空字符串"""
    kd = kl[-2:] if kl else []
    if not kd:
        return ''
    rows = '<tr style="background:#f0f0f0"><td style="padding:3px 6px;color:#555;font-size:11px;width:35%">📅 走势</td>'
    for k in kd:
        c = '#dc2626' if k['pct']>0 else '#16a34a'
        ik = '📈' if k['pct']>0 else '📉'
        rows += f'<td style="padding:3px 6px;color:{c};font-size:11px">{ik}{k["date"][5:]}{k["pct"]:+.1f}%</td>'
    rows += '</tr>'
    return f'<table style="width:100%;border-collapse:collapse;margin:3px 0">{rows}</table>'

cards_html = ''
for i,r in enumerate(checks):
    sc,_,s,_,code=r['item']
    _,ok4=dim4_bar(r)
    jili_flag = get_jili_flag(i, r, ok4)
    level, tag_text, tag_color, tag_bg = get_recommend(r, ok4, is_heji=i==heji_idx, is_jili=jili_flag)
    medal = {0:'🥇',1:'🥈',2:'🥉'}.get(i, f'{i+1}.')
    pct_c = '#dc2626' if s['p']>=0 else '#16a34a'
    pct_s = f'+{s["p"]:.1f}%' if s['p']>=0 else f'{s["p"]:.1f}%'

    dim_html = dim_table_html(r)
    kline_html = kline_table_html(r['kl'])

    veto_html = ''
    if r['veto']:
        veto_html = f'<div style="margin:4px 0;padding:3px 6px;background:#fef2f2;border-left:3px solid #dc2626;font-size:11px;color:#dc2626">⛔ {r["reason"]}</div>'

    # 新闻HTML
    news = r.get('news', {'pos':[],'neg':[]})
    news_html = ''
    for n in news['pos'][:2]:
        dt = f'[{n["date"]}] ' if n.get('date') else ''
        news_html += f'<div style="font-size:10px;color:#dc2626;margin:1px 0">🔴 {dt}{n["text"]}</div>'
    for n in news['neg'][:2]:
        dt = f'[{n["date"]}] ' if n.get('date') else ''
        news_html += f'<div style="font-size:10px;color:#16a34a;margin:1px 0">🟢 {dt}{n["text"]}</div>'
    if news_html:
        news_html = f'<div style="margin-top:4px;padding:3px 6px;background:#f9f9f9;border-radius:3px">{news_html}</div>'

    cards_html += f'''
<div style="background:{'#fff' if i%2 else '#f8f9fa'};border-radius:6px;padding:8px;margin-bottom:5px;border:1px solid #eee">
  <div style="font-weight:bold;font-size:13px;color:#000">
    <span style="font-size:16px">{medal}</span> {s["name"]}({code})
  </div>
  <div style="font-size:11px;color:#000">
    <span>¥{s["price"]:.2f}</span>
    <span style="color:{pct_c};font-weight:bold;margin:0 4px">{pct_s}</span>
    <span>评分{sc:.0f}</span>
  </div>
  <span style="display:inline-block;margin:4px 0;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:bold;background:{tag_bg};color:{tag_color};border:2px solid {"#d4a017" if level==2 else tag_color+"40"}">{tag_text}</span>
  {dim_html}
  {kline_html}
  {veto_html}
  {news_html}
</div>'''

# 热门板块TOP3信息框
hot_items = []
for rank_i, (ind, pct) in enumerate(sorted_industries[:3]):
    cn = clean_ind_name(ind)
    c = '#dc2626' if pct>=0 else '#16a34a'
    icons = ['🥇', '🥈', '🥉']
    hot_items.append(f'<span style="margin:0 4px">{icons[rank_i]}<b>{cn}</b> <span style="color:{c}">{pct:+.1f}%</span></span>')
hot_box_html = f'<div style="font-size:11px;color:#555;text-align:center;padding:4px 8px;background:#f0f8ff;border-radius:6px;margin-bottom:8px">🔥 热门板块TOP3: {" | ".join(hot_items)}</div>'

# 统计
summary_html = f'<div style="font-size:11px;color:#888;text-align:center;margin:8px 0">🦩鹤立鸡群{heji_cnt} 🟢极力{jili_cnt} ✅推荐{tj_cnt} ⚠️观望{wg_cnt} 🚫拒绝{jj_cnt}</div>'

html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body{{margin:0;padding:10px;font-family:-apple-system,'微软雅黑','PingFang SC',sans-serif;color:#000;font-size:13px}}
.dim{{font-size:12px;color:#000;margin:3px 0}}
.dim-ok{{color:#dc2626}}
.dim-fail{{color:#16a34a}}
</style></head><body>
<div style="font-size:18px;font-weight:bold;color:#d4a017;text-align:center;padding:8px;background:linear-gradient(135deg,#fff8e1,#fce68a);border-radius:8px;margin-bottom:8px">
  当天选股 · {TODAY}
</div>
<div style="font-size:12px;color:#555;text-align:center;margin-bottom:8px">
  {mk_cn} / {ul}级
</div>
{hot_box_html}
{cards_html}
{summary_html}
<div style="text-align:center;font-size:10px;color:#999;margin-top:8px">当天选股 · 自动生成</div>
</body></html>'''

# ═══ 6. 发邮件 ═══
from send_email import send_email
subj = f'V50+四维v2 选股展示 {TODAY} {mk_cn}'
ok = send_email(to=['1254628314@qq.com','314913203@qq.com','2603672569@qq.com','2318162429@qq.com'], subject=subj, body=html, html=True, force=True)
print(f'📧 {"✅发送成功(全4人)" if ok else "❌发送失败"}')
