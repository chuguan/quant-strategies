#!/usr/bin/env python3
"""
天机早报 — 初稿
功能: 采集美股/A股/新闻/公告 → 生成HTML → 发邮件
定时: 交易日 07:30 (no_agent=True)
"""
import sys, os, json, subprocess, re, time, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'lib'))
from send_email import send_email

NOW = datetime.now()
TODAY = NOW.strftime('%Y-%m-%d')
WD = ['周一','周二','周三','周四','周五','周六','周日'][NOW.weekday()]
ARCHIVE = Path.home() / 'AppData/Local/hermes/prod/data/email_archive'
ARCHIVE.mkdir(parents=True, exist_ok=True)
START_T = time.time()
MAX_TOTAL = 90  # 总时间预算(秒)，留30s给邮件发送

def elapsed():
    return time.time() - START_T

def budget_left():
    return max(0, MAX_TOTAL - elapsed())

def has_budget(need=5):
    """如果剩余时间不够need秒，返回False"""
    ok = budget_left() >= need
    if not ok:
        print(f'  ⏰ 时间预算不足({budget_left():.0f}s < {need}s)，跳过此段')
    return ok

def curl(url, timeout=6, data=None, gbk=False, connect_timeout=4):
    """带连接超时的curl，默认6s超时"""
    if not has_budget(timeout + 2): return '' if not data else '{}'
    cmd = ['curl', '-s', '--max-time', str(timeout), '--connect-timeout', str(connect_timeout)]
    if data:
        cmd += ['-H', 'Content-Type: application/json', '--data-raw', json.dumps(data)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout+4)
        txt = r.stdout.decode('gbk' if gbk else 'utf-8', errors='replace')
        return txt
    except subprocess.TimeoutExpired:
        print(f'  ⚠️ curl超时({timeout}s)')
        return '' if not data else '{}'
    except Exception as e:
        print(f'  ⚠️ curl异常: {e}')
        return '' if not data else '{}'

def curl_json(url, timeout=6, data=None):
    txt = curl(url, timeout, data)
    if not txt: return {}
    start = txt.find('{')
    if start < 0: start = txt.find('[')
    if start < 0: return {}
    try:
        return json.loads(txt[start:])
    except:
        return {}

UP = '#ff4757'
DN = '#7bed9f'
GOLD = '#ffd700'

# ======== 1. 美股 (批量API提速) ========
print(f'[{(elapsed()):.0f}s] 开始采集美股数据...')
import akshare as ak

us_idx, us_stocks, us_sectors = {}, [], {}

# 指数 (3个快速请求)
for sym, name in [('.INX','S&P 500'),('.IXIC','纳斯达克'),('.DJI','道琼斯')]:
    try:
        df = ak.index_us_stock_sina(symbol=sym)
        l2 = df.tail(2)
        c1 = float(l2.iloc[-1]['close'])
        chg = (c1/float(l2.iloc[-2]['close'])-1)*100
        us_idx[name] = (c1, chg)
    except Exception as e:
        print(f'  US index {name} fail: {e}')

# 个股: 用ak.stock_us_spot_em()一次性拿所有美股real-time数据，再切片
try:
    spot = ak.stock_us_spot_em()
    want = {'NVDA','TSLA','BABA','MSFT','AAPL','AMD','META','GOOGL','AVGO','INTC'}
    for _, r in spot.iterrows():
        sym = str(r.get('代码',''))
        if sym in want:
            us_stocks.append((sym, float(r.get('最新价',0)), float(r.get('涨跌幅',0))))
except Exception as e:
    print(f'  US spot batch fail: {e}')
    # 备选: 逐个股获取
    for sym in ['NVDA','TSLA','BABA','MSFT','AAPL','AMD','META','GOOGL','AVGO','INTC']:
        try:
            df = ak.stock_us_daily(symbol=sym, adjust='')
            l2 = df.tail(2)
            c1 = float(l2.iloc[-1]['close'])
            chg = (c1/float(l2.iloc[-2]['close'])-1)*100
            us_stocks.append((sym, c1, chg))
        except: pass

