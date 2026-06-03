#!/bin/bash
# 前置检查 → 分而治之_V10尾盘策略
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行分而治之V10尾盘策略..."
python V10/分而治之_V10_生产.py
