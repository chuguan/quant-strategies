#!/bin/bash
# V42 每日选股 — 生产环境
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR"
echo "[前置] 数据检查..."
python infra/pre_task_check.py
echo "[任务] 执行V42每日选股..."
python strategies/V42/V42_日报.py
