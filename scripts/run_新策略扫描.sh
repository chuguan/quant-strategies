#!/bin/bash
# 新策略早盘扫描 — 生产环境
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR"
echo "[前置] 数据检查..."
python infra/pre_task_check.py
echo "[任务] 执行新策略早盘扫描..."
python strategies/新策略/scan_new_strategy.py
