#!/bin/bash
# 前置检查 → 定海神针尾盘策略
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行定海神针尾盘策略..."
python 定海神针/定海神针_整则.py
