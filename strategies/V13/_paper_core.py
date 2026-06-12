#!/usr/bin/env python3
"""CG18 模拟盘核心 — 资金管理 + 持仓管理 + 监控 + 通知"""
import json, os, time, subprocess
from datetime import datetime, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
POS_FILE = os.path.join(DIR, '_positions.json')
LOG_FILE = os.path.join(DIR, '_trade_log.json')
ACCOUNT_FILE = os.path.join(DIR, '_account.json')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
INITIAL_CAPITAL = 30000.0

# ====== 资金管理 ======
def load_account():
    if os.path.exists(ACCOUNT_FILE):
        with open(ACCOUNT_FILE) as f:
            return json.load(f)
    return init_account()

def init_account():
    acct = {
        'initial_capital': INITIAL_CAPITAL,
        'available_cash': INITIAL_CAPITAL,
        'total_pnl': 0.0,
        'total_return_pct': 0.0,
    }
    save_account(acct)
    return acct

def save_account(acct):
    with open(ACCOUNT_FILE, 'w') as f:
        json.dump(acct, f, ensure_ascii=False, indent=2)

def get_account_summary():
    """返回账户摘要文本"""
    acct = load_account()
    positions = load_positions()
    active = [p for p in positions if p['status'] == '持有']
    total_cost = sum(p.get('cost', 0) for p in active) if active else 0
    total_market = 0
    for p in active:
        price, _, _, _ = get_live_price(p['code'])
        if price > 0:
            total_market += price * p.get('shares', 0)
        else:
            total_market += p.get('cost', 0)
    total_assets = acct['available_cash'] + total_market
    total_pnl = total_assets - acct['initial_capital']
    total_ret = total_pnl / acct['initial_capital'] * 100
    acct['total_pnl'] = round(total_pnl, 2)
    acct['total_return_pct'] = round(total_ret, 2)
    save_account(acct)
    return acct, total_market, total_assets

# ====== 持仓管理 ======
def load_positions():
    if os.path.exists(POS_FILE):
        with open(POS_FILE) as f:
            return json.load(f)
    return []

def save_positions(positions):
    with open(POS_FILE, 'w') as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return []

def save_log(log):
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def add_position(code, name, buy_price, buy_date=None, market_type='', buy_pct=0):
    """添加一笔模拟买入（全仓梭哈，自动先清旧仓）"""
    if buy_date is None:
        buy_date = datetime.now().strftime('%Y-%m-%d')
    
    # 第一步：先清所有旧持仓，确保资金回笼
    force_sell_all('尾盘换仓清仓')
    
    positions = load_positions()
    # 检查是否已有同一天同一只
    for p in positions:
        if p['code'] == code and p['buy_date'] == buy_date and p['status'] == '持有':
            return p  # 已存在

    # 资金管理：全仓买入
    acct = load_account()
    cash = acct['available_cash']
    if cash <= 0:
        print('⚠️ 可用余额不足，无法买入', flush=True)
        return None

    shares = int(cash / buy_price / 100) * 100  # 整手
    if shares <= 0:
        print('⚠️ 余额不足以买入1手(100股)', flush=True)
        return None

    cost = round(shares * buy_price, 2)
    acct['available_cash'] = round(cash - cost, 2)
    save_account(acct)

    pos = {
        'code': code,
        'name': name,
        'shares': shares,
        'buy_price': round(buy_price, 2),
        'cost': cost,
        'buy_date': buy_date,
        'buy_time': datetime.now().strftime('%H:%M'),
        'buy_pct': round(buy_pct, 1),
        'status': '持有',
        'high_seen': round(buy_price, 2),
        'low_seen': round(buy_price, 2),
        'sell_date': None,
        'sell_price': 0,
        'return_pct': 0,
        'sell_reason': '',
        'market_type': market_type,
        # 回望卖出参数
        'trailing_activated': False,
        'trailing_peak': round(buy_price, 2),
        'trailing_drop': 0.3,       # 回落0.3%触发卖出
        'trail_activate': get_version_trail_activate(),  # 2.5%或3%激活
    }
    positions.append(pos)
    save_positions(positions)
    log_trade(pos, '买入')
    print(f'✅ 模拟买入: {name}({code}) {cost:.2f}元({shares}股@{buy_price:.2f})', flush=True)
    return pos

