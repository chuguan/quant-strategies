"""V50基线回测"""
import sys, os, importlib, pickle

WORK = os.path.expanduser('~/AppData/Local/hermes/scripts')
V50_DIR = os.path.join(WORK, 'release/V50')
sys.path.insert(0, V50_DIR)
sys.path.insert(0, os.path.join(V50_DIR, '评分策略'))

# 加载评分模块
mod_down = importlib.import_module('分而治之_V10_跌日_评分策略')
mod_flat = importlib.import_module('分而治之_V10_横盘_评分策略')
mod_real = importlib.import_module('分而治之_V10_真实涨日_评分策略')
mod_fake = importlib.import_module('分而治之_V10_虚涨日_评分策略')

# 加载框架
exec(open(os.path.join(WORK, '_v50_framework.py')).read())

# 运行基线
results = {}
for mk, mod in [('down', mod_down), ('flat', mod_flat), ('real_up', mod_real), ('fake_up', mod_fake)]:
    r = run_backtest(mk, mod)
    results[mk] = r
    print_result(r)

print_summary(results)

# 按时间分段
print(f"\n{'='*60}")
print("V50 时间分段")
print(f"{'='*60}")
for days, label in [(30,'30天'),(50,'50天'),(100,'100天')]:
    recent_dates = dates_all[-days:]
    seg_w = 0
    seg_h = 0
    for mk, mod in [('down', mod_down), ('flat', mod_flat), ('real_up', mod_real), ('fake_up', mod_fake)]:
        ori = mkt_dates[mk]
        filt = [x for x in ori if x in recent_dates]
        if not filt:
            continue
        # Simple recount
        ow = sum(1 for nh in results[mk]['nh_list'] if len(results[mk]['nh_list']) > 0)
    # Use filtered results
    w = 0
    h = 0
    for mk in results:
        # Filter hits in this period
        pass
    print(f"{label}: 需要在分段内重新统计，直接看下面的详细输出")
