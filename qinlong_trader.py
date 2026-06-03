#!/usr/bin/env python3
"""
擒龙MAX 自动交易系统 — 完整模拟盘方案
═══════════════════════════════════════
【逻辑】
  尾盘运行擒龙MAX → 取评分TOP 3 → 检查持仓止盈止损 → 买入新票
【资金】
  初始本金30,000，等权分配，最多3只持仓
【卖出规则】
  +7% → 止盈清仓
  -3% → 止损清仓
  持仓超5天 → 时间止损清仓
【买入规则】
  擒龙MAX评分TOP 3，每只等权分配

用法:
  尾盘交易:  python qinlong_trader.py --trade
  检查持仓:  python qinlong_trader.py --check
  预览方案:  python qinlong_trader.py --plan
  日报:      python qinlong_trader.py --report
  重置:      python qinlong_trader.py --reset
"""

import json, os, sys, subprocess, re, time, csv
from datetime import datetime, date

CAPITAL = 30000
MAX_POS = 3
TAKE_PROFIT = 0.07
STOP_LOSS = -0.03
MAX_DAYS = 5
CASH_RESERVE = 0.05

BASE = os.path.expanduser("~/AppData/Local/hermes/paper_trading")
POS_FILE = os.path.join(BASE, "positions.json")
TRADE_FILE = os.path.join(BASE, "trades.csv")
PERF_FILE = os.path.join(BASE, "performance.json")
SCAN_FILE = os.path.join(BASE, "last_scan_result.json")
os.makedirs(BASE, exist_ok=True)
SEP = "=" * 50
DASH = "-" * 40


def load_positions():
    if not os.path.exists(POS_FILE):
        return {"capital": CAPITAL, "cash": CAPITAL, "positions": {},
                "total_buy": 0, "total_sell": 0}
    with open(POS_FILE) as f:
        return json.load(f)


def save_positions(state):
    with open(POS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def log_trade(tp, code, name, price, qty, reason=""):
    with open(TRADE_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if os.path.getsize(TRADE_FILE) == 0:
            w.writerow(["日期", "类型", "代码", "名称", "价格", "数量", "金额", "原因"])
        w.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            tp, code, name, f"{price:.2f}", qty, f"{price*qty:.2f}", reason
        ])


def batch_query(codes):
    if not codes:
        return {}
    qid = ",".join(codes)
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "12",
            f"https://qt.gtimg.cn/q={qid}"], capture_output=True, timeout=15)
        text = r.stdout.decode("gbk", errors="replace")
    except:
        return {}
    result = {}
    for line in text.strip().split(";"):
        line = line.strip().strip(";")
        if not line or "=" not in line:
            continue
        pts = line.split("~")
        if len(pts) < 33:
            continue
        try:
            cf = pts[2]
            code = cf.replace("sh", "").replace("sz", "")
            price = float(pts[3]) if pts[3] else 0
            pct = float(pts[32]) if pts[32] else 0
            name = pts[1]
            result[code] = {"code": code, "name": name, "price": price, "pct": pct}
        except:
            continue
    return result


# ═══ 擒龙MAX扫描 ═══

