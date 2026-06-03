#!/bin/bash
# 前置检查 → V48每日选股
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行V48每日选股..."
python V48_日报.py
