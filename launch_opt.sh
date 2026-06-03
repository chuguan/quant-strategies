#!/bin/bash
cd ~/AppData/Local/hermes/scripts
while true; do
    python -u 分而治之_自动调优.py >> 调优日志.txt 2>&1
    sleep 2
done
