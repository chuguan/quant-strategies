#!/bin/bash
# 前置检查 → V22长期稳定版尾盘策略
cd "$(dirname "$0")"
echo "[前置] 数据检查..."
python pre_task_check.py
echo "[任务] 执行V22长期稳定版尾盘策略..."
python V22_日报.py
