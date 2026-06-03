#!/usr/bin/env python3
"""查看小猪策略5/21冠军在5/22的表现"""
import json, os, sys
sys.path.insert(0, r"C:\Users\12546\AppData\Local\hermes\scripts")
from boduan_qidong_小猪CG06_01020 import load_data, calc_ma, calc_macd, calc_kdj, calc_score

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def pick_on_date(all_data, date):
    """对指定日期选股"""
    candidates = []
    for code, sd in all_data.items():
        di = sd.get("date_idx", {}).get(date)
        if di is None or di < 80: continue
        rec = sd["recs"][di]
        cl = rec["close"]; op = rec["open"]
        hi = rec["high"]; lo = rec["low"]
        m = sd["mas"]
        
        # 底仓硬过滤
        if cl > 80: continue
        if not (m[5][di] and m[10][di] and m[20][di] and m[60][di]): continue
        if not (m[5][di] > m[10][di] > m[20][di] > m[60][di]): continue
        dif = sd["dif"][di]; dea = sd["dea"][di]
        if not (dif and dea and dif > 0 and dif > dea): continue
        atr_val = sd["atr"][di]
        if not (atr_val and cl > 0 and atr_val/cl*100 > 3): continue
        if not (m[60][di] and cl > m[60][di]): continue
        if not (cl > op): continue  # 阳线
        if not (m[5][di] and cl > m[5][di]): continue  # 站上MA5
        
        pct = sd["pct"][di]
        v5 = m["v5"][di] if m["v5"][di] else 0
        pos20 = sd["pos20"][di]
        j_val = sd["j"][di]
        sc = calc_score(cl, pct, rec["volume"], v5, pos20, j_val, hi, op)
        candidates.append((code, sc, rec))
    
    if not candidates: return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates

print("🐷 查看5/21冠军在5/22表现")
print("=" * 50)

all_data, n = load_data()
print(f"✅ {n}只股票")

# 21号选股
cand_21 = pick_on_date(all_data, "2026-05-21")
if cand_21:
    champ = cand_21[0]
    code, score, rec = champ
    close_21 = rec["close"]
    print(f"\n📅 5/21 冠军: {code} (评分:{score})")
    print(f"  买入价(收盘): {close_21}元")
    print(f"  5/21 当日: 开{rec['open']} 高{rec['high']} 低{rec['low']} 收{rec['close']}")
    
    # 找5/22数据
    sd = all_data.get(code)
    if sd:
        di = sd.get("date_idx", {}).get("2026-05-22")
        if di is not None:
            r5_22 = sd["recs"][di]
            open_22 = r5_22["open"]
            high_22 = r5_22["high"]
            low_22 = r5_22["low"]
            close_22 = r5_22["close"]
            
            print(f"\n📅 5/22(次日)表现:")
            print(f"  开盘: {open_22}元 ({open_22/close_21*100-100:+.2f}%)")
            print(f"  最高: {high_22}元 ({high_22/close_21*100-100:+.2f}%)")
            print(f"  最低: {low_22}元 ({low_22/close_21*100-100:+.2f}%)")
            print(f"  收盘: {close_22}元 ({close_22/close_21*100-100:+.2f}%)")
            print(f"\n  📉 回撤: {low_22/close_21*100-100:+.2f}% (从买入到最低)")
            print(f"  📈 最高冲到: +{high_22/close_21*100-100:+.2f}%")
            print(f"  收盘盈亏: {close_22/close_21*100-100:+.2f}%")
        else:
            print(f"\n  5/22 数据未找到")
    
    # 再显示前10名
    print(f"\n📋 5/21 前10名:")
    for i, (cd, sc, r) in enumerate(cand_21[:10], 1):
        print(f"  {i:>2}. {cd} 评分:{sc}")
else:
    print("5/21 无输出")

# 22号选股
print(f"\n{'-'*50}")
cand_22 = pick_on_date(all_data, "2026-05-22")
if cand_22:
    champ = cand_22[0]
    code, score, rec = champ
    close_22 = rec["close"]
    print(f"📅 5/22 冠军: {code} (评分:{score})")
    print(f"  买入价(收盘): {close_22}元")
    print(f"  5/22 当日: 开{rec['open']} 高{rec['high']} 低{rec['low']}")
    print(f"  ⏳ 5/25(下周一)数据待更新...")
