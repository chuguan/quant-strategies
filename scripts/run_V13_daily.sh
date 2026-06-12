#!/bin/bash
# V13 每日选股 — 生产环境
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR"
echo "[前置] 数据检查..."
python infra/pre_task_check.py
echo "[任务] 执行V13日报..."
python strategies/V13/V13_日报.py
