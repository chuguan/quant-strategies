import sys
import subprocess
import os

scripts_dir = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(scripts_dir)
log_path = os.path.join(scripts_dir, '调优日志.txt')

with open(log_path, 'a') as log:
    log.write(f"\n=== RESTART AT {__import__('datetime').datetime.now().isoformat()} ===\n")
    proc = subprocess.Popen(
        [sys.executable, '-u', '分而治之_自动调优.py'],
        stdout=log,
        stderr=subprocess.STDOUT
    )
    print(proc.pid)