# 板块ETF: 同样用批量API
try:
    etf_spot = ak.stock_us_etf_spot_em() if hasattr(ak, 'stock_us_etf_spot_em') else None
    if etf_spot is not None:
        sec_map = {'XLK':'科技','XLF':'金融','XLE':'能源','XLV':'医疗','XLI':'工业',
                   'XLP':'消费','XLY':'可选消','XLU':'公用','XLB':'材料','SMH':'半导体'}
        for _, r in etf_spot.iterrows():
            sym = str(r.get('代码',''))
            if sym in sec_map:
                us_sectors[sec_map[sym]] = (float(r.get('最新价',0)), float(r.get('涨跌幅',0)))
except:
    pass
# 备选: 逐个ETF获取
if not us_sectors:
    for sym, name in [('XLK','科技'),('XLF','金融'),('XLE','能源'),('XLV','医疗'),('XLI','工业'),
                      ('XLP','消费'),('XLY','可选消'),('XLU','公用'),('XLB','材料'),('SMH','半导体')]:
        try:
            df = ak.stock_us_daily(symbol=sym)
            l2 = df.tail(2)
            c1 = float(l2.iloc[-1]['close'])
            chg = (c1/float(l2.iloc[-2]['close'])-1)*100
            us_sectors[name] = (c1, chg)
        except: pass

print(f'[{(elapsed()):.0f}s] 美股采集完成({len(us_idx)}指数/{len(us_stocks)}个股)')

# ======== 2. A股（用新浪API curl取，比akshare快10倍）=======
a_idx = {}
if has_budget(15):
    # 从本地DB读上证指数（最快）
    try:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'df04_prices.db')
        conn = sqlite3.connect(db_path)
        cur2 = conn.cursor()
        cur2.execute('SELECT date, close FROM index_daily ORDER BY date DESC LIMIT 2')
        rows = cur2.fetchall()
        if len(rows) >= 2:
            c1, c0 = rows[0][1], rows[1][1]
            a_idx['上证指数'] = (c1, (c1/c0-1)*100)
            print(f'  上证指数: {c1:.0f} (DB读)')
        conn.close()
    except Exception as e:
        print(f'  上证DB读失败: {e}')

    # 其他指数用新浪API curl（需要gbk编码）
    idx_api = [('sz399001','深证成指'),('sz399300','沪深300'),
               ('sh000016','上证50'),('sz399006','创业板指')]
    for code, name in idx_api:
        if budget_left() < 3: break
        try:
            txt = curl(f'https://hq.sinajs.cn/list=s_{code}', timeout=4, gbk=True)
            # 新浪API需要Referer头
            if not txt or '=' not in txt:
                cmd = ['curl', '-s', '--max-time', '4', '-H', 'Referer: https://finance.sina.com.cn',
                       f'https://hq.sinajs.cn/list=s_{code}']
                r = subprocess.run(cmd, capture_output=True, timeout=6)
                txt = r.stdout.decode('gbk', errors='replace')
            parts = txt.split('=')[1].strip('";\n\t ').split(',')
            if len(parts) > 4:
                cur_p = float(parts[1])  # 当前价
                chg = float(parts[3])    # 涨跌幅%
                a_idx[name] = (cur_p, chg)
                print(f'  {name}: {cur_p:.0f} ({chg:+.2f}%)')
        except Exception as e:
            rp = txt[:80] if txt else '空'
            print(f'  {name} curl失败: {e} | resp={rp}')

    # 恒生指数
    if budget_left() >= 3:
        try:
            txt = curl('https://hq.sinajs.cn/list=r_HSI', timeout=4)
            if not txt or '=' not in txt:
                cmd = ['curl', '-s', '--max-time', '4', '-H', 'Referer: https://finance.sina.com.cn',
                       'https://hq.sinajs.cn/list=r_HSI']
                r = subprocess.run(cmd, capture_output=True, timeout=6)
                txt = r.stdout.decode('utf-8', errors='replace')
            parts = txt.split('=')[1].strip('";\n\t ').split(',')
            if len(parts) > 3:
                cur_p = float(parts[1])
                chg = float(parts[3])  # 涨跌幅%
                a_idx['恒生指数'] = (cur_p, chg)
                print(f'  恒生指数: {cur_p:.0f} ({chg:+.2f}%)')
        except Exception as e:
            print(f'  恒生指数curl失败: {e}')

    print(f'[{(elapsed()):.0f}s] A股采集完成({len(a_idx)}指数)')
else:
    print(f'  ⏰ A股采集跳过')

