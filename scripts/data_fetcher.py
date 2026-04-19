"""
杨永兴短线战法 - 行情数据获取层
基于 akshare 封装，提供：
- 实时涨幅排行
- 个股详细数据
- 大盘趋势判断
- 涨停记录查询
- 分时数据
"""

import akshare as ak
import pandas as pd
import datetime
import time
import logging

logger = logging.getLogger(__name__)


def _retry(func, retries=3, delay=2):
    """带重试的函数调用"""
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            if i < retries - 1:
                logger.warning(f"第{i+1}次重试: {e}")
                time.sleep(delay)
            else:
                raise


# ============ 大盘数据 ============

def get_market_trend():
    """
    判断大盘趋势：近5日均线方向
    返回: dict { trend: "up"/"down"/"flat", ma5: float, close: float, change_pct: float }
    """
    try:
        # 获取上证指数近30日日K
        df = _retry(lambda: ak.stock_zh_index_daily(symbol="sh000001"))
        if df is None or df.empty:
            return {"trend": "unknown", "reason": "无法获取大盘数据"}

        # 先按日期升序计算均线，再取最近数据
        df = df.sort_values("date", ascending=True)
        df["ma5"] = df["close"].rolling(5).mean()
        df_recent = df.tail(10)

        latest = df_recent.iloc[-1]
        prev = df_recent.iloc[-2] if len(df_recent) > 1 else latest

        # 近5日均线走势（最新MA5 vs 前一日MA5）
        ma5_latest = latest["ma5"]
        ma5_prev = df_recent.iloc[-2]["ma5"] if len(df_recent) > 1 and pd.notna(df_recent.iloc[-2]["ma5"]) else None

        if pd.notna(ma5_latest) and ma5_prev is not None:
            if ma5_latest > ma5_prev:
                trend = "up"
            elif ma5_latest < ma5_prev:
                trend = "down"
            else:
                trend = "flat"
        else:
            trend = "unknown"

        change_pct = ((latest["close"] - prev["close"]) / prev["close"]) * 100

        return {
            "trend": trend,
            "close": latest["close"],
            "ma5": round(ma5_latest, 2) if pd.notna(ma5_latest) else None,
            "change_pct": round(change_pct, 2),
            "volume": latest.get("volume", 0),
        }
    except Exception as e:
        logger.error(f"获取大盘趋势失败: {e}")
        return {"trend": "unknown", "reason": str(e)}


