"""更新邮件脚本为v10切换策略 + 保存突破版本技能"""
import pickle, json, os
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')
os.chdir(os.path.expanduser('~/AppData/Local/hermes/scripts'))
with open('big_cache_full.pkl','rb') as f:
    cache = pickle.load(f)
data, real, names = cache['data'], cache['real'], cache['names']
dates = sorted(data.keys())

# 查看文件结构
with open('超人策略_每日邮件.py','r') as f:
    content = f.read()
# 检查是否有大盘判断逻辑
has_market = 'mkt' in content or 'avg_p' in content or 'up' in content.lower()
print(f"邮件脚本含大盘切换: {has_market}")
print(f"脚本大小: {len(content)} 字符")
print(f"行数: {content.count(chr(10))}")
