#!/bin/bash
# V13+V42 尾盘选股验证复盘 — 午盘11:40
PROD_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
export PYTHONPATH="$PROD_DIR/lib:$PYTHONPATH"
cd "$PROD_DIR"
echo "============================================"
echo "  V13+V42 尾盘验证复盘 | 午盘 $(date +%H:%M)"
echo "============================================"
python report/fupan.py 2>&1
echo "============================================"
