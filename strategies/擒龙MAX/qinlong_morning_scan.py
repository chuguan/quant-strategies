#!/usr/bin/env python3
"""擒龙早盘扫描 — 9:23/9:26跑，发邮件"""
import os, sys, subprocess, time
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 统一导入 lib/send_email
LIB_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), 'lib')
sys.path.insert(0, LIB_DIR)

def send_email(to_list, subject, body, html=True):
    """用 lib/send_email.py 统一发邮件"""
    try:
        from send_email import send_email as se
        return se(to_list, subject, body, html=html, force=True)
    except Exception as e:
        print(f'⚠️ 邮件发送失败: {e}')
        return False

def main():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    hour_min = f'{now.hour:02d}:{now.minute:02d}'
    
    print(f'🐉 擒龙早盘扫描 {today} {hour_min}')
    print('.' * 50)
    
    # 跑擒龙扫描
    scanner = os.path.join(SCRIPTS_DIR, 'quant', 'qinlong_scanner.py')
    if not os.path.exists(scanner):
        print(f'❌ 找不到 {scanner}')
        # 尝试直接import
        sys.path.insert(0, os.path.join(SCRIPTS_DIR, 'quant'))
        from qinlong_scanner import run as ql_run
        results = ql_run()
    else:
        r = subprocess.run([sys.executable, scanner], capture_output=True, timeout=120, text=True)
        output = r.stdout
        if r.stderr:
            output += '\n[stderr]\n' + r.stderr
        print(output)
        
        # 解析TOP10结果
        results = None
        for line in output.split('\n'):
            if '🏆 擒龙TOP' in line:
                break
    
    if results is not None:
        print(f'  扫描完成: {len(results)}只合格')
    else:
        print('  (已通过subprocess运行，结果见上方)')
    
    # 发送邮件
    to_list = ['1254628314@qq.com', '314913203@qq.com', '2603672569@qq.com', '2318162429@qq.com']
    subj = f'🐉 擒龙早盘扫描 {today} {hour_min}'
    html_body = f'''
<div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif">
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:#e94560;padding:12px;border-radius:8px 8px 0 0;text-align:center;font-size:18px;font-weight:bold">
    🐉 擒龙早盘扫描
  </div>
  <div style="background:#f8f9fa;padding:12px;border:1px solid #ddd;border-top:none">
    <div style="color:#666;font-size:12px;margin-bottom:8px">
      扫描时间: {today} {hour_min} | 基于集合竞价/昨日收盘数据
    </div>
    <pre style="background:#1a1a2e;color:#e0e0e0;padding:10px;border-radius:4px;font-size:12px;overflow-x:auto;white-space:pre-wrap">{output if results is None else "TOP10结果如上"}</pre>
  </div>
  <div style="background:#eee;padding:8px;border-radius:0 0 8px 8px;text-align:center;font-size:11px;color:#999">
    擒龙MAX · 自动扫描 · 仅供参考
  </div>
</div>'''
    
    ok = send_email(to_list, subj, html_body)
    print(f'📧 邮件: {"✅已发送" if ok else "❌失败"}')

if __name__ == '__main__':
    main()
