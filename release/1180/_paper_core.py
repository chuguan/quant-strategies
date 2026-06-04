#!/usr/bin/env python3
"""
1180 模拟盘核心 — 持仓管理 + 监控 + 通知
"""
import json, os, time, subprocess
from datetime import datetime, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
POS_FILE = os.path.join(DIR, '_positions.json')
LOG_FILE = os.path.join(DIR, '_trade_log.json')
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')

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
    """添加一笔模拟买入"""
    if buy_date is None:
        buy_date = datetime.now().strftime('%Y-%m-%d')
    positions = load_positions()
    # 检查是否已有同一天同一只
    for p in positions:
        if p['code'] == code and p['buy_date'] == buy_date and p['status'] == '持有':
            return p  # 已存在
    
    pos = {
        'code': code,
        'name': name,
        'buy_price': round(buy_price, 2),
        'buy_date': buy_date,
        'buy_time': datetime.now().strftime('%H:%M'),
        'buy_pct': round(buy_pct, 1),
        'target_price': round(buy_price * 1.03, 2),  # +3%激活回望
        'stop_price': round(buy_price * 0.97, 2),    # -3%硬止损(防暴跌)
        'status': '持有',
        'high_seen': round(buy_price, 2),
        'low_seen': round(buy_price, 2),
        'sell_date': None,
        'sell_price': 0,
        'return_pct': 0,
        'sell_reason': '',
        'market_type': market_type,
        # 回望卖出参数
        'trailing_activated': False,   # +3%已到达,回望已激活
        'trailing_peak': round(buy_price, 2),  # 激活后的最高价
        'trailing_drop': 0.3,  # 回落0.3%触发卖出
    }
    positions.append(pos)
    save_positions(positions)
    return pos

def get_live_price(code):
    """从腾讯API获取实时价"""
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
                return price, pct
    except:
        pass
    return 0, 0

def check_positions():
    """检查所有持仓，返回触发的信号"""
    positions = load_positions()
    signals = []
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_hour = now.hour
    
    for pos in positions:
        if pos['status'] != '持有':
            continue
        
        buy_date = pos['buy_date']
        buy_price = pos['buy_price']
        trail_drop = pos.get('trailing_drop', 0.3)
        trail_activated = pos.get('trailing_activated', False)
        
        # 买入当天不监控卖出
        if buy_date == today:
            continue
        
        # 计算持有天数
        buy_dt = datetime.strptime(buy_date, '%Y-%m-%d')
        hold_days = (now - buy_dt).days
        
        # 如果是同一天买入(今天14:53买),不监控
        if hold_days == 0:
            continue
        
        # 拉实时价
        price, pct = get_live_price(pos['code'])
        if price <= 0:
            continue
        
        cur_pct = (price - buy_price) / buy_price * 100
        
        # 更新最高/最低价
        pos['high_seen'] = max(pos['high_seen'], price)
        pos['low_seen'] = min(pos['low_seen'], price)
        
        # === 回望卖出逻辑 ===
        
        # 阶段1: 还没到+3%
        if not trail_activated:
            # 检查硬止损
            if cur_pct <= -3.0:
                pos['status'] = '已卖出'
                pos['sell_price'] = round(price, 2)
                pos['sell_date'] = today
                pos['return_pct'] = round(cur_pct, 1)
                pos['sell_reason'] = '-3%止损'
                signals.append(('止损', pos.copy()))
                log_trade(pos, '止损')
                
            # 到+3%了!激活回望
            elif cur_pct >= 3.0:
                pos['trailing_activated'] = True
                pos['trailing_peak'] = price
                signals.append(('回望激活', pos.copy()))
                
        # 阶段2: 回望已激活,追踪最高价
        else:
            # 更新最高价
            if price > pos['trailing_peak']:
                pos['trailing_peak'] = price
            
            # 从最高点回落0.3%
            drop_from_peak = (pos['trailing_peak'] - price) / pos['trailing_peak'] * 100
            if drop_from_peak >= trail_drop:
                pos['status'] = '已卖出'
                pos['sell_price'] = round(price, 2)
                pos['sell_date'] = today
                ret = (price - buy_price) / buy_price * 100
                pos['return_pct'] = round(ret, 1)
                pos['sell_reason'] = f'回望-{trail_drop}%'
                signals.append(('止盈', pos.copy()))
                log_trade(pos, '止盈')
        
        # 阶段3: 持有超1天且接近收盘,强制平仓
        if pos['status'] == '持有' and hold_days >= 1 and current_hour >= 14 and minute >= 50:
            pos['status'] = '已卖出'
            pos['sell_price'] = round(price, 2)
            pos['sell_date'] = today
            ret = (price - buy_price) / buy_price * 100
            pos['return_pct'] = round(ret, 1)
            pos['sell_reason'] = '收盘清仓'
            signals.append(('收盘清仓', pos.copy()))
            log_trade(pos, '收盘清仓')
    
    save_positions(positions)
    return signals

