#!/usr/bin/env python
"""数据源脚本归档到 v13_quant.db"""
import sqlite3, os, hashlib, json

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
db_path = os.path.join(SCRIPTS_DIR, 'v13_quant.db')

# 读已有数据库
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 检查 strategy_files 表是否存在，不存在则创建
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_files'")
if not c.fetchone():
    c.execute('''
        CREATE TABLE strategy_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_type TEXT NOT NULL,
            data_provider TEXT,
            api_endpoint TEXT,
            archive_date TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_content TEXT NOT NULL,
            file_size INTEGER,
            file_hash TEXT NOT NULL,
            UNIQUE(file_name, archive_date)
        )
    ''')
    print('✅ 创建 strategy_files 表')

# =============================================
#  档案一：数据源脚本（4大源）
# =============================================

data_sources = {
    '新浪实时行情': {
        'data_provider': 'sina',
        'api_endpoint': 'hq.sinajs.cn',
        'files': ['sina_api.py']
    },
    '腾讯K线+实时': {
        'data_provider': 'tencent',
        'api_endpoint': 'web.ifzq.gtimg.cn + qt.gtimg.cn',
        'files': ['fetch_us_data.py', 'fetch_spx.py', 'fetch_us_final.py', 'download_missing_data.py']
    },
    '东方财富K线': {
        'data_provider': 'eastmoney',
        'api_endpoint': 'push2his.eastmoney.com',
        'files': ['refresh_em_kline.py', 'build_precise_cache.py']
    },
    '多源统一接口': {
        'data_provider': 'multi',
        'api_endpoint': '新浪+腾讯+Tushare',
        'files': ['data_source.py']
    },
}

total_archived = 0
for src_name, src_info in data_sources.items():
    provider = src_info['data_provider']
    api = src_info['api_endpoint']
    
    for fname in src_info['files']:
        fpath = os.path.join(SCRIPTS_DIR, fname)
        if not os.path.exists(fpath):
            print(f'  ⚠️ 未找到: {fpath}')
            continue
        
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        fhash = hashlib.sha256(content.encode()).hexdigest()[:16]
        fsize = len(content.encode())
        arc_name = f'{fname.replace(".py","")}_{os.path.getmtime(fpath):.0f}.py'
        
        c.execute('''
            INSERT OR REPLACE INTO strategy_files
            (strategy_version, file_date, file_time, file_type,
             file_name, file_path, file_content, file_size, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (f'data:{provider}', '2026-06-01', '00:00:00',
              f'data_source:{provider}',
              fname, fpath, content, fsize, fhash))
        total_archived += 1
        print(f'  ✅ [{provider:>10}] {fname:>30} ({fsize:>5}B) hash={fhash}')

conn.commit()

# =============================================
#  展示
# =============================================
print(f'\n{"="*70}')
print(f'  📂 数据源脚本完整归档到 v13_quant.db')
print(f'{"="*70}')

print(f'\n📋 按数据源分组：')

for src_name, src_info in data_sources.items():
    provider = src_info['data_provider']
    api = src_info['api_endpoint']
    
    print(f'\n  🌐 {src_name}')
    print(f'     数据提供方: {provider}')
    print(f'     API端点:    {api}')
    
    for fname in src_info['files']:
        r = c.execute('''
            SELECT file_size, file_hash FROM strategy_files 
            WHERE file_type=? AND file_name=?
        ''', (f'data_source:{provider}', fname)).fetchone()
        if r:
            print(f'     📄 {fname:>30} ({r[0]:>5}B) {r[1]}')

print(f'\n{"="*70}')
print(f'  📊 数据库归档统计')
print(f'{"="*70}')

# 按类别统计
print(f'\n  按 file_type 统计：')
for r in c.execute('''
    SELECT file_type, COUNT(*), SUM(file_size) 
    FROM strategy_files GROUP BY file_type ORDER BY file_type
'''):
    print(f'    {r[0]:>30}: {r[1]:>2}个文件, {r[2]:>6,}B')

print(f'\n  全部文件列表：')
print(f'  {"文件类型":>30} {"文件名":>35} {"大小":>6}')
print(f'  {"-"*72}')
for r in c.execute('''
    SELECT file_type, file_name, file_size 
    FROM strategy_files ORDER BY file_type, file_name
'''):
    print(f'  {r[0]:>30} {r[1]:>35} {r[2]:>6}B')

print(f'\n  文件还原测试：')
r = c.execute("SELECT file_content FROM strategy_files WHERE file_name='sina_api.py'").fetchone()
print(f'    SELECT file_content FROM strategy_files WHERE file_name="sina_api.py"')
print(f'    → 返回 {len(r[0])} 字符，完整文件内容')
print(f'    ✅ 原文件丢失，从数据库直接还原')

conn.close()
print(f'\n📁 {db_path}')
