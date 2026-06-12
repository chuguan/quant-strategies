#!/bin/bash
# V50 每日选股 — 生产环境（四维V2引擎）
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR/strategies/V50"
echo "[任务] 执行四维V2选股..."
python v51plus_4dim_v2.py