# ======== 3. 新闻 (双源容错) ========
policy_news = []
if has_budget(25):
    # 源A: 新闻联播
    for dd in [NOW.strftime('%Y%m%d'), (NOW-timedelta(days=1)).strftime('%Y%m%d'), (NOW-timedelta(days=2)).strftime('%Y%m%d')]:
        try:
            df = ak.news_cctv(date=dd)
            for _, r in df.iterrows():
                t = r.get('title','')
                if any(k in t for k in ['制造','科技','产业','经济','改革','政策','央行','金融','能源','数字',
                                          '船舶','海工','通信','煤炭','新能源','汽车','消费','投资','外贸','外交',
                                          '应急','规划','建设','智能','绿色','高质量','一带一路','自贸']):
                    policy_news.append(t)
            if policy_news:
                print(f'  新闻联播: {len(policy_news)}条(来自{dd})')
                break
        except:
            print(f'  新闻联播 {dd}: 获取失败')
            continue

    if not policy_news:
        try:
            bd = ak.stock_info_global_em()
            if bd is not None and len(bd):
                for _, r in bd.iterrows():
                    t = r.get('title','') or r.get('新闻标题','') or ''
                    if t and len(t) > 6:
                        policy_news.append(t)
            print(f'  财经头条备选: {len(policy_news)}条')
        except:
            pass

    if not policy_news:
        policy_news.append('⚠️ 暂无政策要闻数据')

    hot_news = []
    try:
        df = ak.stock_news_main_cx()
        for _, r in df.head(10).iterrows():
            s = str(r.get('summary',''))
            if s and len(s) > 10:
                hot_news.append(s)
    except:
        pass
    print(f'[{(elapsed()):.0f}s] 新闻采集完成({len(policy_news)}政策/{len(hot_news)}热点)')
else:
    policy_news = ['⚠️ 时间不足跳过新闻采集']
    hot_news = []
    print(f'  ⏰ 新闻采集跳过')

# ======== 4. 事件日历 ========
calendar_lines = []
if has_budget(10):
    try:
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'event_calendar.py')],
                           capture_output=True, timeout=12, text=True)
        if r.stderr:
            print(f'  event_calendar stderr: {r.stderr.strip()[:100]}')
        for l in r.stdout.split('\n'):
            if l.strip() and any(k in l for k in ['📆','🔴','🟡','🟢']):
                calendar_lines.append(l.strip())
    except subprocess.TimeoutExpired:
        print(f'  事件日历: subprocess超时(12s)')
    except Exception as e:
        print(f'  事件日历: {e}')
    print(f'[{(elapsed()):.0f}s] 事件日历完成({len(calendar_lines)}条)')
else:
    print(f'  ⏰ 事件日历跳过')

# ======== 4.5 重大消息（全部显示，不再关键词过滤）========
cls_news_items = []
if has_budget(20):
    try:
        df = ak.stock_info_global_em()
        for _, r in df.iterrows():
            try:
                ts = str(r.get('发布时间', ''))[:16]
                title = str(r.get('标题', ''))
                summary = str(r.get('摘要', ''))[:100]
                # 判断利好/利空倾向（用于标注颜色，不用于过滤）
                full = title + summary
                sentiment = ''
                if any(k in full for k in ['利好','增持','回购','中标','突破','增长','分红','降息',
                    '降准','新高','扭亏','盈喜','投资级','超额认购','SpaceX']):
                    sentiment = '🟢'
                if any(k in full for k in ['利空','减持','立案','亏损','风险','下调','处罚',
                    '监管','预警','冲突','战争','封杀','违约','暴跌','大跌']):
                    sentiment = sentiment or '🔴'
                cls_news_items.append((ts, sentiment, title, summary))
            except:
                pass
        # 按时间倒序
        cls_news_items.sort(key=lambda x: x[0], reverse=True)
        print(f'  重大消息: {len(cls_news_items)}条')
    except Exception as e:
        print(f'  重大消息失败: {e}')
    print(f'[{(elapsed()):.0f}s] 重大消息完成')
else:
    print(f'  ⏰ 重大消息跳过')

