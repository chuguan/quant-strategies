#!/usr/bin/env python3
"""
本地模拟盘交易系统
══════════════════════
自动跟随策略信号，模拟买卖，记录持仓盈亏

数据文件: ~/AppData/Local/hermes/paper_trading/positions.json
         ~/AppData/Local/hermes/paper_trading/trades.csv
         ~/AppData/Local/hermes/paper_trading/performance.json

用法:
  买入:  python paper_trader.py --buy "000725" --price 5.16 --reason "CG-07冠军"
  卖出:  python paper_trader.py --sell "000725" --price 5.50
  状态:  python paper_trader.py --status
  自动检查: python paper_trader.py --check   (读缓存算当前盈亏)
  重置:   python paper_trader.py --reset
  设置资金: python paper_trader.py --capital 30000
  导入策略: python paper_trader.py --import-strategy "000725,600584,601127"
  每日报告: python paper_trader.py --report | python send_email.py --subject "模拟盘日报"
"""

import json, os, csv, sys, time, subprocess
from datetime import datetime, date
from copy import deepcopy

BASE_DIR = os.path.expanduser("~/AppData/Local/hermes/paper_trading")
POS_FILE = os.path.join(BASE_DIR, "positions.json")
TRADE_FILE = os.path.join(BASE_DIR, "trades.csv")
PERF_FILE = os.path.join(BASE_DIR, "performance.json")
CACHE_DIR = os.path.expanduser("~/AppData/Local/hermes/hermes-agent/cache")
os.makedirs(BASE_DIR, exist_ok=True)

DEFAULT_CAPITAL = 30000

# ═══════════════════════════════════════════════
#  数据层
# ═══════════════════════════════════════════════

def _load():
    """加载持仓"""
    if os.path.exists(POS_FILE):
        with open(POS_FILE) as f:
            return json.load(f)
    return {
        "capital": DEFAULT_CAPITAL,       # 初始资金
        "cash": DEFAULT_CAPITAL,          # 剩余现金
        "positions": {},                  # {code: {qty, avg_cost, current_price, ...}}
        "total_buy": 0,                   # 累计买入金额
        "total_sell": 0,                  # 累计卖出金额
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

def _save(state):
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(POS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def _log_trade(trade_type, code, name, price, qty, reason=""):
    """记录交易到CSV"""
    with open(TRADE_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if os.path.getsize(TRADE_FILE) == 0:
            w.writerow(["日期", "类型", "代码", "名称", "价格", "数量", "金额", "原因"])
        w.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            trade_type, code, name,
            f"{price:.2f}", qty,
            f"{price*qty:.2f}", reason
        ])

def _get_stock_name(code):
    """获取股票名称"""
    m = "sh" if code.startswith("6") else "sz"
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "5",
            f"https://qt.gtimg.cn/q={m}{code}"], capture_output=True, timeout=8)
        text = r.stdout.decode("gbk", errors="replace")
        parts = text.split("~")
        if len(parts) > 2:
            return parts[1]
    except:
        pass
    return code

def _get_latest_price(code):
    """从缓存获取最新价格和涨幅"""
    name = _get_stock_name(code)
    # 先从缓存取最新收盘价
    cache_file = os.path.join(CACHE_DIR, f"{code}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                recs = json.loads(f.read().decode("utf-8"))
            if recs:
                last = recs[-1]
                return {
                    "price": last["close"],
                    "high": last["high"],
                    "low": last["low"],
                    "open": last["open"],
                    "volume": last["volume"],
                    "date": last["date"],
                    "name": name,
                }
        except:
            pass
    
    # 缓存放不下有从实时查
    m = "sh" if code.startswith("6") else "sz"
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "5",
            f"https://qt.gtimg.cn/q={m}{code}"], capture_output=True, timeout=8)
        text = r.stdout.decode("gbk", errors="replace")
        parts = text.split("~")
        if len(parts) > 33:
            return {
                "price": float(parts[3]),
                "high": float(parts[33]),
                "low": float(parts[34]),
                "open": float(parts[5]),
                "volume": float(parts[6]) if parts[6] else 0,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "name": parts[1],
            }
    except:
        pass
    
    return {"price": 0, "name": code}


