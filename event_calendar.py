#!/usr/bin/env python3
"""
未来5天重大事件前瞻
从akshare获取经济数据+已知重大事件
"""
import akshare as ak
from datetime import datetime, timedelta
import json

def get_next_5_trading_days():
    """获取未来5个交易日"""
    today = datetime.now()
    days = []
    d = today
    while len(days) < 5:
        d += timedelta(days=1)
        if d.weekday() < 5:  # 周一至周五
            days.append(d)
    return days

def get_us_nonfarm_dates():
    """获取今年非农发布日期（通常是每月第一个周五）"""
    # 从数据中提取最新非农发布日期
    try:
        df = ak.macro_usa_non_farm()
        latest = df['日期'].iloc[-1]
        return str(latest)[:10]
    except:
        return None

def get_china_pmi_dates():
    """获取中国PMI最新数据（每月最后一天或次月第一天发布）"""
    try:
        df = ak.macro_china_pmi()
        return df['月份'].iloc[0]
    except:
        return None

def get_china_cpi_dates():
    """获取中国CPI数据（每月9号左右发布）"""
    try:
        df = ak.macro_china_cpi_yearly()
        latest = df['日期'].iloc[-1]
        return str(latest)[:10]
    except:
        return None

def build_calendar():
    """构建未来5天事件日历"""
    today = datetime.now()
    next_days = get_next_5_trading_days()
    
    calendar = []
    
    for d in next_days:
        date_str = d.strftime('%Y-%m-%d')
        weekday = d.strftime('%A')
        day_num = d.day
        month_num = d.month
        
        events = []
        
        # === 规律性事件（按日期/星期自动计算）===
        
        # 美国非农：每月第一个周五
        if d.weekday() == 4 and day_num <= 7:  # 周五且日期<=7（第一个周五）
            events.append({
                'event': '🇺🇸 美国5月非农就业数据',
                'impact': '⚠️ 重大',
                'detail': '市场预期就业人数变化，若超预期→加息预期升温，利空成长股',
                'direction': '利空成长股' if day_num <= 7 else '中性'
            })
        
        # 美国初请失业金：每周四
        if d.weekday() == 3:
            events.append({
                'event': '🇺🇸 美国初请失业金人数',
                'impact': '📊 中等',
                'detail': '每周四发布，反映就业市场状况',
                'direction': '依据数据判断'
            })
        
        # 美国ISM制造业PMI：每月1日
        if day_num == 1:
            events.append({
                'event': '🇺🇸 美国ISM制造业PMI',
                'impact': '⚠️ 重要',
                'detail': '反映制造业景气度，>50扩张，<50收缩',
                'direction': '利好/利空周期股'
            })
        
        # 美国ISM非制造业PMI：每月3日
        if day_num == 3:
            events.append({
                'event': '🇺🇸 美国ISM非制造业PMI',
                'impact': '📊 重要',
                'detail': '反映服务业景气度，占比经济~80%',
                'direction': '影响市场整体方向'
            })
        
        # 中国LPR：每月20日
        if day_num == 20:
            events.append({
                'event': '🇨🇳 中国LPR利率报价',
                'impact': '⚠️ 重要',
                'detail': '1年期/5年期LPR，降息则利好房地产+高负债企业',
                'direction': '若降息→利好地产+消费'
            })
        
        # 中国CPI：每月9日左右
        if 8 <= day_num <= 10:
            events.append({
                'event': '🇨🇳 中国CPI/PPI数据',
                'impact': '📊 中等',
                'detail': '通胀数据，影响货币政策预期',
                'direction': '若CPI过高→利空流动性'
            })
        
        # 美联储FOMC会议：1月/3月/5月/6月/7月/9月/11月/12月
        fomc_months = {1, 3, 5, 6, 7, 9, 11, 12}
        if month_num in fomc_months:
            # FOMC通常在月中下旬，具体日期需查
            if 15 <= day_num <= 20:
                events.append({
                    'event': '🇺🇸 美联储FOMC利率决议',
                    'impact': '⚠️⚠️ 极其重大',
                    'detail': '全球最关注的经济事件，决定利率走向',
                    'direction': '暂停加息→利好全球 加息→利空全球'
                })
        
        # === 已知具体事件（6月第1周）===
        # 这些基于当前市场资讯，需定时更新
        if date_str == '2026-06-02':
            events.append({
                'event': '🇺🇸 美国最高法院裁决：特朗普能否解雇美联储理事？',
                'impact': '⚠️⚠️ 极其重大',
                'detail': '若裁决支持解雇→美联储独立性受严重冲击→美元上涨→A股外资可能流出',
                'direction': '支持解雇→⚠️利空全球成长股'
            })
        
        if date_str == '2026-06-03':
            events.append({
                'event': '🇺🇸 博通AVGO + CrowdStrike CRWD 财报',
                'impact': '⚠️ 重要',
                'detail': '博通是AI网络芯片龙头，CrowdStrike是网安龙头。若超预期→提振AI+网安板块',
                'direction': '超预期→✅利好A股芯片+网安'
            })
        
        if date_str == '2026-06-04':
            events.append({
                'event': '🇺🇸 美国4月贸易帐数据',
                'impact': '📊 中等',
                'detail': '反映国际贸易状况，影响汇率和出口板块',
                'direction': '中性观察'
            })
        
        if date_str == '2026-06-05':
            events.append({
                'event': '🇺🇸 美国5月非农就业数据',
                'impact': '⚠️⚠️ 极其重大',
                'detail': '本周最重磅数据！决定6月美联储加息预期方向',
                'direction': '超预期→⚠️利空成长股；低于预期→✅利好成长股'
            })
        
        # 持续事件
        events.append({
            'event': '🌍 美伊60天停火协议谈判',
            'impact': '⚠️ 持续关注',
            'detail': '美伊双方在海峡小规模交火，协议尚未签署。签署则油价回落利好中下游',
            'direction': '签署→✅利好交运/化工'
        })
        
        if events:
            calendar.append({
                'date': d.strftime('%m/%d %a'),
                'date_obj': d,
                'events': events
            })
    
    return calendar

def format_calendar(calendar):
    """格式化日历输出"""
    lines = []
    lines.append('\n=== 📅 未来5天重大事件前瞻 ===')
    lines.append(f'{"="*60}')
    
    for day in calendar:
        date_label = day['date']
        today = datetime.now()
        
        # 标出今天
        if day['date_obj'].date() == today.date():
            date_label += ' ⬅️ 今天'
        
        lines.append(f'\n📆 {date_label}')
        lines.append(f'{"-"*50}')
        
        for ev in day['events']:
            imp = ev['impact']
            emoji_map = {
                '极其重大': '🔴🔴',
                '重大': '🔴',
                '重要': '🟡',
                '中等': '🟢',
                '持续关注': '🔵'
            }
            emoji = ''
            for k, v in emoji_map.items():
                if k in imp:
                    emoji = v
                    break
            
            lines.append(f'  {emoji} {ev["event"]}')
            lines.append(f'     重要性: {imp}')
            lines.append(f'     详情: {ev["detail"]}')
            lines.append(f'     预判: {ev["direction"]}')
            lines.append('')
    
    return '\n'.join(lines)

if __name__ == '__main__':
    calendar = build_calendar()
    print(format_calendar(calendar))
    
    # 输出JSON格式供其他脚本使用
    print('\n\n=== JSON格式（供程序调用）===')
    for day in calendar:
        for ev in day['events']:
            print(json.dumps({'date': day['date'], 'event': ev['event'], 
                            'impact': ev['impact'], 'direction': ev['direction']}, 
                           ensure_ascii=False))
