#!/bin/bash
# 前置检查 → 大道至简_V260529尾盘策略
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行大道至简V260529尾盘策略..."
python 大道至简_V260529.py
