#!/bin/bash
# CG18 每日选股 — 双模式虚涨日
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR/strategies/CG18"
echo "[任务] 执行CG18每日选股(双模式虚涨日)..."
python CG18_日报.py
echo "[完成] CG18每日选股"
