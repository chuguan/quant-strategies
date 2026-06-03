#!/usr/bin/env python3
"""获取沪深主板活跃股票列表（非ST/非退市），存入文件"""
import os, sys, subprocess, time, json

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
os.chdir(SCRIPTS_DIR)

def curl_get(url, timeout=8):
    try:
        r = subprocess.run(['curl','-s','--max-time',str(timeout),url], capture_output=True, timeout=timeout+5)
        return r.stdout.decode('gbk', errors='replace')
    except: return ''

IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))
PREFIX = lambda c: 'sh' if c.startswith(('6','9')) else 'sz'

# 全范围扫描
all_codes = []
for i in range(600000, 606000): all_codes.append(str(i))
for i in range(0, 3000): all_codes.append(f'{i:06d}')

active_stocks = {}  # {code: {name, hsl, sz, pe}}
for i in range(0, len(all_codes), 80):
    chunk = all_codes[i:i+80]
    symbols = [f'{PREFIX(c)}{c}' for c in chunk]
    text = curl_get(f'https://qt.gtimg.cn/q={",".join(symbols)}', timeout=6)
    for line in text.split('\n'):
        if '~' not in line: continue
        parts = line.split('~')
        if len(parts) < 46: continue
        try:
            nm = parts[1]; code = parts[2]
            if not nm or 'ST' in nm or '*ST' in nm or '退' in nm: continue
            if not IS_MAIN(code): continue
            hsl = 0
            try: hsl = float(parts[46]) if parts[46] and float(parts[46]) < 100 else 0
            except: pass
            sz = 0
            try: sz = float(parts[44])/1e8 if parts[44] else 0
            except: pass
            pe = 0
            try: pe = float(parts[39]) if parts[39] else 0
            except: pass
            active_stocks[code] = {'name': nm, 'hsl': hsl, 'sz': sz, 'pe': pe}
        except: pass

print(f'沪深主板活跃: {len(active_stocks)}只')

# 按板块分类
sh = {c:v for c,v in active_stocks.items() if c.startswith(('600','601','603','605'))}
sz = {c:v for c,v in active_stocks.items() if c.startswith(('000','001','002'))}
print(f'  沪主板: {len(sh)}只')
print(f'  深主板: {len(sz)}只')

# 写入文件
output = {
    'update_time': time.strftime('%Y-%m-%d %H:%M:%S'),
    'total': len(active_stocks),
    'sh_count': len(sh),
    'sz_count': len(sz),
    'codes': sorted(active_stocks.keys()),
    'info': active_stocks,
}

with open('活跃股票池_3043.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'✅ 已写入: 活跃股票池_3043.json')
print(f'   路径: {os.path.join(SCRIPTS_DIR, "活跃股票池_3043.json")}')