# 热门个股新闻（用东财个股新闻查）
hot_stock_news = []
if has_budget(10):
    try:
        # 热门票列表
        hot_codes = ['000901','600118','600879','000657','002378','600072','600685','002648','600549']
        stock_df = ak.stock_info_global_em()
        for _, r in stock_df.iterrows():
            full = str(r.get('标题','')) + str(r.get('摘要',''))
            code_matches = [c for c in hot_codes if c in full]
            name_matches = [n for n in ['航天','太空','卫星','钨','中船','氟','磷','无水','污水'] if n in full]
            if code_matches or name_matches:
                hot_stock_news.append((
                    str(r.get('发布时间',''))[:16],
                    str(r.get('标题',''))[:60]
                ))
        hot_stock_news.sort(key=lambda x: x[0], reverse=True)
        print(f'  热门个股新闻: {len(hot_stock_news)}条')
    except Exception as e:
        print(f'  热门个股新闻: {e}')
    print(f'[{(elapsed()):.0f}s] 热门个股完成')
else:
    print(f'  ⏰ 热门个股跳过')

# ======== 5. 巨潮公告 ========
bull_anns, bear_anns = [], []
BULL_KW = ['增持','回购','中标','合同','分红','新高','增长','突破','放量','受益','利好','订单','扭亏','盈喜']
BEAR_KW = ['减持','立案','亏损','下跌','风险','利空','下调','索赔','处罚','监管','降级','跌超','预警','ST','*ST']

if has_budget(15):
    for codes in ['000001,002594,300750,000858,000333,600519,600036',
                  '601318,600900,601088,601398,600941,600887,002415',
                  '300124,002230,600585,000002,002304,300059']:
        if budget_left() < 4:
            print(f'  ⏰ 巨潮剩余时间不足，跳过后续批次')
            break
        try:
            payload = {"pageNum": 1, "pageSize": 10, "stock": codes,
                       "seDate": [(NOW-timedelta(days=7)).strftime('%Y-%m-%d'), TODAY],
                       "isHLtitle": True, "column": "szse_main", "tab": "fulltext",
                       "plate": "sz", "searchkey": "", "secid": "", "category": "", "trade": ""}
            d = curl_json('https://www.cninfo.com.cn/new/hisAnnouncement/query', data=payload, timeout=8)
            for a in d.get('announcements', []):
                t = a.get('announcementTitle','')
                ts = a.get('announcementTime', 0)
                date = datetime.fromtimestamp(ts/1000).strftime('%m/%d') if isinstance(ts,(int,float)) and ts > 0 else ''
                nm = a.get('secName','')
                bs = sum(1 for kw in BULL_KW if kw in t)
                be = sum(1 for kw in BEAR_KW if kw in t)
                entry = f'[{nm}] {t[:50]}' if nm else t[:50]
                if bs > be and bs >= 1: bull_anns.append(entry)
                elif be > bs and be >= 1: bear_anns.append(entry)
        except Exception as e:
            print(f'  巨潮公告批处理失败: {e}')
    print(f'[{(elapsed()):.0f}s] 巨潮公告完成({len(bull_anns)}利好/{len(bear_anns)}利空)')
else:
    print(f'  ⏰ 巨潮公告跳过')

# ======== 资金流向 ========
moneyflow = {}
north_flow = None
if has_budget(10):
    try:
        txt = curl('https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get?secid=1.000001&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65&lmt=1&klt=101', timeout=6)
        if txt:
            d = json.loads(txt)
            klines = d.get('data',{}).get('klines',[])
            if klines:
                parts = klines[0].split(',')
                moneyflow['上证'] = round(float(parts[1])/1e8, 1)
                print(f'  资金流向: 上证主力净{("流入" if moneyflow["上证"]>0 else "流出")}{abs(moneyflow["上证"]):.1f}亿')
    except Exception as e:
        print(f'  资金流向: 失败({e})')

    try:
        r = subprocess.run(['curl','-s','--max-time','6','https://data.eastmoney.com/hsgt/index.html'],
                         capture_output=True, timeout=8)
        txt = r.stdout.decode('utf-8', errors='replace')
        m = re.search(r'北向资金.*?净流入[：:]\s*([+-]?\d+\.?\d*)', txt)
        if m:
            north_flow = float(m.group(1))
            print(f'  北向资金: 净流入{north_flow:.1f}亿')
        else:
            print(f'  北向资金: 未匹配到数据')
    except Exception as e:
        print(f'  北向资金: {e}')
    print(f'[{(elapsed()):.0f}s] 资金流向完成')