def get_market_status():
    """
    获取当日大盘状态（是否放量大跌等）
    返回: dict { is_crash: bool, volume_ratio: float, change_pct: float }
    """
    try:
        df = _retry(lambda: ak.stock_zh_index_daily(symbol="sh000001"))
        if df is None or df.empty:
            return {"is_crash": False, "reason": "无法获取数据"}

        df = df.sort_values("date", ascending=False).head(10)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        latest = df.iloc[0]
        avg_volume = df.iloc[1:6]["volume"].mean()
        latest_vol = pd.to_numeric(latest["volume"], errors="coerce")
        volume_ratio = latest_vol / avg_volume if avg_volume > 0 and pd.notna(avg_volume) else 1.0

        prev = df.iloc[1] if len(df) > 1 else latest
        change_pct = ((latest["close"] - prev["close"]) / prev["close"]) * 100

        # 放量大跌判定：跌幅>2% 且 量比>1.5
        is_crash = change_pct < -2.0 and volume_ratio > 1.5

        return {
            "is_crash": is_crash,
            "volume_ratio": round(volume_ratio, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        logger.error(f"获取大盘状态失败: {e}")
        return {"is_crash": False, "reason": str(e)}


# ============ 个股数据 ============

def get_realtime_quotes():
    """
    获取全市场实时行情（涨幅排行）
    返回 DataFrame: 包含代码、名称、涨跌幅、成交量、换手率等
    """
    try:
        df = _retry(lambda: ak.stock_zh_a_spot_em())
        if df is None or df.empty:
            return pd.DataFrame()

        # 统一列名
        col_map = {
            "代码": "code",
            "名称": "name",
            "最新价": "price",
            "涨跌幅": "change_pct",
            "涨跌额": "change_amt",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "最高": "high",
            "最低": "low",
            "今开": "open",
            "昨收": "pre_close",
            "量比": "volume_ratio",
            "换手率": "turnover_rate",
            "市盈率-动态": "pe",
            "市净率": "pb",
            "总市值": "total_mv",
            "流通市值": "circ_mv",
            "60日涨跌幅": "chge_60d",
            "年初至今涨跌幅": "chge_ytd",
        }
        df = df.rename(columns=col_map)

        # 确保数值类型
        for col in ["change_pct", "volume_ratio", "turnover_rate", "amplitude", "circ_mv", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 流通市值转换为亿元
        if "circ_mv" in df.columns:
            df["circ_mv_billion"] = df["circ_mv"] / 1e8

        return df
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return pd.DataFrame()


def get_limit_up_history(days=20):
    """
    获取近N天的涨停股票记录
    返回 dict: { 日期: [股票代码列表] }
    """
    try:
        result = {}
        today = datetime.date.today()

        for i in range(days):
            date = today - datetime.timedelta(days=i + 1)
            date_str = date.strftime("%Y%m%d")

            # 跳过周末
            if date.weekday() >= 5:
                continue

            try:
                df = _retry(lambda d=date_str: ak.stock_zt_pool_em(date=d))
                if df is not None and not df.empty:
                    codes = df["代码"].tolist() if "代码" in df.columns else []
                    result[date_str] = codes
            except Exception:
                continue

            time.sleep(0.3)  # 控制请求频率

        return result
    except Exception as e:
        logger.error(f"获取涨停历史失败: {e}")
        return {}


def get_limit_up_today():
    """
    获取今日涨停股票列表
    返回 list: 股票代码列表
    """
    try:
        today_str = datetime.date.today().strftime("%Y%m%d")
        df = _retry(lambda: ak.stock_zt_pool_em(date=today_str))
        if df is not None and not df.empty and "代码" in df.columns:
            return df["代码"].tolist()
        return []
    except Exception:
        return []


def get_intraday_data(code):
    """
    获取个股分时数据
    返回 dict: { avg_price: 均价, above_avg: 是否全天在均价线上方, current_vs_avg: 当前价vs均价 }
    """
    try:
        # akshare 分时数据
        df = _retry(lambda: ak.stock_intraday_em(symbol=code))
        if df is None or df.empty:
            return {"avg_price": None, "above_avg": None, "reason": "无分时数据"}

        # 计算成交均价
        if "成交额" in df.columns and "成交量" in df.columns:
            total_amount = df["成交额"].sum()
            total_volume = df["成交量"].sum()
            avg_price = total_amount / total_volume / 100 if total_volume > 0 else None
        else:
            avg_price = None

        # 判断是否全天在均价线上方
        current_price = None
        above_avg = None

        if avg_price and "最新价" in df.columns:
            prices = df["最新价"].dropna()
            current_price = prices.iloc[-1] if len(prices) > 0 else None
            if len(prices) > 0:
                above_avg = (prices >= avg_price * 0.995).all()  # 允许0.5%误差

        return {
            "avg_price": round(avg_price, 2) if avg_price else None,
            "above_avg": above_avg,
            "current_price": current_price,
        }
    except Exception as e:
        logger.error(f"获取{code}分时数据失败: {e}")
        return {"avg_price": None, "above_avg": None, "reason": str(e)}


def get_stock_kline(code, days=30):
    """
    获取个股日K数据
    返回 DataFrame: 包含日期、开高低收、成交量等
    """
    try:
        df = _retry(lambda: ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq"))
        if df is None or df.empty:
            return pd.DataFrame()

        col_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "change_pct",
            "换手率": "turnover_rate",
        }
        df = df.rename(columns=col_map)
        df = df.sort_values("date", ascending=False).head(days)
        return df
    except Exception as e:
        logger.error(f"获取{code}日K数据失败: {e}")
        return pd.DataFrame()


def get_stock_info(code):
    """
    获取个股基本信息
    返回 dict
    """
    try:
        df = _retry(lambda: ak.stock_individual_info_em(symbol=code))
        if df is None or df.empty:
            return {}

        info = {}
        for _, row in df.iterrows():
            info[row["item"]] = row["value"]
        return info
    except Exception as e:
        logger.error(f"获取{code}基本信息失败: {e}")
        return {}
