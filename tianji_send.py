#!/usr/bin/env python3
"""天机早报发送脚本 — 从HTML文件读取内容，发送到3个收件人"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_email import send_email

if len(sys.argv) < 3:
    print('用法: python tianji_send.py <HTML报告文件> <邮件主题>')
    sys.exit(1)

report_file = sys.argv[1]
subject = sys.argv[2]

with open(report_file, 'r', encoding='utf-8') as f:
    html = f.read()

recipients = ['1254628314@qq.com', '314913203@qq.com']
send_email(recipients, subject, html, html=True)
