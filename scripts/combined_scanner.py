"""
SEPA策略 + 杨永兴战法 联合扫描引擎
先SEPA基本面7步筛选优质标的，再杨永兴9步技术面寻找短线买点

流程：
  第一阶段 - SEPA七步基本面筛选：
    1. 剔除ST和上市不满1年的次新股
    2. 营收同比增长 > 25%
    3. 净利润同比增长 > 30%，环比为正
    4. 股价在50日/150日均线之上
    5. 近10日均量 > 120日均量（放量）
    6. ROE > 15%
    7. 近3年净利润CAGR > 20%

  第二阶段 - 杨永兴战法技术面筛选：
    0. 大盘环境判断（放量大跌则空仓）
    1. 今日涨幅 3%-5%
    2. 近20天有涨停记录
    3. 量比 ≥ 1
    4. 流通市值 50-200亿
    5. 换手率 5%-10%
    6. 振幅 ≤ 8%
    7. K线上方无压力（无长上影线）
    8. 分时站均价线上方
"""

import logging
import datetime
import time
import math
import pandas as pd
import numpy as np
from config import (
    SEPA_REVENUE_GROWTH_MIN, SEPA_PROFIT_GROWTH_MIN, SEPA_ROE_MIN,
    SEPA_PROFIT_CAGR_MIN, SEPA_LISTING_MIN_DAYS, SEPA_MA_SHORT, SEPA_MA_LONG,
    SEPA_VOL_SHORT, SEPA_VOL_LONG,
    RISE_MIN, RISE_MAX, MARKET_CAP_MIN, MARKET_CAP_MAX,
    TURNOVER_MIN, TURNOVER_MAX, VOLUME_RATIO_MIN, AMPLITUDE_MAX,
    LIMIT_UP_DAYS,
)
from sepa_filter import SEPAFilter
from scanner import Scanner, is_st_stock
import data_fetcher as df_api

logger = logging.getLogger(__name__)