def get_live_price(code):
    """从腾讯API获取实时价 + 当日最高最低
    返回: (当前价, 涨幅%, 当日最高, 当日最低)"""
    prefix = 'sh' if code.startswith(('6','9')) else 'sz'
    url = f'https://qt.gtimg.cn/q={prefix}{code}'
    try:
        r = subprocess.run(['curl','-s','--max-time',str(5),url], capture_output=True, timeout=10)
        text = r.stdout.decode('gbk', errors='replace')
        if '~' in text:
            parts = text.split('~')
            if len(parts) > 3:
                price = float(parts[3]) if parts[3] else 0
                pct = float(parts[32]) if len(parts) > 32 and parts[32] else 0
                high = float(parts[33]) if len(parts) > 33 and parts[33] else 0
                low = float(parts[34]) if len(parts) > 34 and parts[34] else 0
                return price, pct, high, low
    except:
        pass
    return 0, 0, 0, 0

def calculate_shares_to_sell(pos, price):
    """计算卖出股数和金额，返回资金"""
    shares = pos.get('shares', 0)
    if shares <= 0:
        # 兼容旧数据：无shares字段时按全部资金算
        return None  # 表示全卖出
    proceeds = round(shares * price, 2)
    return proceeds

def sell_position(pos, price, date, reason, cur_pct):
    """执行卖出，返回信号"""
    pos['status'] = '已卖出'
    pos['sell_price'] = round(price, 2)
    pos['sell_date'] = date
    pos['sell_time'] = datetime.now().strftime('%H:%M')
    pos['return_pct'] = round(cur_pct, 1)
    pos['sell_reason'] = reason

    # 资金回账
    shares = pos.get('shares', 0)
    if shares > 0:
        proceeds = round(shares * price, 2)
        pnl = round(proceeds - pos['cost'], 2)
    else:
        # 旧数据兼容
        proceeds = price * 100
        pnl = round(proceeds - pos['buy_price'] * 100, 2)
    
    acct = load_account()
    acct['available_cash'] = round(acct['available_cash'] + proceeds, 2)
    acct['total_pnl'] = round(acct.get('total_pnl', 0) + pnl, 2)
    acct['total_return_pct'] = round(acct['total_pnl'] / acct['initial_capital'] * 100, 2)
    save_account(acct)
    
    log_trade(pos, reason)
    return pos

def get_version_trail_activate():
    """根据目录名返回回望激活线"""
    dn = os.path.basename(DIR)
    if 'CG18' in dn: return 3.0   # CG18: +3%激活回望
    if '1180' in dn or '1180' in dn: return 3.0  # 1180: +3%激活回望
    return 2.5                     # 其他: +2.5%激活回望

def force_sell_all(reason='尾盘换仓清仓'):
    """卖出所有持仓，用于尾盘换仓前清仓"""
    positions = load_positions()
    signals = []
    today = datetime.now().strftime('%Y-%m-%d')
    for pos in positions:
        if pos['status'] != '持有':
            continue
        # 拉实时价
        price, pct, _, _ = get_live_price(pos['code'])
        if price <= 0:
            price = pos['buy_price']  # 拿不到价就用买入价
        cur_pct = (price - pos['buy_price']) / pos['buy_price'] * 100
        pos = sell_position(pos, price, today, reason, cur_pct)
        signals.append(('清仓', pos.copy()))
    save_positions(positions)
    if signals:
        print(f'🔄 尾盘清仓: {len(signals)}笔持仓已卖出', flush=True)
        for s in signals:
            p = s[1]
            print(f'  {p["name"]}({p["code"]}) {p["buy_price"]:.2f}→{p["sell_price"]:.2f} {p["return_pct"]:+.1f}%', flush=True)
    return signals

