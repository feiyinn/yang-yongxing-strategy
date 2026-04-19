"""
杨永兴短线战法 - 配置参数
"""

# ============ 选股过滤参数 ============

# 涨幅范围（收盘涨跌幅）
RISE_MIN = 3.0  # %
RISE_MAX = 5.0  # %

# 流通市值范围（亿元）
MARKET_CAP_MIN = 50.0
MARKET_CAP_MAX = 200.0

# 换手率范围
TURNOVER_MIN = 5.0  # %
TURNOVER_MAX = 10.0  # %

# 量比最低要求
VOLUME_RATIO_MIN = 1.0

# 振幅上限（超过则风险偏高）
AMPLITUDE_MAX = 8.0  # %

# 近N天有涨停记录
LIMIT_UP_DAYS = 20

# 只选主板（排除科创板688、北交所8/4、创业板300）
MAIN_BOARD_ONLY = True

# ============ 大盘环境参数 ============

# 上证指数代码
SH_INDEX_CODE = "000001"

# 大盘5日均线趋势判断：近N日均线方向
TREND_DAYS = 5

# ============ 卖出规则参数 ============

# 止损线（亏损%）
STOP_LOSS = 3.0

# 止损线2（亏损%强制）
FORCE_STOP_LOSS = 5.0

# ============ 仓位管理参数 ============

# 单票最大仓位占比
MAX_POSITION_RATIO = 0.20

# 每日最大操作笔数
MAX_TRADES_PER_DAY = 3

# ============ 路径配置（自动检测） ============

import os

# 基于脚本所在目录自动检测，无需硬编码
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = SCRIPTS_DIR
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
