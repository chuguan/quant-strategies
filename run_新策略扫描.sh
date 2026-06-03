#!/bin/bash
# 前置检查 → 新策略早盘扫描
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行新策略早盘扫描..."
python quant/scan_new_strategy.py