else:
    print(f'  ⏰ 资金流向跳过')

# ======== 6. 构建HTML ========
def pct_html(pct):
    c = UP if pct > 0 else DN
    arrow = '📈' if pct > 0 else '📉'
    return f'<span style="color:{c};font-weight:bold">{arrow} {pct:+.2f}%</span>'

# 美股指数
us_idx_rows = ''
for name, (v, chg) in us_idx.items():
    tag = '大涨' if chg > 2 else '上涨' if chg > 0.5 else '微涨' if chg > 0 else '微跌' if chg > -0.5 else '下跌' if chg > -2 else '大跌'
    us_idx_rows += f'<tr><td>{name}</td><td>{v:.0f}</td><td class="{"bull" if chg>=0 else "bear"}">{pct_html(chg)}</td><td><span class="tag {"tag-g" if chg>=0 else "tag-r"}">{tag}</span></td></tr>\n'

# 美股个股
# 美股个股传导映射
US_CONDUIT = {
    'NVDA': ('半导体/AI芯片', '海光信息/寒武纪'),
    'AMD': ('半导体/AI芯片', '海光信息/中芯国际'),
    'AVGO': ('半导体/AI网络', '中兴通讯/烽火通信'),
    'INTC': ('半导体/CPU', '龙芯中科/海光信息'),
    'TSLA': ('新能源车', '比亚迪/拓普集团'),
    'BABA': ('中概互联', '中概互联ETF'),
    'MSFT': ('AI办公/软件', '金山办公/科大讯飞'),
    'AAPL': ('消费电子', '立讯精密/歌尔股份'),
    'META': ('AI应用/元宇宙', '昆仑万维/恺英网络'),
    'GOOGL': ('AI/云计算', '中科曙光/浪潮信息'),
}

us_stk_rows = ''
for sym, v, chg in us_stocks:
    sec, stk = US_CONDUIT.get(sym, ('其他', ''))
    lvl = '大涨' if chg > 3 else '上涨' if chg > 0.5 else '微跌' if chg > -0.5 else '下跌' if chg > -3 else '大跌'
    arrow = '📈' if chg >= 0 else '📉'
    us_stk_rows += f'<tr><td style="text-align:left;padding-left:8px">{arrow} {sym}</td><td>${v:.1f}</td><td style="color:{UP if chg>=0 else DN};font-weight:bold">{chg:+.2f}%</td><td><span class="tag {"tag-g" if chg>=0 else "tag-r"}">{lvl}</span></td><td style="font-size:10px;text-align:left;padding-left:8px">{sec}</td><td style="font-size:10px;color:#888">{stk}</td></tr>\n'

# 美股板块
sec_rows = ''
sorted_sec = sorted(us_sectors.items(), key=lambda x: -x[1][1])
for i, (name, (v, chg)) in enumerate(sorted_sec):
    medal = ['🥇','🥈','🥉','','','','','','',''][i] if i < 3 else ''
    sec_rows += f'<tr><td>{medal} {name}</td><td style="color:{UP if chg>=0 else DN}">{chg:+.2f}%</td></tr>\n'

# A股
a_rows = ''
for name, (v, chg) in a_idx.items():
    status = '大跌' if chg < -2 else '回调' if chg < -1 else '偏弱' if chg < 0 else '震荡' if chg < 0.5 else '走强' if chg < 1.5 else '大涨'
    a_rows += f'<tr><td>{name}</td><td>{v:.0f}</td><td class="{"bull" if chg>=0 else "bear"}">{chg:+.2f}%</td><td>{status}</td></tr>\n'

# 策略
sh = a_idx.get('上证指数', (0,0))[1]
sz = a_idx.get('深证成指', (0,0))[1]
cy = a_idx.get('创业板指', (0,0))[1]
sp = us_idx.get('S&P 500', (0,0))[1]
nas = us_idx.get('纳斯达克', (0,0))[1]

# 美股影响分析
us_impact = ''
if nas < -2:
    us_impact = f'纳斯达克暴跌{nas:.1f}%，科技股承压，今日A股科技板块可能跟跌'
elif nas > 1:
    us_impact = f'纳斯达克上涨{nas:.1f}%，利好A股科技板块开盘情绪'
