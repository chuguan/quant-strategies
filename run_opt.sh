#!/bin/bash
# Detached launcher for the optimizer
cd ~/AppData/Local/hermes/scripts
rm -f 调优日志.txt
python -u 分而治之_自动调优.py >> 调优日志.txt 2>&1 &
PID=$!
echo $PID > /tmp/optimizer_pid.txt
echo "Started optimizer with PID=$PID"
wait $PID
