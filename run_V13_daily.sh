#!/bin/bash
# 前置检查 → V13每日日报
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行V13日报..."
python V13_日报.py
