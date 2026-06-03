#!/bin/bash
# V43每日选股 — 含安全监控 + 自动降级
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行V43每日选股..."
python V43_日报.py