def check_positions():
    """检查所有持仓，返回触发的信号"""
    positions = load_positions()
    signals = []
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_hour = now.hour
    trail_activate = get_version_trail_activate()

    for pos in positions:
        if pos['status'] != '持有':
            continue

        buy_date = pos['buy_date']
        buy_price = pos['buy_price']
        
        # 买入当天不监控卖出
        if buy_date == today:
            continue

        # 计算持有天数
        buy_dt = datetime.strptime(buy_date, '%Y-%m-%d')
        hold_days = (now - buy_dt).days

        if hold_days == 0:
            continue

        # 拉实时价（含当日最高最低）
        price, pct, today_high, today_low = get_live_price(pos['code'])
        if price <= 0:
            continue

        cur_pct = (price - buy_price) / buy_price * 100

        # 更新最高/最低价（使用真实的当日最高最低）
        if today_high > 0:
            pos['high_seen'] = max(pos['high_seen'], today_high)
        else:
            pos['high_seen'] = max(pos['high_seen'], price)
        if today_low > 0:
            pos['low_seen'] = min(pos['low_seen'], today_low)
        else:
            pos['low_seen'] = min(pos['low_seen'], price)

        trail_activated = pos.get('trailing_activated', False)

        # === 阶段1: 没到激活线 ===
        if not trail_activated:
            # 到位！直接止盈 + 激活回望
            if cur_pct >= trail_activate:
                pos['trailing_activated'] = True
                pos['trailing_peak'] = price
                pos['sell_price'] = round(price, 2)
                pos['sell_date'] = today
                pos['return_pct'] = round(cur_pct, 1)
                pos['sell_reason'] = f'止盈+{trail_activate}%'
                sell_position(pos, price, today, f'止盈+{trail_activate}%', cur_pct)
                signals.append(('止盈', pos.copy()))
                continue
            
            # -7%硬止损
            if cur_pct <= -7.0:
                pos = sell_position(pos, price, today, '止损', cur_pct)
                signals.append(('止损', pos.copy()))
                continue

        # === 阶段2: 回望已激活,让利润奔跑 ===
        else:
            if price > pos['trailing_peak']:
                pos['trailing_peak'] = price

            # 从最高回落0.3%卖出
            drop_from_peak = (pos['trailing_peak'] - price) / pos['trailing_peak'] * 100
            if drop_from_peak >= pos.get('trailing_drop', 0.3):
                pos = sell_position(pos, price, today, f'回望-0.3%', cur_pct)
                signals.append(('止盈(回望)', pos.copy()))
                continue

            # -7%止损也检查
            if cur_pct <= -7.0:
                pos = sell_position(pos, price, today, '止损', cur_pct)
                signals.append(('止损', pos.copy()))
                continue

        # 阶段3: 持有超1天且接近收盘，强制平仓
        if pos['status'] == '持有' and hold_days >= 1 and current_hour >= 14 and now.minute >= 50:
            pos = sell_position(pos, price, today, '收盘清仓', cur_pct)
            signals.append(('收盘清仓', pos.copy()))

    save_positions(positions)
    return signals

def log_trade(pos, action):
    """记录已完成的交易到日志"""
    log = load_log()
    trade = {
        'code': pos['code'],
        'name': pos['name'],
        'shares': pos.get('shares', 0),
        'cost': pos.get('cost', 0),
        'buy_date': pos['buy_date'],
        'buy_time': pos.get('buy_time', ''),
        'buy_price': pos['buy_price'],
        'sell_date': pos.get('sell_date'),
        'sell_time': pos.get('sell_time', ''),
        'sell_price': pos.get('sell_price', 0),
        'return_pct': pos.get('return_pct', 0),
        'return_amount': round((pos.get('sell_price', 0) - pos['buy_price']) * pos.get('shares', 100), 2) if pos.get('sell_price', 0) > 0 else 0,
        'action': action,
        'market_type': pos.get('market_type', ''),
        'high_seen': round(pos.get('high_seen', pos['buy_price']), 2),
        'low_seen': round(pos.get('low_seen', pos['buy_price']), 2),
    }
    log.append(trade)
    save_log(log)

def get_summary():
    """获取摘要统计"""
    log = load_log()
    if not log:
        return {'total': 0, 'wins': 0, 'win_rate': 0, 'total_pnl': 0,
                'total_return': 0, 'avg_return': 0}
    
    total = len(log)
    wins = [t for t in log if t['return_pct'] >= 0]
    total_pnl = sum(t.get('return_amount', 0) for t in log)
    total_ret = sum(t['return_pct'] for t in log)
    avg_ret = total_ret / total if total > 0 else 0
    
    return {
        'total': total,
        'wins': len(wins),
        'win_rate': round(len(wins)/total*100, 1) if total > 0 else 0,
        'total_pnl': round(total_pnl, 2),
        'total_return': round(total_ret, 1),
        'avg_return': round(avg_ret, 1),
    }

