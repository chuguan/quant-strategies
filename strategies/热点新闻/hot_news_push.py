#!/usr/bin/env python3
"""热点新闻监控 — 东方财富全市场热点抓取 → 邮件通知"""
import sys, os, json, time, subprocess, urllib.request, urllib.parse
sys.path.insert(0, os.path.expanduser('~/AppData/Local/hermes/prod'))
from send_email import send_email
from datetime import datetime

TODAY = time.strftime('%Y-%m-%d')
NOW = datetime.now().strftime('%H:%M')

# 东方财富热点新闻API
def fetch_hot_news(limit=10):
    """抓取东方财富24小时热点新闻"""
    news = []
    try:
        # 用多组关键词搜新闻
        keywords = ['A股','市场','数据要素','涨停','大跌','政策','利好']
        seen = set()
        for kw in keywords:
            try:
                enc = urllib.parse.quote(kw)
                url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{enc}%22%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A8%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D'
                r = subprocess.run(['curl','-s','--max-time','4',url], capture_output=True, timeout=6)
                text = r.stdout.decode('utf-8','replace').strip().lstrip('\ufeff')
                if text.startswith('jQuery(') and text.endswith(')'):
                    text = text[7:-1]
                data = json.loads(text)
                articles = data.get('result',{}).get('cmsArticleWebOld',[])
                for a in articles:
                    t = a.get('title','').strip()
                    if not t or t in seen: continue
                    seen.add(t)
                    dt = (a.get('date','') or a.get('showDate','') or '')[:16]
                    news.append({'title':t[:80], 'date':dt})
            except:
                pass
        
        # 关键词分类
        pos_kw = ['涨停','大涨','拉升','走强','中标','合同','增持','回购','分红','新高','增长','突破','放量','受益','利好','绩优','盈利','订单','投产','扩张','合作','主力','景气','政策','利润']
        neg_kw = ['跌停','大跌','减持','立案','亏损','下跌','风险','利空','下调','索赔','处罚','监管','降级','跌超','走低','回调','出货','警告','警示']
        data_kw = ['数据要素','数据集','数据交易','数据资产','数据安全','数据确权','数据标注','算力','AI','人工智能','大模型']
        
        for a in articles:
            t = a.get('title','')
            c = a.get('content','')[:60]
            dt = (a.get('date','') or a.get('showDate','') or '')[:16]
            combined = t + ' ' + c
            ps = sum(1 for kw in pos_kw if kw in combined)
            ns = sum(1 for kw in neg_kw if kw in combined)
            ds = sum(1 for kw in data_kw if kw in combined)
            tag = '📈' if ps > ns else ('📉' if ns > ps else '📰')
            if ds > 0: tag = '🔴数据要素' if ps > ns else '🟢数据要素'
            news.append({'title':t[:80], 'tag':tag, 'date':dt, 'content':c[:80]})
    except Exception as e:
        print(f'新闻获取失败: {e}')
    
    return news[:limit]

# 股票池相关新闻（取昨天擒龙/三策略的热门票）
def fetch_stock_news(codes_dict, limit=3):
    """查特定股票的最新新闻"""
    results = {}
    for code, name in codes_dict.items():
        try:
            enc = urllib.parse.quote(name)
            url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{enc}%22%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A3%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D'
            r = subprocess.run(['curl','-s','--max-time','3',url], capture_output=True, timeout=5)
            text = r.stdout.decode('utf-8','replace').strip().lstrip('\ufeff')
            if text.startswith('jQuery(') and text.endswith(')'): text = text[7:-1]
            data = json.loads(text)
            articles = data.get('result',{}).get('cmsArticleWebOld',[])
            items = []
            for a in articles[:2]:
                items.append({'title':a.get('title','')[:60],'date':(a.get('date','') or '')[:10]})
            if items: results[name] = items
        except: pass
    return results

# 主流程
print(f'=== 热点新闻推送 === {TODAY} {NOW}')
print()

print('[1] 获取热点新闻...')
hot_news = fetch_hot_news(12)
print(f'  获取到 {len(hot_news)} 条热点')

print('[2] 构建HTML...')
html = f"""<html><head><meta charset="utf-8"><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#fff;color:#333;padding:20px}}
h1{{color:#c0392b;border-bottom:2px solid #c0392b;padding-bottom:10px}}
h2{{color:#e67e22;margin:20px 0 10px;border-left:4px solid #e67e22;padding-left:10px}}
.news-item{{padding:8px 0;border-bottom:1px solid #eee}}
.news-title{{font-size:14px}}
.news-date{{color:#999;font-size:11px}}
.pos{{color:#c0392b}}
.neg{{color:#27ae60}}
.tag{{display:inline-block;padding:1px 5px;border-radius:3px;font-size:11px;margin-right:5px}}
.tag-hot{{background:#c0392b;color:#fff}}
.tag-data{{background:#2980b9;color:#fff}}
.footer{{margin-top:30px;padding-top:15px;border-top:1px solid #ddd;color:#999;font-size:12px}}
</style></head><body>
<h1>🔥 热点新闻推送 · {TODAY}</h1>
<p style="color:#888">更新时间：{NOW}</p>
"""

if hot_news:
    html += "<h2>全市场热点快讯</h2>"
    for n in hot_news:
        html += f'<div class="news-item"><span class="news-title">{n["title"]}</span><br><span class="news-date">{n["date"]}</span></div>'
else:
    html += '<p style="color:#888">暂无热点新闻</p>'

html += '<div class="footer"><p>数据源：东方财富 | 自动推送</p></div></body></html>'

print('[3] 发送邮件...')
subject = f'🔥 热点新闻推送 · {TODAY}'
ok = send_email(to=['1254628314@qq.com'], subject=subject, body=html, html=True, env='production', config='A', force=True)
print(f'{"✅" if ok else "❌"} 发送{"成功" if ok else "失败"}')
