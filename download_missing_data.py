#!/usr/bin/env python3
"""补全2024-2025年K线数据 — 从腾讯API下载"""
import json, os, time, urllib.request, urllib.error

CACHE_DIR = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

def fetch_stock_data(code, start_date="2024-01-01", retries=3):
    """从腾讯API下载股票历史K线"""
    # 前复权数据
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{start_date},,700,qfq"
    
    for attempt in range(retries):
        try:
            req = urllib.request.urlopen(url, timeout=15)
            data = json.loads(req.read().decode('gbk'))
            if data.get("code") != 0 or "data" not in data:
                return None
            
            stock_data = data["data"].get(code, {})
            # 可能有多组数据（日、周、月），取日线
            day_data = stock_data.get("qfqday") or stock_data.get("day") or stock_data.get("qfq")
            if not day_data:
                return None
            
            # 转成标准格式
            records = []
            for item in day_data:
                records.append({
                    "date": item[0],
                    "open": float(item[1]),
                    "close": float(item[2]),
                    "high": float(item[3]),
                    "low": float(item[4]),
                    "volume": float(item[5])
                })
            return records
            
        except urllib.error.HTTPError as e:
            if e.code == 403:
                time.sleep(2)
                continue
            return None
        except:
            time.sleep(1)
            continue
    return None

def merge_records(existing, new_records):
    """合并新旧数据，按日期去重"""
    date_set = set(r["date"] for r in existing)
    merged = list(existing)
    for r in new_records:
        if r["date"] not in date_set:
            merged.append(r)
    merged.sort(key=lambda x: x["date"])
    return merged

# 扫描全部文件
all_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
main_files = [f for f in all_files if f.startswith('sh6') or (f.startswith('sz0') and not f.startswith('sz3')) or f.startswith('sz2')]
print(f"📊 共{len(main_files)}只主板股")

# 先检查哪些缺少2024/2025数据
need_update = []
for fn in main_files:
    fp = os.path.join(CACHE_DIR, fn)
    try:
        with open(fp, 'rb') as f: recs = json.loads(f.read().decode('utf-8'))
        dates = [r["date"] for r in recs]
        has_2024 = any(d.startswith("2024") for d in dates)
        has_full_2025 = sum(1 for d in dates if d.startswith("2025")) >= 200
        if not has_2024 or not has_full_2025:
            need_update.append((fn.replace('.json',''), len(recs), has_2024, has_full_2025))
    except: 
        need_update.append((fn.replace('.json',''), 0, False, False))

print(f"\n{{:<8}} {{:<12}} {{:<10}} {{:<10}}".format("类型", "需更新数", "缺2024", "缺2025"))
missing_2024 = sum(1 for _,_,h2024,_ in need_update if not h2024)
missing_2025 = sum(1 for _,_,_,h2025 in need_update if not h2025)
print(f"{{:<8}} {{:<12}} {{:<10}} {{:<10}}".format("总数", len(need_update), missing_2024, missing_2025))

# 只补2024年数据（2025年93%已有，先补重点）
print(f"\n📥 开始下载2024年数据...")
print(f"   需补2024: {missing_2024}只")

completed = 0
errors = 0
skipped = 0
t0 = time.time()

for code, rec_count, has_2024, has_full_2025 in need_update:
    if has_2024:
        skipped += 1
        continue
    
    fp = os.path.join(CACHE_DIR, f"{code}.json")
    
    # 下载2024年起的数据
    records = fetch_stock_data(code)
    if not records:
        errors += 1
        if errors % 10 == 0:
            print(f"  ❌ {errors}次失败（第{completed}只）")
        continue
    
    # 合并现有数据
    try:
        with open(fp, 'rb') as f: existing = json.loads(f.read().decode('utf-8'))
        merged = merge_records(existing, records)
    except:
        merged = records
    
    # 保存
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(merged, f)
    
    completed += 1
    if completed % 50 == 0:
        elapsed = time.time() - t0
        rate = completed / elapsed
        remaining = (missing_2024 - completed) / rate if rate > 0 else 0
        print(f"  ✅ {completed}/{missing_2024}  ({elapsed:.0f}秒, 预计剩余{remaining:.0f}秒)")
    
    # 限速，避免被Ban
    time.sleep(0.3)

elapsed = time.time() - t0
print(f"\n📊 完成统计:")
print(f"  ✅ 成功更新: {completed}只")
print(f"  ❌ 失败: {errors}只")
print(f"  ⏭ 已跳过(已有2024): {skipped}只")
print(f"  ⏱ 总用时: {elapsed:.0f}秒 ({elapsed/60:.1f}分)")
