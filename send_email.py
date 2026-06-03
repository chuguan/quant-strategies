#!/usr/bin/env python3
"""
📧 邮件发送 — 配置从 v13_quant.db 读取，不改代码
使用方法：
  python send_email.py "主题" "正文内容"
  python send_email.py "主题" "正文内容" --html
  python send_email.py "主题" "正文内容" --to "指定收件人"
"""
import smtplib, ssl, sys, os
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

# 从数据库读配置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_config import get_email_config, get_config, get_config_list

def send_email(to=None, subject='', body='', html=False, env=None, config='A'):
    """发送邮件
    to: 收件人列表，None则从数据库读
    subject: 主题
    body: 正文
    html: 是否HTML
    env: 环境（production/dev），None则从环境变量或默认
    config: 'A'读email表, 'B'读email_b表
    """
    cat = 'email_b' if config == 'B' else 'email'
    cfg = get_email_config(env, category=cat)
    
    smtp_host = cfg['smtp_host']
    smtp_port = cfg['smtp_port']
    sender = cfg['sender']
    password = cfg['password']
    recipients = to if to else cfg['recipients']
    night_start = cfg['night_block_start']
    night_end = cfg['night_block_end']
    
    if not all([smtp_host, smtp_port, sender, password]):
        print('❌ 邮件配置不完整，请检查 config 表')
        return False
    
    # 深夜禁发
    now = datetime.now()
    if night_start <= now.hour < night_end:
        print(f'⏰ 凌晨{now.hour}点，跳过邮件发送: {subject}')
        return False
    
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(',') if r.strip()]
    
    display_to = ', '.join(recipients)
    subtype = 'html' if html else 'plain'
    ctx = ssl.create_default_context()
    
    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
            server.login(sender, password)
            for r in recipients:
                msg = MIMEText(body, subtype, 'utf-8')
                msg['From'] = sender
                msg['To'] = r
                msg['Subject'] = Header(subject, 'utf-8')
                server.sendmail(sender, [r], msg.as_string())
        print(f'✓ 邮件已发送到 {display_to}')
        return True
    except Exception as e:
        print(f'✗ 邮件发送失败: {e}')
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python send_email.py "主题" "正文" [--html] [--to "收件人"]')
        sys.exit(1)
    
    subject = sys.argv[1]
    body = sys.argv[2] if len(sys.argv) > 2 else ''
    html = '--html' in sys.argv
    config = 'B' if '--config' in sys.argv and sys.argv[sys.argv.index('--config') + 1] == 'B' else 'A'
    to = None
    
    if '--to' in sys.argv:
        idx = sys.argv.index('--to')
        if idx + 1 < len(sys.argv):
            to = [r.strip() for r in sys.argv[idx + 1].split(',')]
    
    # 从 HERMES_ENV 环境变量决定环境，默认 production
    env = os.environ.get('HERMES_ENV', 'production')
    send_email(to=to, subject=subject, body=body, html=html, env=env, config=config)