def generate_html():
    """生成HTML看板"""
    log = load_log()
    positions = load_positions()
    summary = get_summary()
    acct, market_val, total_assets = get_account_summary()
    
    # 自动识别版本
    dir_name = os.path.basename(DIR)
    ver_name = 'CG18' if 'CG18' in dir_name else ('1210CG01' if '1210' in dir_name else dir_name)
    
    total_pnl = total_assets - acct['initial_capital']
    total_ret_pct = total_pnl / acct['initial_capital'] * 100 if acct['initial_capital'] > 0 else 0
    
    pnl_color = '#ff4757' if total_ret_pct >= 0 else '#7bed9f'
    pnl_sign = '+' if total_ret_pct >= 0 else ''

    # 构建持仓行
    active_positions = [p for p in positions if p['status'] == '持有']
    pos_rows = ''
    for p in active_positions:
        shares = p.get('shares', 0)
        cost = p.get('cost', 0)
        buy_price = p['buy_price']
        trail_act = p.get('trail_activate', 2.5)
        act_price = buy_price * (1 + trail_act/100)
        # 实时价
        price, cur_pct, _, _ = get_live_price(p['code'])
        if price <= 0:
            price_str = '<span style="color:#666">待更新</span>'
            cur_str = '<span style="color:#666">--</span>'
        else:
            color = '#ff4757' if cur_pct >= 0 else '#7bed9f'
            price_str = f'{price:.2f}'
            cur_str = f'<span style="color:{color}">{cur_pct:+.2f}%</span>'
        pos_rows += f'''<tr>
<td>{p['code']}</td>
<td>{p['name']}</td>
<td style="text-align:right">{shares}</td>
<td style="text-align:right">{cost:,.0f}</td>
<td style="text-align:right">{buy_price:.2f}</td>
<td style="text-align:right;color:#ffa502">{act_price:.2f}</td>
<td style="text-align:right;color:#1a73e8">回落0.3%</td>
<td style="text-align:right">{price_str}</td>
<td style="text-align:right">{cur_str}</td>
</tr>'''
    
    if not active_positions:
        pos_rows = '<tr><td colspan="9" style="text-align:center;color:#555;padding:30px">📭 当前无持仓</td></tr>'
    
    # 构建交易记录行
    trade_rows = ''
    for t in reversed(log[-100:]):
        ret = t['return_pct']
        pnl = t.get('return_amount', 0)
        if ret >= 2.5:
            cls = 'win'
            tag = '<span class="tag tag-win">✅ 止盈</span>'
        elif ret >= 0:
            cls = 'neutral'
            tag = '<span class="tag tag-win">⏸️ 微利</span>'
        else:
            cls = 'loss'
            tag = '<span class="tag tag-loss">❌ 亏损</span>'
        ret_color = '#ff4757' if ret >= 0 else '#7bed9f'
        pnl_color_row = '#ff4757' if pnl >= 0 else '#7bed9f'
        trade_rows += f'''<tr>
<td style="color:#999">{t['buy_date']}</td>
<td>{t['name']}</td>
<td style="text-align:right">{t.get('shares','?')}</td>
<td style="text-align:right">{t['buy_price']:.2f}</td>
<td style="text-align:right">{t['sell_price']:.2f}</td>
<td style="text-align:right;color:{ret_color}">{ret:+.1f}%</td>
<td style="text-align:right;color:{pnl_color_row}">{pnl:+,.0f}</td>
<td style="text-align:center">{tag}</td>
</tr>'''
    
    if not trade_rows:
        trade_rows = '<tr><td colspan="8" style="text-align:center;color:#555;padding:30px">📭 暂无交易记录</td></tr>'
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ver_name} 模拟盘看板</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:linear-gradient(135deg,#f5f7fa 0%,#e4e8ef 100%);color:#2c3e50;font-family:-apple-system,'Microsoft YaHei',Arial,sans-serif;padding:24px;max-width:1200px;margin:auto;min-height:100vh}}
h1{{font-size:26px;margin-bottom:4px;display:flex;align-items:center;gap:12px}}
h1 .ver{{background:#e8ecf1;color:#1a73e8;font-size:13px;padding:4px 12px;border-radius:20px;font-weight:normal}}
.subtitle{{color:#889;font-size:13px;margin-bottom:24px}}
.stats-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px}}
@media(max-width:768px){{.stats-grid{{grid-template-columns:repeat(2,1fr)}}}}
.stat-card{{background:#fff;padding:16px;border-radius:12px;border:1px solid #e0e4ea;position:relative;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.05)}}
.stat-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.stat-card.pnl-up::before{{background:linear-gradient(90deg,#ff4757,#ff6b81)}}
.stat-card.pnl-down::before{{background:linear-gradient(90deg,#7bed9f,#2ed573)}}
.stat-card.neutral::before{{background:linear-gradient(90deg,#1a73e8,#4fc3f7)}}
.stat-card .num{{font-size:28px;font-weight:700;margin-top:4px}}
.stat-card .num.up{{color:#ff4757}}
.stat-card .num.down{{color:#7bed9f}}
.stat-card .label{{font-size:11px;color:#889;letter-spacing:0.5px;text-transform:uppercase}}
.stat-card .sub-num{{font-size:12px;color:#aaa;margin-top:2px}}
.section-title{{font-size:14px;color:#666;margin:24px 0 12px;display:flex;align-items:center;gap:8px}}
.section-title::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,#ddd,transparent)}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #e0e4ea;box-shadow:0 1px 3px rgba(0,0,0,0.04)}}
th{{background:#f0f2f5;color:#555;padding:10px 12px;font-size:12px;font-weight:600;text-align:left;white-space:nowrap;letter-spacing:0.5px;border-bottom:2px solid #ddd}}
td{{padding:9px 12px;border-top:1px solid #eee;font-size:13px}}
tr:hover td{{background:#f8f9fb}}
.win{{color:#ff4757}}
.loss{{color:#7bed9f}}
.neutral{{color:#ffa502}}
.tag{{display:inline-block;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.tag-win{{background:#ff475718;color:#d63031}}
.tag-loss{{background:#7bed9f18;color:#00b894}}
.tag-hold{{background:#1a73e818;color:#1a73e8}}
.pnl-bar{{display:inline-block;height:6px;border-radius:3px;margin-right:6px;vertical-align:middle}}
.footer{{text-align:center;color:#999;font-size:11px;margin-top:30px;padding:20px;border-top:1px solid #e0e4ea}}
</style></head>
<body>

<h1>📊 {ver_name} 模拟盘 <span class="ver">本金{acct['initial_capital']:.0f}元</span></h1>
<p class="subtitle">生成: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 策略: 尾盘买入 → 冲到{get_version_trail_activate():.0f}%止盈 / 回望-0.3% / -7%止损 / 收盘清仓</p>

<div class="stats-grid">
<div class="stat-card neutral"><div class="label">总交易</div><div class="num">{summary['total']}</div></div>
<div class="stat-card pnl-up"{" class='stat-card pnl-down'" if summary['win_rate']<50 else ""}><div class="label">胜率</div><div class="num {"up" if summary['win_rate']>=50 else "down"}">{summary['win_rate']}%</div></div>
<div class="stat-card {"pnl-up" if total_ret_pct>=0 else "pnl-down"}"><div class="label">总收益率</div><div class="num {"up" if total_ret_pct>=0 else "down"}">{pnl_sign}{total_ret_pct:.1f}%</div><div class="sub-num">{total_pnl:+,.0f}元</div></div>
<div class="stat-card neutral"><div class="label">总资产</div><div class="num">{total_assets:,.0f}</div><div class="sub-num">现金{acct['available_cash']:,.0f} + 市值{market_val:,.0f}</div></div>
<div class="stat-card {"pnl-up" if summary.get('avg_return',0)>=0 else "pnl-down"}"><div class="label">平均收益</div><div class="num {"up" if summary.get('avg_return',0)>=0 else "down"}">{summary.get('avg_return',0):+.1f}%</div></div>
</div>

<div class="section-title">📌 当前持仓 ({len(active_positions)}只)</div>
<table>
<thead><tr>
<th>代码</th><th>名称</th><th style="text-align:right">股数</th><th style="text-align:right">成本</th><th style="text-align:right">买入价</th><th style="text-align:right">回望激活</th><th style="text-align:right">回落卖</th><th style="text-align:right">现价</th><th style="text-align:right">实时涨幅</th>
</tr></thead>
<tbody>
{pos_rows}
</tbody>
</table>

<div class="section-title">📋 历史交易记录</div>
<table>
<thead><tr>
<th>日期</th><th>名称</th><th style="text-align:right">股数</th><th style="text-align:right">买入价</th><th style="text-align:right">卖出价</th><th style="text-align:right">收益率</th><th style="text-align:right">盈亏</th><th style="text-align:center">操作</th>
</tr></thead>
<tbody>
{trade_rows}
</tbody>
</table>

<div class="footer">{ver_name} 模拟盘交易系统 · 数据自动更新</div>
</body></html>'''
    
    out_path = os.path.join(os.path.expanduser('~/Desktop'), f'{ver_name}_模拟盘看板.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path

if __name__ == '__main__':
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else ''

    if action == 'check':
        signals = check_positions()
        if signals:
            for sig_type, pos in signals:
                print(f'📊 模拟盘信号: {sig_type} {pos["name"]}({pos["code"]}) '
                      f'买入{pos["buy_price"]:.2f} 卖出{pos["sell_price"]:.2f} '
                      f'收益{pos["return_pct"]:+.1f}%')
        generate_html()
        # 打印账户摘要
        acct, mv, ta = get_account_summary()
        print(f'\n💰 账户: 总资产{ta:.0f}元 | 现金{acct["available_cash"]:.0f}元 | 市值{mv:.0f}元 | 总盈亏{acct["total_pnl"]:+.0f}元 ({acct["total_return_pct"]:+.1f}%)')
        print(f'\n💾 看板: {os.path.join(os.path.expanduser("~/Desktop"), "CG18_模拟盘看板.html")}')

    elif action == 'dashboard':
        path = generate_html()
        print(f'💾 看板已更新: {path}')

    elif action == 'add':
        code = sys.argv[2]; name = sys.argv[3]; price = float(sys.argv[4])
        pct = float(sys.argv[5]) if len(sys.argv) > 5 else 0
        market = sys.argv[6] if len(sys.argv) > 6 else ''
        pos = add_position(code, name, price, buy_pct=pct, market_type=market)
        if pos:
            acct, mv, ta = get_account_summary()
            print(f'  持仓: {pos["shares"]}股 @ {pos["buy_price"]:.2f} = {pos["cost"]:.2f}元')
            ta = get_version_trail_activate()
            trail_drop = pos.get('trailing_drop', 0.3)
            print(f'  回望: 冲到+{ta}%止盈 回落{trail_drop}%卖')
            print(f'  余额: {acct["available_cash"]:.2f}元')

    elif action == 'summary':
        s = get_summary()
        if isinstance(s, str):
            print(s)
        else:
            acct, mv, ta = get_account_summary()
            print(f'📊 CG18模拟盘统计')
            print(f'  本金: {acct["initial_capital"]:.0f}元')
            print(f'  总资产: {ta:.0f}元 (现金{acct["available_cash"]:.0f} + 市值{mv:.0f})')
            print(f'  总盈亏: {acct["total_pnl"]:+.0f}元 ({acct["total_return_pct"]:+.1f}%)')
            print(f'  交易: {s["total"]}笔 | 胜率{s["win_rate"]}% | 均收益{s["avg_return"]:+.1f}%')

    elif action == 'account':
        acct, mv, ta = get_account_summary()
        print(f'💰 CG18模拟盘账户')
        print(f'  初始本金: {acct["initial_capital"]:.2f}元')
        print(f'  可用现金: {acct["available_cash"]:.2f}元')
        print(f'  持仓市值: {mv:.2f}元')
        print(f'  总资产: {ta:.2f}元')
        print(f'  累计盈亏: {acct["total_pnl"]:+.2f}元 ({acct["total_return_pct"]:+.1f}%)')

    elif action == 'init':
        init_account()
        print(f'✅ 账户已初始化: 本金{INITIAL_CAPITAL:.0f}元')
