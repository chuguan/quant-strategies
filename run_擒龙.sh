#!/bin/bash
# 前置检查 → 擒龙MAX策略
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行擒龙MAX..."
python qinlong_5day_email.py