class CombinedScanner:
    """SEPA + 杨永兴 联合扫描引擎"""

    def __init__(self):
        self.filter_log = []
        self.sepa_filter = SEPAFilter()
        self.scanner = Scanner()

    def log_filter(self, phase, step, action, count_before, count_after, reason=""):
        self.filter_log.append({
            "phase": phase,
            "step": step,
            "action": action,
            "count_before": count_before,
            "count_after": count_after,
            "filtered": count_before - count_after,
            "reason": reason,
        })

    def scan(self, skip_intraday=False, skip_ma_check=False, relax_yang=False):
        """
        执行SEPA+杨永兴联合扫描

        参数:
          skip_intraday: 跳过杨永兴分时数据检查（加快速度）
          skip_ma_check: 跳过SEPA均线检查（加快速度）
          relax_yang: 放宽杨永兴条件（涨幅不限、市值/换手率放宽）

        返回: {
            sepa_candidates: list,   # SEPA通过的候选股
            final_candidates: list,  # 双战法同时通过的最终候选
            filter_log: list,        # 完整筛选日志
            market: dict,            # 大盘环境
            scan_time: str,
            strategy: str,
        }
        """
        self.filter_log = []

        # ============ 第一阶段：SEPA基本面筛选 ============
        logger.info("=" * 60)
        logger.info("第一阶段：SEPA七步基本面筛选")
        logger.info("=" * 60)

        sepa_result = self.sepa_filter.scan(skip_ma_check=skip_ma_check)

        # 把SEPA的filter_log搬过来，标注phase
        for log in self.sepa_filter.filter_log:
            self.filter_log.append({
                "phase": "SEPA",
                "step": log.get("step"),
                "action": log.get("action"),
                "count_before": log.get("count_before", log.get("count_before", 0)),
                "count_after": log.get("count_after", log.get("count_after", 0)),
                "filtered": log.get("filtered", 0),
            })

        sepa_candidates = sepa_result.get("candidates", [])
        logger.info(f"SEPA筛选完成: {len(sepa_candidates)} 只候选股")

        if not sepa_candidates:
            return self._build_result([], sepa_candidates)

        # ============ 获取SEPA候选股行情 ============
        sepa_codes = [c["code"] for c in sepa_candidates]
        all_stocks = df_api.get_realtime_quotes()

        if all_stocks.empty:
            logger.warning("无法获取行情数据，跳过杨永兴筛选")
            return self._build_result([], sepa_candidates)

        stocks = all_stocks[all_stocks["code"].isin(sepa_codes)].copy()
        if stocks.empty:
            # 行情不可用但有SEPA候选，构建仅含代码的DataFrame
            stocks = pd.DataFrame({
                "code": sepa_codes,
                "name": [c.get("name", "") for c in sepa_candidates],
                "price": [c.get("price") for c in sepa_candidates],
                "change_pct": [c.get("change_pct", 0) for c in sepa_candidates],
            })

        # 补充财务数据到行情中（用于后续报告）
        financial_cache = self.sepa_filter._financial_cache

        # ============ 第二阶段：杨永兴战法技术面筛选 ============
        logger.info("=" * 60)
        logger.info("第二阶段：杨永兴战法技术面筛选")
        logger.info("=" * 60)

        # 步骤0：大盘环境判断
        market_status = df_api.get_market_status()
        market_trend = df_api.get_market_trend()

        if market_status.get("is_crash"):
            logger.warning("大盘放量大跌，按杨永兴战法应空仓！")
            return self._build_result([], sepa_candidates, market_trend, market_status, "大盘放量大跌，空仓")

        # 步骤1：涨幅范围
        before = len(stocks)
        stocks["change_pct"] = stocks["change_pct"].apply(
            lambda x: float(x) if x and str(x) not in ("-", "--", "") else 0
        )

        if relax_yang:
            # 放宽模式：涨幅>0即可
            yang_stocks = stocks[stocks["change_pct"] > 0].copy()
            self.log_filter("杨永兴", 1, "涨幅>0%（放宽）", before, len(yang_stocks))
        else:
            yang_stocks = stocks[
                (stocks["change_pct"] >= RISE_MIN) & (stocks["change_pct"] <= RISE_MAX)
            ].copy()
            self.log_filter("杨永兴", 1, f"涨幅{RISE_MIN}%-{RISE_MAX}%", before, len(yang_stocks))

        logger.info(f"杨永兴步骤1后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            self._log_remaining_steps(start_step=2)
            return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤2：近20天有涨停记录
        before = len(yang_stocks)
        limit_up_cache = df_api.get_limit_up_history(days=LIMIT_UP_DAYS)
        limit_up_codes = set()
        for codes in limit_up_cache.values():
            limit_up_codes.update(codes)
        today_limit = df_api.get_limit_up_today()
        limit_up_codes.update(today_limit)

        yang_stocks = yang_stocks[yang_stocks["code"].isin(limit_up_codes)].copy()
        self.log_filter("杨永兴", 2, f"近{LIMIT_UP_DAYS}天有涨停", before, len(yang_stocks))
        logger.info(f"杨永兴步骤2后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            if relax_yang:
                logger.info("放宽模式下无涨停记录，跳过涨停要求")
                yang_stocks = stocks[stocks["change_pct"] > 0].copy()
                self.log_filter("杨永兴", 2, "涨停要求（放宽跳过）", before, len(yang_stocks))
            else:
                self._log_remaining_steps(start_step=3)
                return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤3：量比
        before = len(yang_stocks)
        if "volume_ratio" in yang_stocks.columns and yang_stocks["volume_ratio"].notna().any():
            yang_stocks["volume_ratio"] = yang_stocks["volume_ratio"].apply(
                lambda x: float(x) if x and str(x) not in ("-", "--", "") else None
            )
            mask = (yang_stocks["volume_ratio"] >= VOLUME_RATIO_MIN) | yang_stocks["volume_ratio"].isna()
            yang_stocks = yang_stocks[mask].copy()
        self.log_filter("杨永兴", 3, f"量比≥{VOLUME_RATIO_MIN}", before, len(yang_stocks))
        logger.info(f"杨永兴步骤3后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            self._log_remaining_steps(start_step=4)
            return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤4：流通市值
        before = len(yang_stocks)
        if "circ_mv_billion" in yang_stocks.columns and yang_stocks["circ_mv_billion"].notna().any():
            yang_stocks["circ_mv_billion"] = yang_stocks["circ_mv_billion"].apply(
                lambda x: float(x) if x and str(x) not in ("-", "--", "") else None
            )
            if relax_yang:
                cap_min, cap_max = 30, 500  # 放宽
            else:
                cap_min, cap_max = MARKET_CAP_MIN, MARKET_CAP_MAX
            mask = (
                (yang_stocks["circ_mv_billion"] >= cap_min) &
                (yang_stocks["circ_mv_billion"] <= cap_max)
            ) | yang_stocks["circ_mv_billion"].isna()
            yang_stocks = yang_stocks[mask].copy()
        cap_label = f"流通市值{cap_min}-{cap_max}亿" if relax_yang else f"流通市值{MARKET_CAP_MIN}-{MARKET_CAP_MAX}亿"
        self.log_filter("杨永兴", 4, cap_label, before, len(yang_stocks))
        logger.info(f"杨永兴步骤4后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            self._log_remaining_steps(start_step=5)
            return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤5：换手率
        before = len(yang_stocks)
        if "turnover_rate" in yang_stocks.columns and yang_stocks["turnover_rate"].notna().any():
            yang_stocks["turnover_rate"] = yang_stocks["turnover_rate"].apply(
                lambda x: float(x) if x and str(x) not in ("-", "--", "") else None
            )
            if relax_yang:
                tr_min, tr_max = 2, 15  # 放宽
            else:
                tr_min, tr_max = TURNOVER_MIN, TURNOVER_MAX
            mask = (
                (yang_stocks["turnover_rate"] >= tr_min) &
                (yang_stocks["turnover_rate"] <= tr_max)
            ) | yang_stocks["turnover_rate"].isna()
            yang_stocks = yang_stocks[mask].copy()
        tr_label = f"换手率{tr_min}-{tr_max}%" if relax_yang else f"换手率{TURNOVER_MIN}-{TURNOVER_MAX}%"
        self.log_filter("杨永兴", 5, tr_label, before, len(yang_stocks))
        logger.info(f"杨永兴步骤5后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            self._log_remaining_steps(start_step=6)
            return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤6：振幅
        before = len(yang_stocks)
        if "amplitude" in yang_stocks.columns:
            yang_stocks["amplitude"] = yang_stocks["amplitude"].apply(
                lambda x: float(x) if x and str(x) not in ("-", "--", "") else 0
            )
            yang_stocks = yang_stocks[yang_stocks["amplitude"] <= AMPLITUDE_MAX].copy()
        self.log_filter("杨永兴", 6, f"振幅≤{AMPLITUDE_MAX}%", before, len(yang_stocks))
        logger.info(f"杨永兴步骤6后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            self._log_remaining_steps(start_step=7)
            return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤7：K线上方无压力
        before = len(yang_stocks)
        yang_stocks = self._filter_kline_pressure(yang_stocks)
        self.log_filter("杨永兴", 7, "K线上方无压力", before, len(yang_stocks))
        logger.info(f"杨永兴步骤7后: {len(yang_stocks)} 只")

        if yang_stocks.empty:
            self._log_remaining_steps(start_step=8)
            return self._build_result([], sepa_candidates, market_trend, market_status)

        # 步骤8：分时站均价线上方
        if not skip_intraday:
            before = len(yang_stocks)
            yang_stocks = self._filter_intraday(yang_stocks)
            self.log_filter("杨永兴", 8, "分时站均价线上方", before, len(yang_stocks))
            logger.info(f"杨永兴步骤8后: {len(yang_stocks)} 只")
        else:
            self.log_filter("杨永兴", 8, "分时站均价线上方（跳过）", len(yang_stocks), len(yang_stocks))

        # ============ 构建最终结果 ============
        final_candidates = self._build_candidates(yang_stocks, financial_cache)

        return self._build_result(
            final_candidates, sepa_candidates, market_trend, market_status
        )

    def _filter_kline_pressure(self, stocks):
        """K线形态过滤：高位长上影线剔除"""
        result_codes = []
        for _, row in stocks.iterrows():
            code = row["code"]
            try:
                kline = df_api.get_stock_kline(code, days=20)
                if kline.empty or len(kline) < 5:
                    result_codes.append(code)
                    continue
                recent = kline.head(5)
                has_long_shadow = False
                for _, krow in recent.iterrows():
                    if pd.notna(krow.get("high")) and pd.notna(krow.get("close")):
                        upper_shadow = (krow["high"] - krow["close"]) / krow["close"]
                        if upper_shadow > 0.03:
                            has_long_shadow = True
                            break
                if not has_long_shadow:
                    result_codes.append(code)
            except Exception:
                result_codes.append(code)
            time.sleep(0.2)
        return stocks[stocks["code"].isin(result_codes)].copy()

    def _filter_intraday(self, stocks):
        """分时数据过滤：全天站均价线上方"""
        result_codes = []
        for _, row in stocks.iterrows():
            code = row["code"]
            try:
                intraday = df_api.get_intraday_data(code)
                if intraday.get("above_avg") is True or intraday.get("above_avg") is None:
                    result_codes.append(code)
            except Exception:
                result_codes.append(code)
        return stocks[stocks["code"].isin(result_codes)].copy()

    def _log_remaining_steps(self, start_step):
        """记录未执行的步骤"""
        step_names = {
            2: f"近{LIMIT_UP_DAYS}天有涨停", 3: f"量比≥{VOLUME_RATIO_MIN}",
            4: f"流通市值{MARKET_CAP_MIN}-{MARKET_CAP_MAX}亿",
            5: f"换手率{TURNOVER_MIN}-{TURNOVER_MAX}%", 6: f"振幅≤{AMPLITUDE_MAX}%",
            7: "K线上方无压力", 8: "分时站均价线上方",
        }
        for step in range(start_step, 9):
            self.log_filter("杨永兴", step, f"{step_names.get(step, '')}（前置淘汰）", 0, 0)

    def _build_candidates(self, stocks, financial_cache):
        """构建候选股列表（含SEPA基本面+杨永兴技术面数据）"""
        candidates = []
        for _, row in stocks.iterrows():
            code = str(row.get("code", ""))
            financial = financial_cache.get(code, {})

            def _float(val):
                try:
                    v = float(val)
                    return v if not (math.isnan(v) or math.isinf(v)) else None
                except:
                    return None

            candidate = {
                "code": code,
                "name": str(row.get("name", "")),
                "price": _float(row.get("price")),
                "change_pct": _float(row.get("change_pct")),
                # SEPA基本面
                "revenue_growth_yoy": financial.get("revenue_growth_yoy"),
                "profit_growth_yoy": financial.get("profit_growth_yoy"),
                "roe": financial.get("roe"),
                # 杨永兴技术面
                "volume_ratio": _float(row.get("volume_ratio")),
                "turnover_rate": _float(row.get("turnover_rate")),
                "circ_mv_billion": _float(row.get("circ_mv_billion")),
                "amplitude": _float(row.get("amplitude")),
                "pe": _float(row.get("pe")),
            }
            candidates.append(candidate)
        return candidates

    def _build_result(self, final_candidates, sepa_candidates,
                      market=None, market_status=None, warning=""):
        """构建最终返回结果"""
        return {
            "final_candidates": final_candidates,
            "sepa_candidates": sepa_candidates,
            "filter_log": self.filter_log,
            "market": market or {},
            "market_status": market_status or {},
            "scan_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_final": len(final_candidates),
            "total_sepa": len(sepa_candidates),
            "strategy": "SEPA+杨永兴",
            "warning": warning,
        }