# ═══════════════════════════════════════════════
#  交易操作
# ═══════════════════════════════════════════════

def buy(code, price=None, qty=0, reason=""):
    """模拟买入"""
    state = _load()
    info = _get_latest_price(code)
    name = info["name"]
    cur_price = price or info["price"]
    
    if cur_price <= 0:
        print(f"❌ 无法获取 {code} 的价格")
        return False
    
    # 如果qty为0，全仓买入
    if qty <= 0:
        max_shares = int(state["cash"] / cur_price / 100) * 100
        if max_shares < 100:
            print(f"❌ 现金不足 {state['cash']:.2f}，最少买100股需 {cur_price*100:.2f}")
            return False
        qty = max_shares
    
    cost = qty * cur_price
    if cost > state["cash"]:
        print(f"❌ 现金不足 需{cost:.2f} 有{state['cash']:.2f}")
        return False
    
    code = _fmt_code(code)
    
    # 已有持仓 → 加仓
    if code in state["positions"]:
        pos = state["positions"][code]
        total_cost = pos["avg_cost"] * pos["qty"] + cost
        pos["qty"] += qty
        pos["avg_cost"] = total_cost / pos["qty"]
        pos["current_price"] = cur_price
    else:
        state["positions"][code] = {
            "code": code,
            "name": name,
            "qty": qty,
            "avg_cost": cur_price,
            "current_price": cur_price,
            "buy_date": datetime.now().strftime("%Y-%m-%d"),
            "buy_reason": reason,
        }
    
    state["cash"] -= cost
    state["total_buy"] += cost
    _save(state)
    _log_trade("买入", code, name, cur_price, qty, reason)
    print(f"✅ 买入 {name}({code}) {qty}股 @ {cur_price:.2f} = {cost:.2f}")
    print(f"   现金余额: {state['cash']:.2f}")
    return True


def sell(code, price=None, qty=0, reason="止盈/止损"):
    """模拟卖出"""
    state = _load()
    code = _fmt_code(code)
    
    if code not in state["positions"]:
        print(f"❌ 未持有 {code}")
        return False
    
    pos = state["positions"][code]
    name = pos["name"]
    info = _get_latest_price(code)
    cur_price = price or info["price"]
    
    if cur_price <= 0:
        print(f"❌ 无法获取 {code} 价格")
        return False
    
    if qty <= 0 or qty > pos["qty"]:
        qty = pos["qty"]  # 全卖
    
    proceeds = qty * cur_price
    cost_basis = qty * pos["avg_cost"]
    profit = proceeds - cost_basis
    profit_pct = (cur_price / pos["avg_cost"] - 1) * 100
    
    state["cash"] += proceeds
    state["total_sell"] += proceeds
    pos["qty"] -= qty
    
    if pos["qty"] <= 0:
        del state["positions"][code]
    else:
        state["positions"][code] = pos
    
    _save(state)
    _log_trade("卖出", code, name, cur_price, qty, reason)
    print(f"✅ 卖出 {name}({code}) {qty}股 @ {cur_price:.2f} = {proceeds:.2f}")
    print(f"   盈亏: {profit:+.2f} ({profit_pct:+.2f}%)")
    print(f"   现金余额: {state['cash']:.2f}")
    return True


