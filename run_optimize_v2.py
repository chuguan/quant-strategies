#!/usr/bin/env python3
"""Watchdog launcher that keeps 分而治之_自动调优.py running in background"""

import subprocess
import sys
import os
import time
import signal

scripts_dir = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(scripts_dir)
log_path = os.path.join(scripts_dir, '调优日志.txt')

def start_optimizer():
    with open(log_path, 'a') as log:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        log.write(f"\n=== LAUNCH at {ts} ===\n")
        log.flush()
        proc = subprocess.Popen(
            [sys.executable, '-u', '分而治之_自动调优.py'],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=scripts_dir
        )
    return proc

proc = start_optimizer()
# Print PID so Hermes can track it
print(f"OPTIMIZER_PID={proc.pid}")
sys.stdout.flush()

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
    sys.exit(0)
