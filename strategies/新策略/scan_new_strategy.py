"""
新策略 v1 — 定时扫描脚本（实时API版 ⚡）
条件：WR<25下穿 + MACD买点B + KDJ斜率J>K>D + 主力吸筹
数据源：腾讯API实时K线 + 新浪实时行情
"""
import sys, os, json, time, subprocess
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── 路径 ─────────────────────────────────────
SCRIPTS_DIR = os.path.dirname(os.path.dirname(__file__))
CACHE_DIR = os.path.join(SCRIPTS_DIR, "hermes-agent", "cache")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
IS_MAIN = lambda c: c.startswith(("600","601","603","605","000","001","002"))
PREFIX = lambda c: "sh" if c.startswith(("6","9")) else "sz"

def curl_get(url, timeout=10):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except:
        return ""

def fetch_kline(code):
    """从腾讯API获取K线（与qinlong_max一致，1小时缓存自动刷新）"""
    mkt = "sh" if code.startswith(("6","9")) else "sz"
    kf = os.path.join(CACHE_DIR, f"{mkt}{code}.json")
    if os.path.exists(kf) and time.time() - os.path.getmtime(kf) < 3600:
        try:
            return json.load(open(kf))
        except:
            pass
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,300,qfq"
    try:
        text = curl_get(url)
        d = json.loads(text) if text.strip().startswith("{") else {}
        sd = d.get("data",{}).get(f"{mkt}{code}",{})
        k = sd.get("qfqday",[])
        if not k:
            for key in sd:
                if isinstance(sd[key],list) and sd[key] and isinstance(sd[key][0],list):
                    k=sd[key]
                    break
        if len(k) < 80:
            return None
        recs = [{"date":x[0],"open":float(x[1]),"close":float(x[2]),"high":float(x[3]),"low":float(x[4]),"volume":float(x[5])} for x in k]
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(recs, open(kf,"w"))
        return recs
    except:
        return None

# ─── 指标 ─────────────────────────────────────
def calc_all(df):
    for p in [5,10,20,60]:
        df[f"MA{p}"] = df["close"].rolling(window=p).mean()
    ema_f = df["close"].ewm(span=12).mean()
    ema_s = df["close"].ewm(span=26).mean()
    df["DIF"] = ema_f - ema_s
    df["DEA"] = df["DIF"].ewm(span=9).mean()
    df["MACD"] = 2 * (df["DIF"] - df["DEA"])
    low9 = df["low"].rolling(window=9).min()
    high9 = df["high"].rolling(window=9).max()
    rsv = (df["close"] - low9) / (high9 - low9 + 1e-10) * 100
    df["K"] = rsv.ewm(com=2, adjust=False).mean()
    df["D"] = df["K"].ewm(com=2, adjust=False).mean()
    df["J"] = 3 * df["K"] - 2 * df["D"]
    h21 = df["high"].rolling(window=21).max()
    l21 = df["low"].rolling(window=21).min()
    df["WR"] = 100 * (h21 - df["close"]) / (h21 - l21 + 1e-10)
    return df


# ─── 条件判断 ─────────────────────────────────
def check_all(df, idx):
    if idx < 60:
        return False
    if not (df.iloc[idx-1]["WR"] > 25 and df.iloc[idx]["WR"] <= 25):
        return False
    m0,m1,m2 = df.iloc[idx]["MACD"],df.iloc[idx-1]["MACD"],df.iloc[idx-2]["MACD"]
    if not (m0 > m1 and m1 < m2 and m0 > m1 and df.iloc[idx]["K"] > df.iloc[idx-1]["K"]):
        return False
    dj = df.iloc[idx]["J"] - df.iloc[idx-1]["J"]
    dk = df.iloc[idx]["K"] - df.iloc[idx-1]["K"]
    dd = df.iloc[idx]["D"] - df.iloc[idx-1]["D"]
    if not (dj > dk > dd and dj > 0):
        return False
    s,e = max(0,idx-60), idx-20
    if e <= s:
        return False
    acc = df.iloc[s:e]
    if len(acc) < 20:
        return False
    amp = (acc["high"].max()-acc["low"].min())/max(acc["low"].min(),0.01)*100
    if not (amp < 35 and acc.iloc[-1]["MACD"] > 0 and (acc["volume"]>acc["volume"].mean()*1.5).sum() >= 3):
        return False
    ws,we = max(0,idx-15), idx-5
    if we <= ws:
        return False
    wash = df.iloc[ws:we]
    if len(wash) < 5:
        return False
    wd = (wash.iloc[-1]["close"]-wash.iloc[0]["close"])/max(wash.iloc[0]["close"],0.01)*100
    if not (-8 <= wd <= 2 and wash["volume"].mean() < acc["volume"].mean()*0.9 and
            wash.iloc[-1]["MACD"] < wash.iloc[0]["MACD"] and
            wash.iloc[-1]["DIF"] > wash.iloc[-1]["DEA"]):
        return False
    if not (df.iloc[-1]["close"] > wash["low"].min()*1.01 and df.iloc[-1]["MA5"] > df.iloc[-1]["MA10"]):
        return False
    return True