def check_positions():
    """检查所有持仓的当前盈亏"""
    state = _load()
    if not state["positions"]:
        print("📭 无持仓")
        return
    
    total_cost = 0
    total_value = 0
    print(f"\n📊 模拟盘持仓 (现金: {state['cash']:.2f})")
    print(f"  {'名称':<10} {'代码':<10} {'数量':<8} {'成本':<10} {'现价':<10} {'盈亏%':<10} {'浮动盈亏':<10}")
    print(f"  {'-'*70}")
    
    for code, pos in sorted(state["positions"].items()):
        info = _get_latest_price(code)
        cur = info["price"] if info["price"] > 0 else pos["current_price"]
        cost = pos["avg_cost"]
        pnl = (cur / cost - 1) * 100
        float_pnl = (cur - cost) * pos["qty"]
        cost_total = cost * pos["qty"]
        val_total = cur * pos["qty"]
        total_cost += cost_total
        total_value += val_total
        
        print(f"  {pos['name']:<10} {code:<10} {pos['qty']:<8} {cost:<10.2f} {cur:<10.2f} "
              f"{pnl:<+10.2f}% {float_pnl:<+10.2f}")
        
        # 更新现价
        pos["current_price"] = cur
    
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0
    total_assets = state["cash"] + total_value
    
    print(f"  {'-'*70}")
    print(f"  {'合计':<18} {'':<8} {total_cost:<10.2f} {total_value:<10.2f} "
          f"{total_pnl_pct:<+10.2f}% {total_pnl:<+10.2f}")
    print(f"  总资产: {total_assets:.2f}  总盈亏: {total_pnl_pct:+.2f}%")
    
    state["positions"] = {k: v for k, v in state["positions"].items()}
    _save(state)


def show_status():
    """显示完整状态"""
    state = _load()
    total_pos = len(state["positions"])
    
    print(f"\n{'='*50}")
    print(f"  模拟盘概览")
    print(f"{'='*50}")
    print(f"  初始资金: {state['capital']:.2f}")
    print(f"  剩余现金: {state['cash']:.2f}")
    print(f"  持仓数量: {total_pos} 只")
    print(f"  累计买入: {state['total_buy']:.2f}")
    print(f"  累计卖出: {state['total_sell']:.2f}")
    print(f"  {'='*50}")
    
    if state["positions"]:
        check_positions()

    # 交易记录
    if os.path.exists(TRADE_FILE):
        with open(TRADE_FILE) as f:
            lines = f.readlines()
        print(f"\n📜 交易记录 (最近10条):")
        for line in lines[-10:]:
            print(f"  {line.strip()}")


