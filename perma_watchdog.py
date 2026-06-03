#!/usr/bin/env python3
"""Permanent optimizer watchdog - runs forever, restarts optimizer on crash"""
import subprocess, sys, os, time, signal

scripts_dir = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(scripts_dir)
log_path = os.path.join(scripts_dir, 'opt_log.txt')

def start_opt():
    with open(log_path, 'a') as log:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        log.write(f"\n{'='*50} LAUNCH at {ts} {'='*50}\n")
        log.flush()
        return subprocess.Popen(
            [sys.executable, '-u', '分而治之_自动调优.py'],
            stdout=log, stderr=subprocess.STDOUT, cwd=scripts_dir
        )

print(f"WATCHDOG_PID={os.getpid()}", flush=True)
proc = start_opt()

while True:
    try:
        rc = proc.wait()
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a') as log:
            log.write(f"\n*** EXIT code={rc} at {ts}, restarting in 3s ***\n")
        time.sleep(3)
        proc = start_opt()
    except KeyboardInterrupt:
        proc.terminate()
        break