def scan_stock(code, name=""):
    """用实时API K线数据扫描单只股票"""
    recs = fetch_kline(code)
    if not recs or len(recs) < 60:
        return None
    df = pd.DataFrame(recs)
    df["date"] = pd.to_datetime(df["date"])
    df = calc_all(df)
    idx = len(df) - 1
    if not check_all(df, idx):
        return None
    last = df.iloc[-1]
    wr_prev = df.iloc[-2]["WR"]
    dj = df.iloc[-1]["J"] - df.iloc[-2]["J"]
    dk = df.iloc[-1]["K"] - df.iloc[-2]["K"]
    dd = df.iloc[-1]["D"] - df.iloc[-2]["D"]
    p5d = (last["close"]-df.iloc[max(0,idx-5)]["close"])/max(df.iloc[max(0,idx-5)]["close"],0.01)*100
    v5 = df["volume"].rolling(5).mean().iloc[-1]
    return {
        "code": code, "name": name or "",
        "price": round(last["close"], 2),
        "WR_cross": f"{wr_prev:.0f}→{last['WR']:.0f}",
        "WR": round(last["WR"], 1),
        "MACD": round(last["MACD"], 3),
        "K": round(last["K"], 1), "J": round(last["J"], 1),
        "slope": f"+{dj:.1f}>+{dk:.1f}>+{dd:.1f}",
        "R5d": round(p5d, 1),
        "vol_ratio": round(last["volume"]/max(v5,1), 2),
    }


if __name__ == "__main__":
    t0 = time.time()
    today = datetime.now()
    if today.weekday() >= 5:
        print(f"⏰ {today.strftime('%Y-%m-%d %H:%M')} | 非交易日，跳过")
        sys.exit(0)

    # 获取沪深主板股票列表（从新浪实时查询，不用本地缓存）
    print("获取股票列表...", flush=True)
    all_codes = []
    for i in range(600000, 606000): all_codes.append(str(i))
    for i in range(0, 2000): all_codes.append(f"{i:06d}")
    for i in range(2000, 3000): all_codes.append(f"{i:06d}")

    names = {}
    active_codes = []
    for i in range(0, len(all_codes), 80):
        chunk = all_codes[i:i+80]
        symbols = [f"{PREFIX(c)}{c}" for c in chunk]
        try:
            text = curl_get(f"https://qt.gtimg.cn/q={','.join(symbols)}", timeout=8)
            for line in text.split("\n"):
                if "=\"" not in line: continue
                parts = line.split("~")
                if len(parts) < 3: continue
                cid = line.split("_")[-1].split("=")[0]
                nm = parts[1]
                if not nm or "ST" in nm or "*ST" in nm or "退" in nm: continue
                c = cid[2:]
                mkt = "sh" if cid.startswith("sh") else "sz"
                if (mkt == "sh" and c.startswith(("3","68"))) or (mkt == "sz" and c.startswith(("3","68"))): continue
                if not IS_MAIN(c): continue
                active_codes.append(c)
                names[c] = nm
        except:
            pass

    print(f"  主板活跃: {len(active_codes)}只 ({time.time()-t0:.0f}s)", flush=True)

    # 全量扫描（实时K线数据）
    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(scan_stock, c, names.get(c,"")): c for c in active_codes[:1200]}
        for f in as_completed(futs):
            r = f.result()
            if r: results.append(r)

    now = today.strftime("%Y-%m-%d %H:%M")

    if not results:
        print(f"⏰ {now} | 新策略扫描 | 无信号")
        sys.exit(0)

    results.sort(key=lambda x: x["R5d"], reverse=True)
    print(f"\n⏰ {now} | 新策略扫描 | {len(results)}只信号 ({time.time()-t0:.0f}s)")
    print()
    for r in results:
        print(f"🟢 {r['code']} {r['name']} ¥{r['price']}")
        print(f"   WR:{r['WR_cross']}下穿25 | MACD:{r['MACD']:.3f}")
        print(f"   KDJ斜率:{r['slope']} | J值:{r['J']:.0f}")
        print(f"   前5日:{r['R5d']:+.1f}% | 量比:{r['vol_ratio']:.2f}")
        print()

    # ─── 邮件发送 ─────────────────────────────
    EMAIL_TO_LIST = ["1254628314@qq.com", "314913203@qq.com"]
    EMAIL_TITLE = f"新策略扫描结果_{today.strftime('%Y-%m-%d')}"
    lines = [f"⏰ {now} | 新策略扫描 | {len(results)}只信号", ""]
    for r in results:
        lines.append(f"🟢 {r['code']} {r['name']} ¥{r['price']}")
        lines.append(f"   WR:{r['WR_cross']}下穿25 | MACD:{r['MACD']:.3f}")
        lines.append(f"   KDJ斜率:{r['slope']} | J值:{r['J']:.0f}")
        lines.append(f"   前5日:{r['R5d']:+.1f}% | 量比:{r['vol_ratio']:.2f}")
        lines.append("")
    body = "\n".join(lines)
    try:
        from email.mime.text import MIMEText
        from email.header import Header
        import ssl, smtplib
        SENDER = "xiaozhufenfen88@163.com"
        PASSWORD = "YZmfTbTsvXWbSnFy"
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = SENDER
        msg["To"] = ", ".join(EMAIL_TO_LIST)
        msg["Subject"] = Header(EMAIL_TITLE, "utf-8")
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.163.com", 465, timeout=15) as svr:
            svr.login(SENDER, PASSWORD)
            svr.sendmail(SENDER, EMAIL_TO_LIST, msg.as_string())
        print(f"📧 邮件已发送到 {', '.join(EMAIL_TO_LIST)}")
    except Exception as e:
        print(f"⚠️ 邮件发送失败: {e}")
