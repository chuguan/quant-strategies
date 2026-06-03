#!/bin/bash
# 前置检查 → V42每日选股
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行V42每日选股..."
python V42_日报.py