elif sp < -1:
    us_impact = f'S&P500下跌{sp:.1f}%，A股大盘可能低开'
else:
    us_impact = '美股窄幅震荡，对A股开盘影响有限'

# 大盘判断
if sp < -2:
    mkt = f'谨慎偏空 — 美跌{sp:.1f}%，A股跟跌概率63.6%'
    pos = '3成以下'
    act = '观望，早盘不抄底'
    liner = '美股暴跌+情绪脆弱=控仓位等尾盘信号'
elif sp < -1 or sh < -1:
    mkt = '偏弱 — 外围+内部承压'
    pos = '3-5成'
    act = '防御为主，精选个股'
    liner = '市场偏弱，防御为主'
elif sp > 1:
    mkt = f'偏多 — 美股涨{sp:.1f}%，利好开盘'
    pos = '5-7成'
    act = '积极操作'
    liner = '内外共振偏多，积极把握'
else:
    mkt = '震荡 — 方向不明等待信号'
    pos = '3-5成'
    act = '等待尾盘信号'
    liner = '震荡整理，尾盘按信号操作'

# 利好方向
up_secs = set()
for sym, v, chg in us_stocks:
    if chg > 1 and sym in US_CONDUIT:
        up_secs.add(US_CONDUIT[sym][0])  # 只取板块名
dn_secs = set()
for sym, v, chg in us_stocks:
    if chg < -1 and sym in US_CONDUIT:
        dn_secs.add(US_CONDUIT[sym][0])  # 只取板块名

# 构建HTML各区块
see_good = '、'.join(sorted(up_secs)[:4]) or '高股息防御'
see_bad = '、'.join(sorted(dn_secs)[:4]) or '暂无'

policy_section = ''.join(f'<div style="font-size:12px;color:#ccc;padding:2px 0">🏛️ {t[:45]}</div>' for t in policy_news[:5]) or '<div style="color:#888;font-size:12px">暂无</div>'
hot_section = ''.join(f'<div style="font-size:12px;color:#ccc;padding:2px 0">{s[:50]}</div>' for s in hot_news[:6]) or '<div style="color:#888;font-size:12px">暂无</div>'

# 公告强度分级
def rate_bull(t):
    strong = sum(1 for k in ['增持','回购','中标','合同','分红','新高','增长','突破','放量','受益','利好','订单','扭亏','盈喜','产能','投产','扩张','合作'] if k in t)
    if strong >= 3: return '⭐⭐⭐'
    if strong >= 2: return '⭐⭐'
    if strong >= 1: return '⭐'
    return '⭐'

def rate_bear(t):
    strong = sum(1 for k in ['减持','立案','亏损','下跌','风险','利空','下调','索赔','处罚','监管','降级','跌超','预警','ST','*ST','退市','违约','爆雷','调查','违规'] if k in t)
    if strong >= 3: return '🔴🔴🔴'
    if strong >= 2: return '🔴🔴'
    if strong >= 1: return '🔴'
    return '🔴'

bull_ann_section = ''
for a in bull_anns[:6]:
    intens = rate_bull(a)
    bull_ann_section += f'<div style="font-size:11px;color:#7bed9f;padding:2px 0">🟢 {a} <span class="tag tag-g">{intens}</span></div>\n'
if not bull_ann_section:
    bull_ann_section = '<div style="color:#888;font-size:11px">暂无近期利好公告</div>'

bear_ann_section = ''
for a in bear_anns[:5]:
    intens = rate_bear(a)
    bear_ann_section += f'<div style="font-size:11px;color:#ff6b6b;padding:2px 0">🔴 {a} <span class="tag tag-r">{intens}</span></div>\n'
if not bear_ann_section:
    bear_ann_section = '<div style="color:#888;font-size:11px">暂无近期利空公告</div>'

cal_section = ''
if calendar_lines:
    cal_section = '<div class="box" style="border-left:3px solid #3498db"><h3 style="color:#3498db">📆 事件前瞻</h3>' + ''.join(f'<div style="font-size:11px;color:#ccc;padding:1px 0">{l}</div>' for l in calendar_lines[:10]) + '</div>'