def reset(confirm=True):
    """重置模拟盘"""
    if confirm:
        print("⚠️ 重置将清空所有持仓和交易记录！")
        try:
            r = input("确认重置? (y/N): ")
            if r.lower() != "y":
                print("已取消")
                return
        except:
            print("非交互模式，跳过")
            return
    state = {
        "capital": DEFAULT_CAPITAL,
        "cash": DEFAULT_CAPITAL,
        "positions": {},
        "total_buy": 0,
        "total_sell": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _save(state)
    # 清空交易记录
    if os.path.exists(TRADE_FILE):
        os.remove(TRADE_FILE)
    print("✅ 模拟盘已重置")


def _fmt_code(code):
    """统一代码格式，去掉sh/sz前缀"""
    return code.replace("sh", "").replace("sz", "")


def import_strategy(codes_str):
    """从策略结果导入 - 等权买入Top N"""
    codes = [c.strip().replace("sh", "").replace("sz", "") 
             for c in codes_str.replace(",", " ").split() 
             if c.strip() and len(c.strip()) >= 6]
    if not codes:
        print("❌ 未识别到股票代码")
        return
    
    state = _load()
    per_stock = state["cash"] / len(codes) if codes else 0
    
    print(f"\n📥 从策略导入 {len(codes)} 只股票, 每只预算 {per_stock:.2f}")
    for code in codes:
        info = _get_latest_price(code)
        price = info["price"]
        if price <= 0:
            print(f"  ⚠️ {code}: 无法获取价格，跳过")
            continue
        qty = int(per_stock / price / 100) * 100
        if qty >= 100:
            buy(code, price, qty, "策略导入")
        else:
            print(f"  ⚠️ {code}: 预算不足买100股 ({price*100:.2f} > {per_stock:.2f})")


def make_report():
    """生成日报文本"""
    state = _load()
    lines = []
    lines.append(f"📊 模拟盘日报 {date.today()}")
    lines.append("=" * 40)
    lines.append(f"初始资金: {state['capital']:.0f}")
    lines.append(f"剩余现金: {state['cash']:.0f}")
    
    if state["positions"]:
        total_val = 0
        total_cost = 0
        lines.append(f"\n持仓:")
        for code, pos in sorted(state["positions"].items()):
            info = _get_latest_price(code)
            cur = info["price"] if info["price"] > 0 else pos["current_price"]
            pnl = (cur / pos["avg_cost"] - 1) * 100
            val = cur * pos["qty"]
            cost = pos["avg_cost"] * pos["qty"]
            total_val += val
            total_cost += cost
            lines.append(f"  {pos['name']:<8} {pos['qty']:>4}股  {pos['avg_cost']:.2f}→{cur:.2f}  {pnl:+.1f}%")
        
        total_pnl = total_val - total_cost
        total_pnl_pct = (total_val / total_cost - 1) * 100
        total_assets = state["cash"] + total_val
        lines.append(f"\n总资产: {total_assets:.0f}  ({state['capital']:.0f}→{total_assets:.0f})")
        lines.append(f"总盈亏: {total_pnl:+.1f}  ({total_pnl_pct:+.1f}%)")
    else:
        lines.append(f"\n📭 空仓")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(f"用法:")
        print(f"  --buy CODE [--price X] [--qty N] [--reason \"...\"]     买入")
        print(f"  --sell CODE [--price X] [--qty N] [--reason \"...\"]    卖出")
        print(f"  --check                                                  检查持仓盈亏")
        print(f"  --status                                                 完整状态")
        print(f"  --capital AMOUNT                                        设置初始资金")
        print(f"  --import CODE1,CODE2,...                                策略导入(等权买入)")
        print(f"  --report                                                 生成日报文本")
        print(f"  --reset                                                  重置（清空所有）")
        return
    
    cmd = sys.argv[1]
    
    # 解析公共参数
    kwargs = {}
    for arg in ["--price", "--qty", "--reason", "--code"]:
        if arg in sys.argv:
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                kwargs[arg[2:]] = sys.argv[idx + 1]
    
    if cmd == "--buy":
        code = kwargs.get("code") or (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None)
        if not code:
            print("❌ 请指定股票代码")
            return
        price = float(kwargs["price"]) if "price" in kwargs else None
        qty = int(kwargs["qty"]) if "qty" in kwargs else 0
        reason = kwargs.get("reason", "手动买入")
        buy(code, price, qty, reason)
    
    elif cmd == "--sell":
        code = kwargs.get("code") or (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None)
        if not code:
            print("❌ 请指定股票代码")
            return
        price = float(kwargs["price"]) if "price" in kwargs else None
        qty = int(kwargs["qty"]) if "qty" in kwargs else 0
        reason = kwargs.get("reason", "手动卖出")
        sell(code, price, qty, reason)
    
    elif cmd == "--check":
        check_positions()
    
    elif cmd == "--status":
        show_status()
    
    elif cmd == "--report":
        print(make_report())
    
    elif cmd == "--reset":
        reset("--force" in sys.argv)
    
    elif cmd == "--capital":
        if len(sys.argv) > 2:
            amt = float(sys.argv[2])
            state = _load()
            diff = amt - state["capital"]
            state["capital"] = amt
            state["cash"] += diff
            if state["cash"] < 0:
                state["cash"] = 0
            _save(state)
            print(f"✅ 初始资金设为 {amt:.0f}")
        else:
            print("❌ 请指定金额")
    
    elif cmd == "--import":
        if len(sys.argv) > 2:
            import_strategy(sys.argv[2])
        else:
            print("❌ 请指定股票代码")
    
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
