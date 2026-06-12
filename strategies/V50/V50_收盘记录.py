#!/usr/bin/env python3
"""V50 收盘记录(15:10) — 跑选股+写数据库, 不发邮件"""
import sys, os
SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/prod')
sys.path.insert(0, SCRIPTS_DIR)

# 临时禁用邮件发送
import subprocess
_real_run = subprocess.run
def _noop_run(*args, **kwargs):
    cmd = args[0] if args else kwargs.get('args', [])
    if len(cmd) > 1 and 'send_email' in str(cmd[0]):
        print('📧 [收盘模式] 跳过邮件发送')
        class FakeResult:
            stdout = '✓ 收盘模式跳过'
        return FakeResult()
    return _real_run(*args, **kwargs)
subprocess.run = _noop_run

# 运行V50日报
exec(open(os.path.join(SCRIPTS_DIR, 'strategies', 'V50', 'V51_日报.py')).read())
