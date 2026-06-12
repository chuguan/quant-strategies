#!/bin/bash
# V13+V42+V50 尾盘选股验证复盘 — 盘后15:05
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR"
echo "============================================"
echo "  V13+V42+V50 尾盘验证复盘 | 盘后 $(date +%H:%M)"
echo "============================================"
python report/fupan.py 2>&1
echo "============================================"
