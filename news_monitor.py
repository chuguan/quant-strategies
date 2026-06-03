#!/usr/bin/env python3
"""热点新闻监控脚本 — 每2小时检查，只输出重大利好/利空"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))
import akshare as ak
from datetime import datetime

CACHE = os.path.join(os.path.dirname(__file__), 'news_monitor_cache.json')
NOW = datetime.now().strftime('%Y-%m-%d %H:%M')

def load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except: return {'last_titles': [], 'last_time': ''}

def save_cache(titles):
    with open(CACHE, 'w') as f:
        json.dump({'last_titles': titles[:50], 'last_time': NOW}, f)

def get_finance_news():
    """获取东方财富/财新金融新闻"""
    try:
        df = ak.stock_news_main_cx()
        items = []
        for _, r in df.iterrows():
            items.append({'title': r['summary'][:100], 'tag': r['tag'], 'url': r['url']})
        return items
    except: return []

def get_cctv_news():
    """获取新闻联播政策新闻"""
    try:
        today = datetime.now().strftime('%Y%m%d')
        df = ak.news_cctv(date=today)
        items = []
        for _, r in df.iterrows():
            items.append({'title': r['title'], 'content': r['content'][:500]})
        return items
    except: return []

# 主逻辑
cache = load_cache()
old_titles = set(cache['last_titles'])

print(f'📡 热点监控检查: {NOW}')
print(f'   上次检查: {cache.get("last_time", "从未")}')

# 获取新闻
fin_news = get_finance_news()
cctv_news = get_cctv_news()

print(f'   金融新闻: {len(fin_news)}条')
print(f'   新闻联播: {len(cctv_news)}条')

# 找出新新闻
new_items = []
seen_titles = set()

for item in fin_news:
    t = item['title'].strip()
    if not t or t in seen_titles: continue
    seen_titles.add(t)
    if t not in old_titles:
        new_items.append(('金融', item['tag'], t, item['url']))

for item in cctv_news:
    t = item['title'].strip()
    if not t or t in seen_titles: continue
    seen_titles.add(t)
    if t not in old_titles:
        new_items.append(('政策', '新闻联播', t, item['content'][:300]))

if not new_items:
    print('   ⏺ 无新消息')
    save_cache(list(seen_titles))

# 输出新消息（让LLM判断重要性）
for src, tag, title, detail in new_items:
    print(f'---')
    print(f'来源: {src}/{tag}')
    print(f'标题: {title}')
    print(f'详情: {detail}')

print(f'\n---END---')
print(f'新消息总数: {len(new_items)}')
save_cache(list(seen_titles))
