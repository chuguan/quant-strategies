"""早盘检查脚本 — 9:40自动运行，生成京东方A操作建议"""
import subprocess, json
from datetime import datetime

def curl(url):
    r = subprocess.run(["curl", "-s", "-m", "10", url], capture_output=True, timeout=15)
    return r.stdout.decode("utf-8", errors="replace")

# 获取京东方A实时行情
r = curl("https://qt.gtimg.cn/q=sz000725")
parts = r.split("~")
if len(parts) > 46:
    name = parts[1]
    price = float(parts[3]) if parts[3] else 0
    prev_close = float(parts[4]) if parts[4] else 0
    open_p = float(parts[5]) if parts[5] else 0
    high = float(parts[33]) if parts[33] else 0
    low = float(parts[34]) if parts[34] else 0
    volume = parts[6] if parts[6] else "0"  # 手
    amount = parts[37] if parts[37] else "0"
    pct = parts[32] if parts[32] else "0"
    turnover = parts[38] if parts[38] else "0"
    pe = parts[39] if parts[39] else "-"
    
    # 分析开盘情况
    if open_p > prev_close * 1.01:
        open_type = "高开"
    elif open_p < prev_close * 0.99:
        open_type = "低开"
    else:
        open_type = "平开"
    
    # 当前涨跌幅
    chg_pct = (price / prev_close - 1) * 100 if prev_close > 0 else 0
    
    # 判断强弱
    if chg_pct > 2: strength = "强势上攻🔥"
    elif chg_pct > 0: strength = "小幅上涨"
    elif chg_pct > -2: strength = "小幅回调"
    else: strength = "弱势下跌⚠️"
    
    # 量比（用成交量估算）
    vol_val = float(volume.replace(",","")) if volume else 0
    
    # 输出JSON给主程序
    result = {
        "股票": name,
        "代码": "000725",
        "时间": datetime.now().strftime("%H:%M"),
        "昨收": prev_close,
        "今开": open_p,
        "开盘类型": open_type,
        "现价": price,
        "涨跌幅": f"{chg_pct:.2f}%",
        "最高": high,
        "最低": low,
        "强弱": strength,
        "市盈率": pe,
    }
    print(json.dumps(result, ensure_ascii=False))
else:
    print(json.dumps({"error": "获取数据失败"}, ensure_ascii=False))
