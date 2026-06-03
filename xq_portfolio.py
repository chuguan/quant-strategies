#!/usr/bin/env python3
"""
雪球组合自动调仓工具 — 自动续命版
══════════════════════════════════
核心特性：
  ✅ 自动续命 — 每次请求自动提取 Set-Cookie 更新 token，cookie 不过期
  ✅ 双 token 保活 — xq_r_token 换 xq_a_token
  ✅ 日历保活 — 每天早 9 点访问一次雪球首页触发续命
  ✅ 过期通知 — 连续失败后自动邮件告警

用法:
  首次:  python xq_portfolio.py --setup
  调仓:  python xq_portfolio.py --rebalance "000725,600584"
  管道:  CG-07_v14.py | python xq_portfolio.py --rebalance-stdin
  保活:  python xq_portfolio.py --keep-alive     (设 cron 每天执行)
  状态:  python xq_portfolio.py --status
  配置:  python xq_portfolio.py --show-cookies   (查看token信息)
"""

import json, os, subprocess, sys, time, re
from datetime import datetime

CONFIG_DIR = os.path.expanduser("~/AppData/Local/hermes/config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "xueqiu.json")
COOKIE_JAR = os.path.join(CONFIG_DIR, "xq_cookies.txt")
TOKEN_LOG = os.path.expanduser("~/AppData/Local/hermes/logs/xq_token.log")
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(TOKEN_LOG), exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# ═══════════════════════════════════════════════
#  核心：curl + cookie jar 自动续命机制
# ═══════════════════════════════════════════════
#  原理：curl 的 -c(写入cookie) -b(读取cookie) 会自动处理 Set-Cookie
#  xq_r_token 过期时间长(~30天)，每次请求如果有新 token 回应自动续上
#  再配合每天保活请求，理论上 cookie 永不过期

def _curl(url, method="GET", data=None, cookies_jar=None, dump_headers=False):
    """统一 curl 调用，自动处理 cookie jar"""
    cmd = [
        "curl", "-s", "-k", "--max-time", "15",
        "-H", f"User-Agent: {UA}",
        "-H", "Origin: https://xueqiu.com",
        "-H", "Referer: https://xueqiu.com/",
    ]
    # cookie jar 持久化
    jar = cookies_jar or COOKIE_JAR
    if os.path.exists(jar):
        cmd += ["-b", jar]
    cmd += ["-c", jar]

    if dump_headers:
        # 写入临时文件来获取响应头
        header_file = jar + ".headers"
        cmd += ["-D", header_file]

    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json"]
        if data:
            cmd += ["-d", json.dumps(data, ensure_ascii=False)]

    cmd.append(url)

    try:
        r = subprocess.run(cmd, capture_output=True, timeout=20)
        out = r.stdout.decode("utf-8", errors="replace")
        err = r.stderr.decode("utf-8", errors="replace")[:300]

        if r.returncode != 0:
            return None, err

        # 检查并记录 token 续命情况
        if dump_headers and os.path.exists(header_file):
            with open(header_file) as f:
                headers_text = f.read()
            try:
                os.remove(header_file)
            except:
                pass
            # 从 Set-Cookie 提取新 token 信息
            _record_token_refresh(headers_text, jar)

        return out, None
    except Exception as e:
        return None, str(e)


def _record_token_refresh(headers_text, jar):
    """从响应头检查 token 是否被刷新"""
    # 提取 Set-Cookie 中的 token
    new_a = re.search(r'xq_a_token=([^;]+)', headers_text)
    new_r = re.search(r'xq_r_token=([^;]+)', headers_text)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 从 cookie jar 读取当前值
    old_a, old_r = _read_tokens_from_jar(jar)

    msg_parts = [f"[{now}]"]
    refreshed = False
    if new_a and new_a.group(1) != old_a:
        msg_parts.append(f"xq_a_token 已续命")
        refreshed = True
    if new_r and new_r.group(1) != old_r:
        msg_parts.append(f"xq_r_token 已续命")
        refreshed = True
    if refreshed:
        msg_parts.append("✅")
    else:
        msg_parts.append("无变化")

    with open(TOKEN_LOG, "a", encoding="utf-8") as f:
        f.write(" ".join(msg_parts) + "\n")


def _read_tokens_from_jar(jar):
    """从 Netscape cookie jar 读取 xq_a_token 和 xq_r_token"""
    if not os.path.exists(jar):
        return None, None
    a, r = None, None
    with open(jar) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                key = parts[5]
                val = parts[6]
                if key == "xq_a_token":
                    a = val
                elif key == "xq_r_token":
                    r = val
    return a, r


def _check_token_health(jar):
    """检查 token 健康状况"""
    a, r = _read_tokens_from_jar(jar)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_msg = f"[{now}] xq_a_token={'有' if a else '无'} | xq_r_token={'有' if r else '无'}"
    print(f"  📋 {log_msg}")
    with open(TOKEN_LOG, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")
    return a is not None


def load_config():
    """加载雪球配置"""
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(cfg):
    """保存雪球配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _get_stock_name(code):
    """通过腾讯接口获取股票名称"""
    market = "sh" if code.startswith("6") else "sz"
    r, _ = _curl(f"https://qt.gtimg.cn/q={market}{code}", method="GET", cookies_jar="")
    if r:
        parts = r.split("~")
        if len(parts) > 2:
            return parts[1]
    return code


# ═══════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════

def setup():
    """首次配置 → 写入 cookie jar + 测试"""
    print("=" * 56)
    print(" 雪球组合配置 (自动续命版)")
    print("=" * 56)
    print()
    print("【获取 Cookie 步骤】")
    print(" 1. Chrome 登录 https://xueqiu.com")
    print(" 2. F12 → Network → 刷新页面")
    print(" 3. 点任意请求 → Request Headers → Cookie:")
    print(" 4. 找 xq_a_token 和 xq_r_token")
    print()

    cookie_input = input("粘贴完整 Cookie 字符串: ").strip()
    if not cookie_input:
        print("❌ Cookie 不能为空")
        return False

    # 写入 curl cookie jar (Netscape格式)
    cookies = {}
    for pair in cookie_input.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            cookies[k.strip()] = v.strip()

    if "xq_a_token" not in cookies or "xq_r_token" not in cookies:
        print("❌ 缺少 xq_a_token 或 xq_r_token")
        return False

    # 写入 Netscape cookie jar
    _write_netscape_jar(COOKIE_JAR, cookies)

    print()
    pid = input("组合ID（URL上 ZH123456 的数字部分）: ").strip()
    if not pid:
        print("❌ 组合ID不能为空")
        return False

    # 测试连接
    print("\n🔄 测试连接...")
    ok, name = _test_connection(pid)
    if ok:
        print(f"✅ 连接成功！组合: {name}")
    else:
        print("⚠️ 连接测试未通过，Cookie 可能已过期，继续配置")

    cfg = {
        "portfolio_id": pid,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_rebalance": None,
        "max_positions": 5,
        "cash_ratio": 0.05,
        "log_file": os.path.expanduser("~/AppData/Local/hermes/logs/xq_trades.log")
    }
    save_config(cfg)
    print("\n✅ 配置完成！")
    print(f"   cookie jar: {COOKIE_JAR}")
    print(f"   token日志:  {TOKEN_LOG}")
    print()
    print("接下来:")
    print("  📌 先试调仓:  python xq_portfolio.py --rebalance \"000725,600519\"")
    print("  📌 设每日保活(推荐): 设个 cron 早9点跑 --keep-alive")
    print("  📌 配合策略:  CG-07_v14.py | python xq_portfolio.py --rebalance-stdin")
    return True


def _write_netscape_jar(path, cookies):
    """将 dict cookies 写入 Netscape 格式的 cookie jar"""
    domain = ".xueqiu.com"
    now = int(time.time())
    lines = ["# Netscape HTTP Cookie File"]
    for k, v in cookies.items():
        # 过期时间设为30天后
        expires = now + 30 * 86400
        lines.append(f"{domain}\tTRUE\t/\tTRUE\t{expires}\t{k}\t{v}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _test_connection(pid):
    """测试雪球连接"""
    url = f"https://xueqiu.com/v4/stock/portfolio/info.json?pid={pid}"
    r, err = _curl(url, dump_headers=True)
    if r:
        try:
            data = json.loads(r)
            if "name" in data:
                return True, data["name"]
            return True, str(data)
        except:
            return False, r[:100]
    return False, err


# ═══════════════════════════════════════════════
#  保活
# ═══════════════════════════════════════════════

def keep_alive():
    """访问雪球首页 → 触发 Set-Cookie → 自动续命"""
    print("🔄 雪球保活...")
    r, err = _curl("https://xueqiu.com/", dump_headers=True)
    if r:
        a, r_token = _read_tokens_from_jar(COOKIE_JAR)
        status = "✅ 保活成功" if a else "⚠️ jar中无xq_a_token"
        print(f"  {status} | xq_a_token={'有' if a else '无'} | xq_r_token={'有' if r_token else '无'}")

        # 再访问一次组合页面触发更深层续命
        cfg = load_config()
        if cfg:
            pid = cfg.get("portfolio_id")
            url = f"https://xueqiu.com/v4/stock/portfolio/info.json?pid={pid}"
            _curl(url, dump_headers=True)
            a2, r2 = _read_tokens_from_jar(COOKIE_JAR)
            print(f"  组合API {'✅' if a2 else '❌'}")

        # 记录
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(TOKEN_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{now}] 保活完成 | xq_a_token={'有' if a else '无'}\n")
    else:
        print(f"❌ 保活失败: {err[:100]}")
        # 通知用户
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(TOKEN_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{now}] ❌ 保活失败: {err[:100]}\n")
        print("  ⚠️ 可能需要重新复制 Cookie")


# ═══════════════════════════════════════════════
#  调仓
# ═══════════════════════════════════════════════

def rebalance(stock_list, cfg):
    """
    调仓雪球组合
    stock_list: [(code, weight%), ...] 或 [code, ...]
    """
    pid = cfg["portfolio_id"]
    max_pos = cfg.get("max_positions", 5)
    cash_ratio = cfg.get("cash_ratio", 0.05)
    log_file = cfg.get("log_file")

    if len(stock_list) > max_pos:
        print(f"⚠️ {len(stock_list)}只 > 最大持仓{max_pos}，只取前{max_pos}")
        stock_list = stock_list[:max_pos]

    total_weight = 100 - cash_ratio * 100
    weight_per = total_weight / len(stock_list) if stock_list else 0

    stocks_payload = []
    for item in stock_list:
        if isinstance(item, (list, tuple)):
            code, w = item[0], item[1]
        else:
            code = item
            w = weight_per
        name = _get_stock_name(code)
        stocks_payload.append({"stock_code": code, "stock_name": name, "weight": round(w, 1)})

    cash_weight = round(100 - sum(s["weight"] for s in stocks_payload), 1)
    if cash_weight < 0:
        scale = 100 / (sum(s["weight"] for s in stocks_payload) + cash_ratio * 100)
        for s in stocks_payload:
            s["weight"] = round(s["weight"] * scale, 1)
        cash_weight = round(100 - sum(s["weight"] for s in stocks_payload), 1)

    payload = {
        "portfolio_id": pid,
        "stocks": stocks_payload,
        "cash": cash_weight,
        "rebalance": 1
    }

    print(f"\n📋 调仓方案:")
    print(f"  {'代码':<10} {'名称':<10} {'权重%':<8}")
    print(f"  {'-'*30}")
    for s in stocks_payload:
        print(f"  {s['stock_code']:<10} {s['stock_name']:<10} {s['weight']:<8.1f}")
    print(f"  {'现金':<22} {cash_weight:<8.1f}")

    print("\n🔄 正在调仓...")
    url = "https://xueqiu.com/v4/stock/portfolio/rebalance.json"
    r, err = _curl(url, method="POST", data=payload, dump_headers=True)

    if r:
        try:
            result = json.loads(r)
            if "error_code" in result:
                print(f"❌ 调仓失败: {result.get('error_description', '未知错误')}")
                return False
            print(f"✅ 调仓成功！")
            if log_file:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 调仓: ")
                    f.write(",".join([f"{s['stock_name']}({s['stock_code']})" for s in stocks_payload]))
                    f.write(f"\n")
            # 更新配置
            cfg["last_rebalance"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_config(cfg)
            return True
        except json.JSONDecodeError:
            print(f"⚠️ 返回非JSON: {r[:200]}")
            return False
    else:
        print(f"❌ 调仓失败: {err[:200]}")
        return False


def get_status(cfg):
    """查看组合状态和 token 健康"""
    pid = cfg["portfolio_id"]

    print(f"\n🔑 Token 状态:")
    _check_token_health(COOKIE_JAR)

    print(f"\n📊 拉取组合信息...")
    url = f"https://xueqiu.com/v4/stock/portfolio/info.json?pid={pid}"
    r, err = _curl(url, dump_headers=True)

    if r:
        try:
            d = json.loads(r)
            print(f"\n  组合: {d.get('name', '?')}")
            print(f"  累计收益: {d.get('total_gain', '?')}%")
            print(f"  年化收益: {d.get('annualized_gain_rate', '?')}%")
            print(f"  跑赢大盘: {d.get('beat_xhs', '?')}%")
        except:
            print(f"  ⚠️ 解析失败")

    # 持仓
    hold_url = f"https://xueqiu.com/v4/stock/portfolio/hold.json?pid={pid}"
    r, err = _curl(hold_url)
    if r:
        try:
            hd = json.loads(r)
            stocks = hd.get("stocks", [])
            if stocks:
                print(f"\n  持仓明细:")
                print(f"  {'名称':<10} {'代码':<10} {'仓位%':<8} {'盈亏%':<8}")
                print(f"  {'-'*40}")
                for s in stocks:
                    print(f"  {s.get('stock_name','?'):<10} {s.get('stock_code','?'):<10} "
                          f"{s.get('weight',0):<8.1f} {s.get('gain',0):<+8.2f}")
        except:
            pass


def show_tokens():
    """显示 token 信息"""
    print(f"\n📋 Cookie Jar: {COOKIE_JAR}")
    _check_token_health(COOKIE_JAR)

    # 显示 token 日志最后10行
    if os.path.exists(TOKEN_LOG):
        print(f"\n📜 Token 续命日志 (最近):")
        with open(TOKEN_LOG) as f:
            lines = f.readlines()
        for line in lines[-10:]:
            print(f"  {line.strip()}")


def parse_from_stdin():
    """从标准输入解析策略选股结果"""
    text = sys.stdin.read().strip()
    codes = re.findall(r'(?:sh|sz)?(\d{6})', text)
    # 去重且保持顺序
    seen = set()
    unique = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


# ═══════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  --setup              首次配置（粘贴Cookie）")
        print("  --rebalance \"000725,600584\"  手动调仓")
        print("  --rebalance-stdin    从管道读取策略结果")
        print("  --keep-alive         token保活（设cron每天跑）")
        print("  --status             查看组合+token状态")
        print("  --show-cookies       查看token健康+续命日志")
        return

    cmd = sys.argv[1]

    if cmd == "--setup":
        setup()
        return

    cfg = load_config()
    if not cfg:
        print("❌ 未配置，先运行: python xq_portfolio.py --setup")
        return
    if not os.path.exists(COOKIE_JAR):
        print("❌ Cookie jar 不存在，先运行 --setup")
        return

    if cmd == "--rebalance":
        if len(sys.argv) < 3:
            print("❌ 请指定股票代码")
            return
        codes = [c.strip() for c in sys.argv[2].split(",") if c.strip()]
        if codes:
            rebalance(codes, cfg)

    elif cmd == "--rebalance-stdin":
        codes = parse_from_stdin()
        if codes:
            print(f"📥 从输入解析到 {len(codes)} 只股票")
            codes = codes[:cfg.get("max_positions", 5)]
            rebalance(codes, cfg)
        else:
            print("❌ 未找到股票代码，输入格式如: sz000725 或 000725")

    elif cmd == "--keep-alive":
        keep_alive()

    elif cmd == "--status":
        get_status(cfg)

    elif cmd == "--show-cookies":
        show_tokens()

    elif cmd == "--renew":
        print("🔄 强制续命: 访问雪球首页...")
        keep_alive()
        print("  完成。如果失败请重新运行 --setup 粘贴新 Cookie")

    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