bull_dir_section = ''.join(f'<div style="font-size:12px;color:#7bed9f;padding:2px 0">🔥 {s} — 美股映射</div>' for s in sorted(up_secs)) or '<div style="color:#888;font-size:12px">暂无</div>'
bear_dir_section = ''.join(f'<div style="font-size:12px;color:#ff6b6b;padding:2px 0">🔴 {s} — 美股下跌传导</div>' for s in sorted(dn_secs)) or '<div style="color:#888;font-size:12px">暂无</div>'

mf_html = ''
if moneyflow:
    mf_val = moneyflow.get('上证', 0)
    mf_color = 'ff4757' if mf_val > 0 else '7bed9f'
    nf_str = f' | 北向: <span style="color:#{"ff4757" if north_flow>0 else "7bed9f"}">{"+" if north_flow>0 else ""}{north_flow:.1f}亿</span>' if north_flow is not None else ''
    mf_html = f'<div class="box"><h3>💰 资金流向</h3><p style="font-size:12px">上证主力净<span style="color:#{mf_color}">{"流入" if mf_val>0 else "流出"}</span>: <span style="color:#{mf_color}">{abs(mf_val):.1f}亿</span>{nf_str}</p></div>'

# 重大消息HTML块
cls_html = ''
if cls_news_items:
    items_html = ''.join(
        f'<div style="font-size:11px;color:#ccc;padding:3px 0">{s} {t[:50]} — {d[:80]}</div>'
        for ts, s, t, d in cls_news_items[:20]
    )
    cls_html = f'<h2>&#x26A1; 昨夜今晨重大消息</h2><div class="box" style="border-left:3px solid #ffd700">{items_html}</div>'

