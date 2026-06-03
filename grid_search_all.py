#!/usr/bin/env python3
"""
全面网格搜索：涨跌幅1~8%过滤下，所有评分公式的胜率
"""
import pickle
import pandas as pd
import numpy as np
from itertools import product
import time

start = time.time()

with open('precise_cache.pkl', 'rb') as f:
    cache = pickle.load(f)

data = cache['data']
names = cache['names']

# Hard filter: 涨跌幅 1~8%
MIN_CHG = 1.0
MAX_CHG = 8.0

# 次日目标涨幅 2.5%
TARGET = 2.5

# We need the 5日最高 to compute next-day performance.
# The cache already has 5日最高 embedded... wait, let me check.
# Actually the cache doesn't have future data. Let me check the CG-07 backtest
# code to understand how next-day performance is calculated.

# Let me check what the CG-07 backtester does
import os
for f in os.listdir('.'):
    if 'CG-07' in f and f.endswith('.py'):
        print(f'Found: {f}')

# Actually I know the CG-07 code. It uses the data from the original stock data
# to compute next-day performance.
# The cache only stores today's data. We need another source for next-day data.

# Let me check the original data source
print('Checking for data source files...')
for f in os.listdir('.'):
    if 'all_stocks' in f or 'stock_data' in f or 'stock' in f.lower():
        size = os.path.getsize(f) / 1024 / 1024
        print(f'  {f}: {size:.1f}MB')
