#!/usr/bin/env python3
"""回查 V13 每日2:50选股记录
用法：
  python 回查_V13选股记录.py              # 列出所有日期
  python 回查_V13选股记录.py 2026-06-01   # 查看指定日期
  python 回查_V13选股记录.py 2026-06-01 2026-06-05  # 查看范围
"""
import os, sys, json, glob
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
LOG_DIR = os.path.join(SCRIPTS_DIR, 'email_archive', '选股记录', 'V13')

def list_all():
    files = sorted(glob.glob(os.path.join(LOG_DIR, 'V13_*.json')))
    if not files:
        print('暂无选股记录')
        return
    
    print(f'📂 V13 每日选股记录（共{len(files)}天）')
    print(f'{"日期":>12} {"时间":>6} {"行情":>6} {"池":>4} {"冠军":>10} {"涨幅":>6} {"评分":>5} {"CL":>4} {"WR":>4}')
    print('-' * 65)
    
    for fp in files:
        with open(fp, 'r', encoding='utf-8') as f:
            r = json.load(f)
        t = r['top10'][0] if r['top10'] else {}
        print(f'{r["date"]:>12} {r["time"][:5]:>6} {r["market_type"]:>6} {r["pool_size"]:>4} '
              f'{t.get("name","?"):>10} {t.get("p",0):>+5.1f}% {t.get("score",0):>5.0f} '
              f'{t.get("cl",0):>4.0f} {t.get("wrv",0):>4.0f}')

def show_date(target):
    fp = os.path.join(LOG_DIR, f'V13_{target}.json')
    if not os.path.exists(fp):
        print(f'❌ 未找到 {target} 的选股记录')
        return
    
    with open(fp, 'r', encoding='utf-8') as f:
        r = json.load(f)
    
    print(f'📊 V13 选股记录 — {r["date"]} {r["time"]}')
    print(f'📈 行情: {r["market_type"]} | 候选池: {r["pool_size"]}只 (等级{r["used_level"]}) | 全市场: {r["total_candidates"]}只')
    print(f'{"#":>2} {"名称":>8} {"代码":>7} {"评分":>5} {"涨幅":>6} {"CL":>4} {"WR":>4} {"量比":>5} {"现价":>7}')
    print('-' * 60)
    for t in r['top10']:
        print(f'{t["rank"]:>2} {t["name"]:>8} {t["code"]:>7} {t["score"]:>5.0f} '
              f'{t["p"]:>+5.1f}% {t["cl"]:>4.0f} {t["wrv"]:>4.0f} {t["vr"]:>5.1f} {t["price"]:>7.2f}')

if __name__ == '__main__':
    if len(sys.argv) == 1:
        list_all()
    elif len(sys.argv) == 2:
        show_date(sys.argv[1])
    else:
        # 范围
        start, end = sys.argv[1], sys.argv[2]
        files = sorted(glob.glob(os.path.join(LOG_DIR, 'V13_*.json')))
        for fp in files:
            fn = os.path.basename(fp)
            d = fn[4:14]  # V13_2026-06-01.json
            if start <= d <= end:
                show_date(d)
                print()
