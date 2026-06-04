# V50 分而治之 — 全量独立归档

## 版本信息
- **版本**: V50
- **创建日期**: 2026-06-04
- **基版**: V42 (横盘混合评分+HSL否决) + V46新尾盘形态加分
- **胜率**: 30天80%/50天72%/100天72%

## 全量文件清单
```
release/V50/
├── V50_日报.py              ★ 主选股脚本（含实时+回测+邮件）
├── run_V50_daily.sh          ★ 定时运行（14:50）
├── pre_task_check.py         ★ 前置数据完整性检查
├── selection_log_db.py       ★ 选股日志写入数据库
├── send_email.py             ★ 邮件发送
├── 活跃股票池_3043.json      ★ 沪深主板3043只股票池
├── big_cache_full.pkl        ★ 回测缓存（含ma5_slope等全字段）
├── features_30d.pkl          ★ 特征缓存
├── VERSION.md                ★ 本文件
└── 评分策略/
    ├── 分而治之_V10_真实涨日_评分策略.py
    ├── 分而治之_V10_虚涨日_评分策略.py
    ├── 分而治之_V10_跌日_评分策略.py
    ├── 分而治之_V10_横盘_评分策略.py
    └── momentum_features.py
```

## 外部依赖（不包含在归档内，需要系统级存在）
- `~/AppData/Local/hermes/scripts/v13_quant.db` — 共享SQLite数据库（data_cache表用于VR值预加载、选股日志）
- `~/AppData/Local/hermes/hermes-agent/cache/` — 个股日K线JSON缓存（用于实时行情获取）
- Python标准库: sys, os, json, re, time, subprocess, datetime, pickle, importlib, sqlite3, concurrent.futures

## 定时任务
- 每天14:50运行（周日-周四）
- 执行: `run_V50_daily.sh` (cd到release/V50/目录后执行)

## 设计要点
- 红涨绿跌（中国习惯）：📈#ff4757红 📉#7bed9f绿
- 尾盘形态加分不改变评分排序（仅标注）
- 回测数据源：big_cache_full.pkl（含ma5_slope字段）
- 实时选股：从K线JSON缓存计算ma5_slope
- 初始过滤 p < 15
- 达标标准：次日最高涨幅 ≥ 2.5%
- 邮件模板：日期卡片 + 实战复盘 + 精研选股 + 版本档案（30/50/100天胜率）
- 尾盘时间（14:00~15:00）红色高亮
|- 收件人：1254628314@qq.com
|- 自动刷新：每次运行前自动调用rebuild_big_cache.py重建最新big_cache

## 版本升级指南
1. 全量复制 release/V50/ → release/V51/
2. 修改 V51_日报.py 中的版本号和路径
3. 创建新 cron job 或修改 shell 脚本路径
4. V50 可继续独立运行，不影响
