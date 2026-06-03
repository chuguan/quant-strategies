"""腾讯API字段解析 — 找出HSL和市值位置"""
import subprocess, sys

r = subprocess.run(['curl', '-s', 'http://qt.gtimg.cn/q=sh600519'], capture_output=True, timeout=10)
line = r.stdout.decode('gbk', errors='ignore').strip()
if '=' in line:
    data = line.split('=')[1].strip().strip('"')
    parts = data.split('~')
    for i, p in enumerate(parts):
        print(f'[{i:>3}] = {p}')