def run_scan():
    print("  🔄 运行擒龙MAX扫描...")
    ql = os.path.expanduser("~/AppData/Local/hermes/hermes-agent/qinlong_max.py")
    if not os.path.exists(ql):
        print(f"  ❌ 找不到 qinlong_max.py")
        return []
    try:
        r = subprocess.run(["python", ql], capture_output=True, timeout=300, text=True)
        out = r.stdout
    except Exception as e:
        print(f"  ❌ 扫描失败: {e}")
        return []

    top_list = []
    for line in out.split("\n"):
        ls = line.strip()
        m = re.match(r'(\d+)\.\s+(.+)\s{2,}(\d{6})\s+([\d.]+)\s+([+-][\d.]+)%\s+(\d+)分', ls)
        if m:
            top_list.append({
                "rank": int(m.group(1)), "name": m.group(2).strip(),
                "code": m.group(3), "price": float(m.group(4)),
                "pct": float(m.group(5)), "score": int(m.group(6))
            })

    print(f"  ✅ 解析到 {len(top_list)} 只")
    with open(SCAN_FILE, "w", encoding="utf-8") as f:
        json.dump({"time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "top_list": top_list}, f, ensure_ascii=False, indent=2)
    return top_list


# ═══ 交易决策 ═══

def execute_trades(top_list):
    state = load_positions()
    today = date.today().isoformat()
    trades = []

    print(f"\n{SEP}")
    print(f"  擒龙MAX 交易执行 — {today}")
    print(f"  资金: 总{state['capital']:.0f} | 现金{state['cash']:.0f} | "
          f"持仓{len(state['positions'])}只")
    print(SEP)

    # 收集需要实时报价的股票
    need = set(state["positions"].keys())
    if top_list:
        for t in top_list[:MAX_POS]:
            need.add(t["code"])

    qc = []
    for c in need:
        if c.startswith("6"):
            qc.append(f"sh{c}")
        else:
            qc.append(f"sz{c}")

    print(f"\n  📡 查询 {len(qc)} 只实时行情...")
    prices = batch_query(qc)
    print(f"     获取到 {len(prices)} 只")

    # 步骤一：检查持仓 → 卖出
    print(f"\n  {DASH}")
    print(f"  步骤一：检查持仓")
    print(f"  {DASH}")

    for code, pos in list(state["positions"].items()):
        name = pos["name"]
        bp = pos["avg_cost"]
        qty = pos["qty"]
        bd = pos.get("buy_date", "")
        cur = prices.get(code, {}).get("price", pos.get("current_price", bp))
        pnl = (cur / bp - 1) * 100

        days = (date.today() - date.fromisoformat(bd)).days if bd else 0
        reason = None

        if pnl >= TAKE_PROFIT * 100:
            reason = f"止盈📈 +{pnl:.1f}%"
        elif pnl <= STOP_LOSS * 100:
            reason = f"止损📉 {pnl:.1f}%"
        elif days >= MAX_DAYS:
            reason = f"时间⏰ {days}天"

        if reason:
            proceeds = cur * qty
            profit = proceeds - bp * qty
            print(f"    🚩 {name}({code}) {bp:.2f}->{cur:.2f} {pnl:+.1f}% | {reason}")
            print(f"      卖出{qty}股={proceeds:.0f} 盈亏{profit:+.0f}")
            state["cash"] += proceeds
            state["total_sell"] += proceeds
            del state["positions"][code]
            log_trade("卖出", code, name, cur, qty, reason)
            trades.append(("卖出", code, name, cur, qty, profit))
        else:
            print(f"    ✓ {name}({code}) {bp:.2f}->{cur:.2f} {pnl:+.1f}% "
                  f"({days}天) 持有")

    # 步骤二：买入TOP 3
    print(f"\n  {DASH}")
    print(f"  步骤二：买入擒龙TOP 3")
    print(f"  {DASH}")

    if top_list:
        top3 = top_list[:MAX_POS]
        print()
        for t in top3:
            print(f"    {t['rank']}. {t['name']}({t['code']}) "
                  f"{t['price']:.2f} {t['pct']:+.2f}% 评分{t['score']}")

        per_amt = state["cash"] * (1 - CASH_RESERVE) / MAX_POS

        for t in top3:
            code, name, price = t["code"], t["name"], t["price"]
            if code in state["positions"]:
                print(f"    ⏭ {name}({code}) 已持有")
                continue
            if price <= 0:
                print(f"    ⚠ {name}({code}) 价格异常")
                continue

            max_qty = int(per_amt / price / 100) * 100
            if max_qty < 100:
                print(f"    ⚠ {name}({code}) 资金不足")
                continue
            cost = max_qty * price
            if cost > state["cash"]:
                max_qty = int(state["cash"] / price / 100) * 100
                if max_qty < 100:
                    continue
                cost = max_qty * price

            print(f"    🟢 买入 {name}({code}) {max_qty}股 @ {price:.2f} = {cost:.0f}")
            state["positions"][code] = {
                "code": code, "name": name, "qty": max_qty,
                "avg_cost": price, "current_price": price,
                "buy_date": today, "buy_reason": f"擒龙TOP{t['rank']}",
            }
            state["cash"] -= cost
            state["total_buy"] += cost
            log_trade("买入", code, name, price, max_qty,
                     f"擒龙MAX #{t['rank']} 评分{t['score']}")
            trades.append(("买入", code, name, price, max_qty, -cost))

    save_positions(state)
    perf = calc_perf(state)
    with open(PERF_FILE, "w", encoding="utf-8") as f:
        json.dump(perf, f, ensure_ascii=False, indent=2)
    return trades, state


def calc_perf(state):
    pv = sum(p["qty"] * p.get("current_price", p["avg_cost"])
             for p in state["positions"].values())
    ta = state["cash"] + pv
    return {
        "date": date.today().isoformat(),
        "capital": state["capital"], "cash": state["cash"],
        "positions": len(state["positions"]), "position_value": pv,
        "total_assets": ta,
        "total_pnl": round(ta - state["capital"], 2),
        "total_pnl_pct": round((ta / state["capital"] - 1) * 100, 2),
        "total_buy": state["total_buy"], "total_sell": state["total_sell"],
    }


# ═══ 报告 ═══

def gen_report(top_list=None, trades=None, state=None):
    if state is None:
        state = load_positions()
    today = date.today().isoformat()
    pv = sum(p["qty"] * p.get("current_price", p["avg_cost"])
             for p in state["positions"].values())
    ta = state["cash"] + pv
    pp = (ta / state["capital"] - 1) * 100

    lines = [SEP]
    lines.append(f"  擒龙MAX 模拟盘日报 {today}")
    lines.append(SEP)
    lines.append("")
    lines.append(f"  资金: {state['capital']:.0f} -> {ta:.0f}")
    lines.append(f"  盈亏: {ta-state['capital']:+.0f} ({pp:+.1f}%)")
    lines.append(f"  现金: {state['cash']:.0f} | 持仓: {len(state['positions'])}只")
    lines.append("")

    if state["positions"]:
        lines.append(f"  {'名称':<10} {'数量':<6} {'成本':<8} {'现价':<8} {'盈亏%':<8}")
        lines.append(f"  {'-'*42}")
        for code, pos in sorted(state["positions"].items()):
            pnl = (pos["current_price"] / pos["avg_cost"] - 1) * 100
            lines.append(f"  {pos['name']:<10} {pos['qty']:<6} {pos['avg_cost']:<8.2f} "
                        f"{pos['current_price']:<8.2f} {pnl:<+8.1f}%")
    else:
        lines.append("  📭 空仓")
    lines.append("")

    if trades:
        lines.append("  今日交易:")
        for t in trades:
            if t[0] == "买入":
                lines.append(f"    🟢 买入 {t[2]}({t[1]}) {t[4]}股 @ {t[3]:.2f}")
            else:
                lines.append(f"    🚩 卖出 {t[2]}({t[1]}) {t[4]}股 @ {t[3]:.2f} "
                            f"盈亏{t[5]:+.0f}")
    if top_list:
        lines.append("")
        lines.append("  擒龙MAX TOP 3:")
        for t in top_list[:3]:
            lines.append(f"    {t['rank']}. {t['name']}({t['code']}) "
                        f"{t['price']:.2f} {t['pct']:+.2f}% 评分{t['score']}")
    lines.append("")
    lines.append("  📋 止盈+7% | 止损-3% | 持仓<=5天")
    lines.append(SEP)
    return "\n".join(lines)


# ═══ 命令 ═══

def cmd_plan():
    print(f"\n📋 今日擒龙MAX方案")
    print(SEP)
    top = run_scan()
    if not top:
        print("  ❌ 无选股")
        return
    print(f"\n🏆 TOP 10:")
    print(f"  {'#':<3} {'名称':<10} {'代码':<8} {'价格':<8} {'涨幅':<8} {'评分':<5}")
    print(f"  {'-'*42}")
    for t in top:
        m = "🏆" if t["rank"] <= 3 else ""
        print(f"  {t['rank']:<3} {t['name']:<10} {t['code']:<8} "
              f"{t['price']:<8.2f} {t['pct']:<+8.2f}% {t['score']:<5} {m}")
    state = load_positions()
    per = state["cash"] * (1 - CASH_RESERVE) / MAX_POS
    print(f"\n📥 拟买入:")
    for t in top[:3]:
        qty = int(per / t["price"] / 100) * 100
        held = " (已持有)" if t["code"] in state["positions"] else ""
        print(f"  {t['name']}({t['code']}) {t['price']:.2f} -> {qty}股 {held}")


def cmd_trade():
    top = run_scan()
    if top is None:
        return
    trades, state = execute_trades(top)
    print(f"\n{SEP}")
    print("  ✅ 交易执行完成")
    print(SEP)
    print()
    print(gen_report(top, trades, state))


def cmd_check():
    state = load_positions()
    if not state["positions"]:
        print("  📭 空仓")
        return
    print(f"\n📊 持仓检查 ({date.today()})")
    print(SEP)
    qc = [f"sh{c}" if c.startswith("6") else f"sz{c}" for c in state["positions"]]
    prices = batch_query(qc)
    tv, tc = 0, 0
    print(f"  {'名称':<10} {'代码':<8} {'数量':<6} {'成本':<8} {'现价':<8} {'盈亏%':<8}")
    print(f"  {'-'*52}")
    for code, pos in sorted(state["positions"].items()):
        cur = prices.get(code, {}).get("price", pos["current_price"])
        pnl = (cur / pos["avg_cost"] - 1) * 100
        val = cur * pos["qty"]
        cost = pos["avg_cost"] * pos["qty"]
        tv += val
        tc += cost
        pos["current_price"] = cur
        print(f"  {pos['name']:<10} {code:<8} {pos['qty']:<6} "
              f"{pos['avg_cost']:<8.2f} {cur:<8.2f} {pnl:<+8.1f}%")
    save_positions(state)
    pp = (tv / tc - 1) * 100 if tc > 0 else 0
    print(f"  {'-'*52}")
    print(f"  {'合计':<18} {tc:<8.2f} {tv:<8.2f} {pp:<+8.1f}%")
    print(f"  总资产: {state['cash']+tv:.0f} | 现金: {state['cash']:.0f}")


def cmd_report():
    state = load_positions()
    top = []
    if os.path.exists(SCAN_FILE):
        try:
            with open(SCAN_FILE) as f:
                top = json.load(f).get("top_list", [])
        except:
            pass
    print(gen_report(top, None, state))


def cmd_reset():
    state = {"capital": CAPITAL, "cash": CAPITAL, "positions": {},
             "total_buy": 0, "total_sell": 0}
    save_positions(state)
    for p in [TRADE_FILE, SCAN_FILE]:
        if os.path.exists(p):
            os.remove(p)
    print(f"✅ 已重置（初始资金 {CAPITAL}）")


def cmd_email():
    """生成日报并通过邮件发送"""
    state = load_positions()
    top = []
    if os.path.exists(SCAN_FILE):
        try:
            with open(SCAN_FILE) as f:
                top = json.load(f).get("top_list", [])
        except:
            pass
    report = gen_report(top, None, state)
    print(report)

    # 调用send_email发送
    email_script = os.path.expanduser("~/AppData/Local/hermes/scripts/send_email.py")
    if os.path.exists(email_script):
        today = date.today().isoformat()
        try:
            r = subprocess.run(
                ["python", email_script,
                 "--subject", f"擒龙MAX 模拟盘日报 {today}"],
                input=report, capture_output=True, timeout=30, text=True)
            print(f"  📧 邮件发送: {r.stdout.strip() or 'ok'}")
        except Exception as e:
            print(f"  ⚠ 邮件发送失败: {e}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  --trade      尾盘交易（扫描->决策->执行）")
        print("  --plan       预览方案（不下单）")
        print("  --check      检查持仓")
        print("  --report     日报")
        print("  --email      日报+邮件")
        print("  --reset      重置")
        return
    cmd = sys.argv[1]
    cmds = {
        "--trade": cmd_trade, "--plan": cmd_plan, "--check": cmd_check,
        "--report": cmd_report, "--email": cmd_email, "--reset": cmd_reset,
    }
    f = cmds.get(cmd)
    if f:
        f()
    else:
        print(f"  ❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
