"""
大道至简策略 v2.0 — 4子策略索引
每个子策略独立文件，独立选股条件+评分公式
"""
import os

STRATEGIES = [
    {"name": "真实涨日", "file": "大道至简_子策略01_真实涨日.py", "market": "real_up",
     "days": 111, "champ": 64.9, "top3": 88.3},
    {"name": "虚涨日",   "file": "大道至简_子策略02_虚涨日.py",   "market": "fake_up",
     "days": 17,  "champ": 88.2, "top3": 100.0},
    {"name": "跌日",     "file": "大道至简_子策略03_跌日.py",    "market": "down",
     "days": 80,  "champ": 58.8, "top3": 97.5},
    {"name": "横盘",     "file": "大道至简_子策略04_横盘.py",    "market": "flat",
     "days": 124, "champ": 64.5, "top3": 90.3},
]

def print_summary():
    print(f"\n{'='*55}")
    print(f"  大道至简 v2.0 — 4子策略总览")
    print(f"{'='*55}")
    print(f"  {'策略':<10} {'文件':<26} {'天数':>5} {'冠军':>6} {'Top3':>6}")
    print(f"  {'-'*10} {'-'*26} {'-'*5} {'-'*6} {'-'*6}")
    for s in STRATEGIES:
        print(f"  {s['name']:<10} {s['file']:<26} {s['days']:>5} {s['champ']:>5.1f}% {s['top3']:>5.1f}%")
    print(f"\n  总: 332天  冠军64.5%  Top391.9%")
    print(f"  分级放宽: 95.8%在L0  |  最高p_max=7(涨<8%)")
    print(f"  每日候选池≥10只  ✅  0天缺池")
    print(f"{'='*55}")

if __name__ == '__main__':
    print_summary()