# 热门个股新闻HTML块
hot_html = ''
if hot_stock_news:
    hot_items = ''.join(f'<div style="font-size:11px;color:#ffd700;padding:3px 0">&#x1F525; {ts} {t[:60]}</div>' for ts, t in hot_stock_news[:10])
    hot_html = f'<h2>&#x1F4C8; 热门个股/板块</h2><div class="box" style="border-left:3px solid #ff4757">{hot_items}</div>'

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
body{{font-family:微软雅黑,Helvetica,sans-serif;background:#0d1117;color:#eee;padding:12px;margin:0}}
h1{{font-size:20px;color:#ffd700;text-align:center;text-shadow:0 0 10px rgba(255,215,0,0.3);margin:0 0 6px}}
h2{{font-size:15px;color:#ffd700;border-bottom:1px solid #333;padding-bottom:4px;margin-top:14px;margin-bottom:8px}}
.bull{{color:#ff4757;font-weight:bold}}
.bear{{color:#7bed9f;font-weight:bold}}
.box{{background:#161b22;border-radius:8px;padding:10px;margin:8px 0;border:1px solid #2a2a3e}}
table{{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0}}
th{{background:#0f3460;color:#ffd700;padding:4px 6px;text-align:center;font-size:11px}}
td{{background:#1a1a2e;padding:3px 6px;text-align:center;border-bottom:1px solid #333;font-size:11px}}
.tag{{display:inline-block;padding:1px 5px;border-radius:3px;font-size:10px;margin:1px}}
.tag-r{{background:#4a0e0e;color:#ff6b6b}}
.tag-g{{background:#0e4a0e;color:#6bff6b}}
.footer{{text-align:center;font-size:10px;color:#555;margin-top:14px;padding:6px;border-top:1px solid #2a2a3e}}
</style></head><body>

<h1>""" + f'📰 天机早报 | {TODAY} {WD}' + """</h1>
<p style="text-align:center;font-size:11px;color:#888;margin-bottom:8px">⏱ """ + NOW.strftime('%H:%M') + """ 采集</p>

<h2>🇺🇸 昨夜美股</h2>
<div class="box"><table><tr><th>指数</th><th>收盘</th><th>涨跌</th><th>信号</th></tr>""" + us_idx_rows + """</table></div>
<div class="box"><h3>📊 重点个股与传导</h3><table><tr><th>个股</th><th>收盘</th><th>涨跌</th><th>信号</th><th>传导板块</th><th>A股映射</th></tr>""" + us_stk_rows + """</table></div>
<div class="box"><h3>🏆 板块ETF</h3><table><tr><th>板块</th><th>涨跌幅</th></tr>""" + sec_rows + """</table></div>

<h2>🇨🇳 昨日A股</h2>
<div class="box"><table><tr><th>指数</th><th>收盘</th><th>涨跌</th><th>状态</th></tr>""" + a_rows + """</table></div>
""" + (mf_html if 'mf_html' in dir() else '') + """

<h2>📰 政策 · 新闻</h2>
<div class="box" style="border-left:3px solid #3498db">
<h3 style="color:#3498db">🏛️ 政策要闻</h3>
""" + policy_section + """
<h3 style="color:#3498db;margin-top:10px">💹 财经热点</h3>
""" + hot_section + """
</div>
""" + cal_section + """
""" + cls_html + """
""" + hot_html + """

<h2>✅ 利好方向</h2>
<div class="box" style="border-left:3px solid #27ae60">
""" + bull_dir_section + """
<h3 style="margin-top:10px;color:#7bed9f;font-size:13px">📄 巨潮利好公告</h3>
""" + bull_ann_section + """
</div>

<h2>⚠️ 利空方向</h2>
<div class="box" style="border-left:3px solid #e74c3c">
""" + bear_dir_section + """
<h3 style="margin-top:10px;color:#ff6b6b;font-size:13px">📄 巨潮利空预警</h3>
""" + bear_ann_section + """
</div>

<h2>🛡️ 防御池</h2>
<div class="box"><table><tr><th>个股</th><th>代码</th><th>理由</th><th>股息</th></tr>
<tr><td>长江电力</td><td>600900</td><td>水电龙头</td><td>~3.5%</td></tr>
<tr><td>中国神华</td><td>601088</td><td>煤炭电力央企</td><td>~5%+</td></tr>
<tr><td>工商银行</td><td>601398</td><td>宇宙行</td><td>~6%</td></tr>
<tr><td>中国移动</td><td>600941</td><td>电信龙头</td><td>~4%</td></tr>
<tr><td>贵州茅台</td><td>600519</td><td>A股股王</td><td>递增</td></tr>
<tr><td>伊利股份</td><td>600887</td><td>乳业龙头</td><td>~3.5%</td></tr>
<tr><td>大秦铁路</td><td>601006</td><td>铁路高分红</td><td>~5%</td></tr>
</table></div>

<h2>🎯 今日策略</h2>
<div class="box" style="border:1px solid #ffd700">
<p style="font-size:12px;margin:4px 0"><b style="color:#ffd700">📊 大盘判断：</b><span class="bear">""" + mkt + """</span></p>
<p style="font-size:12px;margin:4px 0"><b style="color:#ffd700">🌙 外围影响：</b><span style="color:#ccc">""" + us_impact + """</span></p>
<p style="font-size:12px;margin:6px 0"><b style="color:#7bed9f">✅ 看好方向：</b>""" + see_good + """</p>
<p style="font-size:12px;margin:6px 0"><b class="bear">⚠️ 需要回避：</b>""" + see_bad + """</p>
<p style="font-size:12px;margin:6px 0"><b style="color:#ffd700">🎯 操作建议：</b>""" + act + """</p>
<p style="font-size:12px;margin:2px 0">&nbsp;&nbsp;建议仓位：""" + pos + """</p>
<p style="font-size:12px;margin:6px 0;color:#ffd700;text-align:center"><b>📌 """ + liner + """</b></p>
</div>

<div class="footer">天机早报 初稿 | 数据: ak/巨潮/东财/腾讯/新浪 | ⚠️ 仅供参考</div>
</body></html>"""

# ======== 输出 ========
arc_path = ARCHIVE / f'morning_brief_{NOW.strftime("%Y%m%d")}.html'
try:
    arc_path.write_text(html, encoding='utf-8')
    print(f'存档: {arc_path}')
except Exception as e:
    print(f'存档失败: {e}')

if budget_left() < 10:
    print(f'⏰ 总时间已消耗{elapsed():.0f}s，跳过邮件发送')
else:
    # 发邮件（全部4人，收件人从config/email_config.yaml统一读取）
    try:
        r = send_email(subject=f'天机早报 {TODAY}', body=html, html=True)
        if r:
            print('邮件已发送 (全部4人)')
        else:
            print('邮件发送返回False')
    except Exception as e:
        print(f'邮件失败: {e}')

dur = time.time() - START_T
print(f'天机早报 完成 ⏱ {dur:.0f}s')
