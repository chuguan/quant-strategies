"""版本路径配置 — 自检测，拷贝到新版本自动适配"""
import os

# 自动检测本文件所在目录（即版本根目录）
VERSION_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_NAME = os.path.basename(VERSION_DIR)

# 常用路径
BIG_CACHE_PKL = os.path.join(VERSION_DIR, 'big_cache_full.pkl')
FEATURES_PKL = os.path.join(VERSION_DIR, 'features_30d.pkl')
QUANT_DB = os.path.join(VERSION_DIR, f'{VERSION_NAME.lower()}_quant.db')

# 评分策略DIR
STRATEGY_DIR = os.path.join(VERSION_DIR, '评分策略')

# 父级目录
SCRIPTS_DIR = os.path.dirname(os.path.dirname(VERSION_DIR))
CACHE_DIR = os.path.expanduser('~/AppData/Local/hermes/hermes-agent/cache')

# 常用别名
DIR = VERSION_DIR
NAME = VERSION_NAME
PKL = BIG_CACHE_PKL
