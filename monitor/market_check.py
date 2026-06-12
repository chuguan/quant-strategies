"""盘中检查脚本 — 从watchlist.json读取当日监控股票池，获取实时数据"""
import subprocess, json, os, sys
from datetime import datetime

def curl(url):
    r = subprocess.run(["curl", "-s", "-m", "10", url], capture_output=True, timeout=15)
    return r.stdout.decode("utf-8", errors="replace")

# 读取当日监控股票池
watchlist_path = os.path.expanduser("~/AppData/Local/hermes/prod/data/watchlist.json")
# 也检查桌面路径
fallback_path = os.path.expanduser("~/Desktop/watchlist.json")

watchlist = None
for p in [watchlist_path, fallback_path]:
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                watchlist = json.load(f)
            break
        except:
            pass

if not watchlist or "stocks" not in watchlist or len(watchlist["stocks"]) == 0:
    # 默认股票池
    watchlist = {
        "stocks": [
            {"code": "000725", "market": "sz", "name": "京东方A", "sector": "面板"},
            {"code": "600584", "market": "sh", "name": "长电科技", "sector": "芯片半导体"},
        ]
    }

stocks = watchlist["stocks"]
results = []
for s in stocks:
    code = s["code"]
    market = s.get("market", "sh")
    name = s["name"]
    sector = s.get("sector", "")
    
    qid = f"{market}{code}"
    r = curl(f"https://qt.gtimg.cn/q={qid}")
    parts = r.split("~")
    if len(parts) > 46:
        try:
            price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else 0
            open_p = float(parts[5]) if parts[5] else 0
            high = float(parts[33]) if parts[33] else 0
            low = float(parts[34]) if parts[34] else 0
            pct = float(parts[32]) if parts[32] else 0
            vol_ratio = float(parts[41]) if parts[41] else 0
            turnover = float(parts[38]) if parts[38] else "0"
            amount = float(parts[37]) if parts[37] else 0
            pe = parts[39] if parts[39] else "-"
            
            if open_p > prev_close * 1.01:
                open_type = "高开"
            elif open_p < prev_close * 0.99:
                open_type = "低开"
            else:
                open_type = "平开"
            
            results.append({
                "code": code, "name": name, "sector": sector,
                "price": price, "prev_close": prev_close,
                "open": open_p, "open_type": open_type,
                "high": high, "low": low,
                "pct": pct, "vol_ratio": vol_ratio,
                "turnover": turnover, "amount": amount,
                "pe": pe,
            })
        except:
            results.append({"code": code, "name": name, "error": "解析失败"})
    else:
        results.append({"code": code, "name": name, "error": "无数据"})

output = {
    "time": datetime.now().strftime("%H:%M"),
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "market_trend": watchlist.get("market_trend", ""),
    "hot_sectors": watchlist.get("hot_sectors", []),
    "stocks": results,
}
print(json.dumps(output, ensure_ascii=False, indent=2))