def log_trade(pos, action):
    """记录已完成的交易到日志"""
    log = load_log()
    trade = {
        'code': pos['code'],
        'name': pos['name'],
        'buy_date': pos['buy_date'],
        'buy_price': pos['buy_price'],
        'sell_date': pos['sell_date'],
        'sell_price': pos['sell_price'],
        'return_pct': pos['return_pct'],
        'action': action,
        'market_type': pos.get('market_type', ''),
        'high_seen': round(pos['high_seen'], 2),
        'low_seen': round(pos['low_seen'], 2),
    }
    log.append(trade)
    save_log(log)

def get_summary():
    """获取摘要统计"""
    log = load_log()
    if not log:
        return "暂无交易记录"
    
    total = len(log)
    wins = [t for t in log if t['return_pct'] >= 2.5]
    stop_loss = [t for t in log if t['return_pct'] <= -5]
    total_ret = sum(t['return_pct'] for t in log)
    avg_ret = total_ret / total
    
    return {
        'total': total,
        'wins': len(wins),
        'win_rate': round(len(wins)/total*100, 1),
        'stop_loss': len(stop_loss),
        'avg_return': round(avg_ret, 1),
        'total_return': round(total_ret, 1),
    }

def generate_html():
    """生成HTML看板"""
    log = load_log()
    positions = load_positions()
    summary = get_summary()
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>1180 模拟盘交易看板</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f1923;color:#e0e0e0;font-family:'Microsoft YaHei',Arial;padding:20px;max-width:1200px;margin:auto}}
h1{{color:#00d4aa;font-size:24px;margin-bottom:20px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}}
.stat-card{{background:#1a2a3a;padding:14px;border-radius:8px}}
.stat-card .num{{font-size:28px;font-weight:bold;color:#00d4aa}}
.stat-card .label{{font-size:12px;color:#888}}
table{{width:100%;border-collapse:collapse;background:#1a2a3a;border-radius:8px;overflow:hidden}}
th{{background:#0d2137;color:#00d4aa;padding:10px 8px;font-size:13px;text-align:left}}
td{{padding:8px;border-top:1px solid #253544;font-size:13px}}
.win{{color:#ff4757}}
.loss{{color:#7bed9f}}
.neutral{{color:#ffa502}}
.hold{{color:#00d4aa}}
.tag{{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px}}
.tag-win{{background:#ff475722;color:#ff4757}}
.tag-loss{{background:#7bed9f22;color:#7bed9f}}
.tag-hold{{background:#00d4aa22;color:#00d4aa}}
.section-title{{color:#888;font-size:13px;margin:20px 0 10px;text-transform:uppercase;letter-spacing:1px}}
</style></head>
<body>
<h1>📊 1180 模拟盘交易看板</h1>
<p style="color:#666;font-size:12px;margin-bottom:20px">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 策略: 尾盘买入→+5%止盈/-7%止损/3天平仓</p>

<div class="stats">
<div class="stat-card"><div class="num">{summary['total']}</div><div class="label">总交易</div></div>
<div class="stat-card"><div class="num" style="color:#ff4757">{summary['win_rate']}%</div><div class="label">胜率</div></div>
<div class="stat-card"><div class="num">+{summary['avg_return']}%</div><div class="label">平均收益</div></div>
<div class="stat-card"><div class="num">{summary['total_return']}%</div><div class="label">累计收益</div></div>
<div class="stat-card"><div class="num">{summary['stop_loss']}</div><div class="label">止损数</div></div>
</div>

<div class="section-title">📌 当前持仓 ({len([p for p in positions if p['status']=='持有'])}只)</div>
<table>
<tr><th>代码</th><th>名称</th><th>买入日期</th><th>买入价</th><th>目标价</th><th>止损价</th><th>买入涨幅</th><th>状态</th></tr>'''
    
    for p in positions:
        if p['status'] != '持有': continue
        html += f'''<tr>
<td>{p['code']}</td><td>{p['name']}</td><td>{p['buy_date']}</td>
<td>{p['buy_price']:.2f}</td><td style="color:#ff4757">{p['target_price']:.2f}</td>
<td style="color:#7bed9f">{p['stop_price']:.2f}</td>
<td>{p.get('buy_pct',0):+.1f}%</td>
<td><span class="tag tag-hold">持有中</span></td></tr>'''
    
    html += '''</table>
<div class="section-title">📋 历史交易记录</div>
<table><tr><th>日期</th><th>名称</th><th>买入价</th><th>卖出价</th><th>收益率</th><th>操作</th><th>最高</th><th>最低</th></tr>'''
    
    for t in reversed(log[-50:]):
        cls = 'win' if t['return_pct'] >= 2.5 else ('loss' if t['return_pct'] <= -2 else 'neutral')
        tag = f'<span class="tag tag-win">{t["action"]}</span>' if t['return_pct']>=2.5 else f'<span class="tag tag-loss">{t["action"]}</span>'
        html += f'''<tr>
<td>{t['buy_date']}</td><td>{t['name']}</td><td>{t['buy_price']:.2f}</td>
<td>{t['sell_price']:.2f}</td><td class="{cls}">{t['return_pct']:+.1f}%</td>
<td>{tag}</td><td>{t.get('high_seen',0):.2f}</td><td>{t.get('low_seen',0):.2f}</td></tr>'''
    
    html += '</table></body></html>'
    
    out_path = os.path.join(os.path.expanduser('~/Desktop'), '1180_模拟盘看板.html')
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
                # 也写入微信通知
                send_to = '1254628314@qq.com'  # 主邮箱
                from send_email import send_email
                msg = f'【模拟盘{sig_type}】{pos["name"]}({pos["code"]})\n买入价: {pos["buy_price"]:.2f}\n卖出价: {pos["sell_price"]:.2f}\n收益率: {pos["return_pct"]:+.1f}%\n买入日期: {pos["buy_date"]}'
                
        generate_html()
        print(f'\n💾 看板: {os.path.join(os.path.expanduser("~/Desktop"), "1180_模拟盘看板.html")}')
        
    elif action == 'dashboard':
        path = generate_html()
        print(f'💾 看板已更新: {path}')
        
    elif action == 'add':
        # python _paper_core.py add <code> <name> <price> [pct] [market]
        code = sys.argv[2]; name = sys.argv[3]; price = float(sys.argv[4])
        pct = float(sys.argv[5]) if len(sys.argv) > 5 else 0
        market = sys.argv[6] if len(sys.argv) > 6 else ''
        pos = add_position(code, name, price, buy_pct=pct, market_type=market)
        print(f'✅ 模拟买入: {name}({code}) {price:.2f}元 涨幅{pct:+.1f}%')
        print(f'   止盈价: {pos["target_price"]:.2f} (+5%)')
        print(f'   止损价: {pos["stop_price"]:.2f} (-7%)')
        
    elif action == 'summary':
        s = get_summary()
        if isinstance(s, str):
            print(s)
        else:
            print(f'📊 模拟盘统计: {s["total"]}笔 胜{s["win_rate"]}% 均{s["avg_return"]:+.1f}% 累计{s["total_return"]:+.1f}%')
