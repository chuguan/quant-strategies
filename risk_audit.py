#!/usr/bin/env python
"""风险管控与质量管控 — 全流程扫描"""
import sqlite3, os

db = os.path.expanduser('~/AppData/Local/hermes/scripts/v13_quant.db')
conn = sqlite3.connect(db)
c = conn.cursor()

print('=' * 75)
print('  🔍 风险管控与质量管控 — 全流程扫描')
print('=' * 75)

risks = [
    # ===== 数据采集层 =====
    {
        'layer': '数据采集',
        'risk': '新浪/腾讯API请求失败',
        'impact': '当天选股缺数据，冠军可能选错或没票',
        'mitigation': '① 自动重试3次 ② 降级到其他数据源 ③ 记录失败率到config表',
        'priority': 'P0-致命'
    },
    {
        'layer': '数据采集',
        'risk': 'API返回值格式变了（新浪改字段名）',
        'impact': '解析失败，生产脚本跑不出结果',
        'mitigation': '① 数据格式校验（断言字段存在）② 解析失败时告警邮件',
        'priority': 'P0-致命'
    },
    {
        'layer': '数据采集',
        'risk': '部分股票API没返回数据（漏股）',
        'impact': '候选池少了优质股，冠军可能不是真正的第一名',
        'mitigation': '① 记录每批次的获取成功率 ② 成功率<95%告警',
        'priority': 'P1-严重'
    },
    {
        'layer': '数据采集',
        'risk': '同一数据源，不同时间拉取数据不一致',
        'impact': '2:50和2:51拉的同只股票p值不同',
        'mitigation': '① 固定2:50一次性拉完 ② 拉完立刻锁存，不走增量',
        'priority': 'P1-严重'
    },

    # ===== 数据库层 =====
    {
        'layer': '数据库',
        'risk': 'v13_quant.db 文件损坏或丢失',
        'impact': '所有配置、选股记录、策略文件、归档全丢',
        'mitigation': '① 每日自动备份到 backup/ ② 备份保留30天 ③ JSON日志作为二次保险',
        'priority': 'P0-致命'
    },
    {
        'layer': '数据库',
        'risk': 'SQLite并发写入冲突（选股+回测同时写）',
        'impact': '数据库锁死，写入失败',
        'mitigation': '① 启用WAL模式（读写不互斥）② 生产写入独占时间段 ③ 查询用只读连接',
        'priority': 'P2-中'
    },
    {
        'layer': '数据库',
        'risk': '数据量越来越大（每天3000股×1年=75万行）',
        'impact': '查询变慢，回测越来越卡',
        'mitigation': '① 按年分区表 data_cache_2025 / data_cache_2026 ② 旧数据归档 ③ 索引优化',
        'priority': 'P2-中'
    },
    {
        'layer': '数据库',
        'risk': '误操作删除数据（手误DROP/DELETE）',
        'impact': '数据不可恢复',
        'mitigation': '① 只能通过专用工具操作数据库 ② SELECT权限开放，写权限限制 ③ 每日备份',
        'priority': 'P1-严重'
    },

    # ===== 策略层 =====
    {
        'layer': '策略',
        'risk': '30天胜率100%但下一个月可能掉到60%（过拟合）',
        'impact': '实盘连续亏钱',
        'mitigation': '① 每月自动计算滚动胜率 ② 胜率低于阈值(70%)自动告警 ③ 新版本必须在30天+全年都验证通过才能上线',
        'priority': 'P0-致命'
    },
    {
        'layer': '策略',
        'risk': '生产用的评分策略和归档的不一致',
        'impact': '回测结果和生产结果对不上',
        'mitigation': '① 每次定版时strategy_files + strategy_snapshot写入DB ② 运行时对比文件hash与DB ③ 不一致拒绝运行',
        'priority': 'P0-致命'
    },
    {
        'layer': '策略',
        'risk': '开发环境改参数后不小心覆盖了生产参数',
        'impact': '生产跑了错误的参数',
        'mitigation': '① env=production/dev强行隔离 ② 生产脚本启动时检查HERMES_ENV不为dev ③ dev环境不连生产DB',
        'priority': 'P0-致命'
    },

    # ===== 定时任务层 =====
    {
        'layer': '定时任务',
        'risk': '交易日14:50服务器关机/断网',
        'impact': '当天没选股，错过机会',
        'mitigation': '① 15:00再补跑一次（如果miss了14:50）② 下午收盘后补发告警 ③ 第二天开盘前如果有缺口补选',
        'priority': 'P1-严重'
    },
    {
        'layer': '定时任务',
        'risk': '节假日的判断错误（休市日跑了选股）',
        'impact': '选股结果无效，浪费资源',
        'mitigation': '① 交易日历离线文件 ② 读取A股交易日API ③ 非交易日自动跳过',
        'priority': 'P2-中'
    },
    {
        'layer': '定时任务',
        'risk': '定时任务本身挂了没启动',
        'impact': '没跑没告警，用户不知道',
        'mitigation': '① 每日健康检查（检查昨天是否有选股记录）② 无记录则告警邮件',
        'priority': 'P1-严重'
    },

    # ===== 实战与回测差异 =====
    {
        'layer': '实盘',
        'risk': '2:50买入价和收盘价偏差>1%（非平均的0.375%）',
        'impact': '回测达标实盘不达标',
        'mitigation': '① 逐日统计2:50价vs收盘价偏差 ② 偏差>1%标记为高风险日 ③ 按偏离度调整实战预期',
        'priority': 'P1-严重'
    },
    {
        'layer': '实盘',
        'risk': '买入时价格跳动（从2:50出结果到实际下单差几秒）',
        'impact': '买在了比结果更高的价格',
        'mitigation': '① 使用限价单（不高于结果价+0.5%）② 记录实际成交价 ③ 持续监控滑点',
        'priority': 'P2-中'
    },
    {
        'layer': '实盘',
        'risk': '次日最高没达到2.5%，但收盘是涨的',
        'impact': '虽然胜率不达标，但其实不亏钱',
        'mitigation': '① 同时追踪3个指标：达标率(≥2.5%)、胜率(>0%)、平均收益 ② 综合评估',
        'priority': 'P2-中'
    },

    # ===== 版本发布 =====
    {
        'layer': '发布',
        'risk': 'V14发布了，但V13还在生产跑，V14的结果和V13混在一起',
        'impact': '同一天的selection_pool里V13和V14冠军不一样，用户看哪个？',
        'mitigation': '① config.active_version指定当前生产版本 ② 查询时默认只查active_version ③ 需要对比时手动指定',
        'priority': 'P1-严重'
    },
    {
        'layer': '发布',
        'risk': 'V14回测胜率比V13高，但实盘反而差了',
        'impact': '新版本上线后实战表现不如预期',
        'mitigation': '① V14先在dev环境跑1周 ② 对比dev结果和生产V13结果 ③ 确认实盘偏差在可接受范围内再切换',
        'priority': 'P1-严重'
    },
]

# 展示
current_layer = ''
for item in sorted(risks, key=lambda x: (x['priority'], x['layer'])):
    if item['layer'] != current_layer:
        print(f'\n{"-"*75}')
        print(f'  📌 {item["layer"]}')
        print(f'{"-"*75}')
        current_layer = item['layer']
    
    print(f'\n  [{item["priority"]}] {item["risk"]}')
    print(f'     影响: {item["impact"]}')
    print(f'     应对: {item["mitigation"]}')

# 统计
print(f'\n{"="*75}')
print(f'  📊 风险统计')
print(f'{"="*75}')
by_priority = {}
for item in risks:
    p = item['priority']
    by_priority[p] = by_priority.get(p, 0) + 1
for p in sorted(by_priority.keys(), reverse=True):
    print(f'  {p}: {by_priority[p]} 项')
print(f'  总计: {len(risks)} 项风险')

conn.close()
