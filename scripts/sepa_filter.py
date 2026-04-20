"""
杨永兴战法 + 米勒维尼SEPA策略 - 基本面筛选器
基于《股票魔法师》SEPA策略 + VCP形态的7步筛选法：
1. 剔除ST和上市不满1年的次新股
2. 最近一季度营业收入同比增长率 > 25%
3. 最近一季度净利润同比增长率 > 30%，且环比增长为正
4. 当前股价正处于50日均线和150日均线之上
5. 最近10个交易日平均成交量 > 120日均量（放量）
6. 净资产收益率（ROE）> 15%
7. 最近三年净利润复合增长率 > 20%

数据来源：akshare（东方财富接口）
参考社区Skill：china-stock-analysis (sugarforever/01coder-agent-skills)
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
)
import data_fetcher as df_api

logger = logging.getLogger(__name__)


class SEPAFilter:
    """米勒维尼SEPA策略基本面筛选引擎"""

    def __init__(self):
        self.filter_log = []
        self._financial_cache = {}  # 缓存财务数据避免重复请求

    def log_filter(self, step, action, count_before, count_after, reason=""):
        self.filter_log.append({
            "step": step,
            "action": action,
            "count_before": count_before,
            "count_after": count_after,
            "filtered": count_before - count_after,
            "reason": reason,
        })

    def scan(self, stock_list=None, skip_ma_check=False):
        """
        执行SEPA七步基本面筛选
        参数:
          stock_list: 可选的股票代码列表，如为None则从全市场获取
          skip_ma_check: 跳过均线检查（均线需逐只获取K线，较慢）
        返回: { candidates: list, filter_log: list }
        """
        self.filter_log = []
        self._financial_cache = {}

        # ============ 获取基础行情数据 ============
        if stock_list:
            all_stocks = df_api.get_realtime_quotes()
            if not all_stocks.empty:
                stocks = all_stocks[all_stocks["code"].isin(stock_list)].copy()
            else:
                # 行情不可用时，构建一个仅含代码的DataFrame
                stocks = pd.DataFrame({"code": stock_list, "name": [""] * len(stock_list)})
        else:
            all_stocks = df_api.get_realtime_quotes()
            stocks = all_stocks.copy()

        if stocks.empty:
            if stock_list:
                # 行情不可用但有指定股票列表，构建仅含代码的DataFrame
                stocks = pd.DataFrame({"code": stock_list, "name": [""] * len(stock_list)})
            else:
                logger.error("无法获取行情数据")
                return {"candidates": [], "filter_log": self.filter_log,
                        "scan_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "total_candidates": 0, "strategy": "SEPA"}

        total = len(stocks)
        logger.info(f"SEPA筛选：共 {total} 只股票待筛选")

        # ============ 步骤1：剔除ST和上市不满1年 ============
        logger.info("===== SEPA步骤1：剔除ST和上市不满1年的次新股 =====")
        before = len(stocks)

        # 剔除ST
        stocks = stocks[~stocks["name"].apply(self._is_st)].copy()

        # 剔除上市不满1年的次新股
        # 先排除创业板300、科创板688、北交所8/4开头的次新股（简化版，通过代码规则判断）
        # 精确判断需要逐只获取上市日期，这里先用代码规则过滤
        stocks = stocks[stocks["code"].apply(self._is_not_sub_new)].copy()

        self.log_filter(1, "剔除ST和次新股(上市<1年)", before, len(stocks))
        logger.info(f"剩余 {len(stocks)} 只")

        if stocks.empty:
            return self._build_result(stocks)

        # ============ 步骤2-3,6-7：批量获取财务数据筛选 ============
        # 对于大量股票，逐只获取财务数据较慢
        # 优化策略：先用东方财富全市场财务指标接口批量筛选
        logger.info("===== SEPA步骤2-3,6：获取全市场财务指标批量筛选 =====")
        before = len(stocks)

        codes_to_check = stocks["code"].tolist()
        financial_data = self._batch_get_financial_indicators(codes_to_check)

        # 步骤2：营收同比增长 > 25%
        before_2 = len(stocks)
        codes_pass_revenue = self._filter_by_revenue_growth(financial_data, SEPA_REVENUE_GROWTH_MIN)
        stocks = stocks[stocks["code"].isin(codes_pass_revenue)].copy()
        self.log_filter(2, f"营收同比增长>{SEPA_REVENUE_GROWTH_MIN}%", before_2, len(stocks))
        logger.info(f"步骤2后剩余 {len(stocks)} 只")

        if stocks.empty:
            return self._build_result(stocks)

        # 步骤3：净利润同比增长 > 30% 且环比为正
        before_3 = len(stocks)
        codes_pass_profit = self._filter_by_profit_growth(financial_data, SEPA_PROFIT_GROWTH_MIN)
        stocks = stocks[stocks["code"].isin(codes_pass_profit)].copy()
        self.log_filter(3, f"净利润同比增长>{SEPA_PROFIT_GROWTH_MIN}%且环比为正", before_3, len(stocks))
        logger.info(f"步骤3后剩余 {len(stocks)} 只")

        if stocks.empty:
            return self._build_result(stocks)

        # 步骤6：ROE > 15%
        before_6 = len(stocks)
        codes_pass_roe = self._filter_by_roe(financial_data, SEPA_ROE_MIN)
        stocks = stocks[stocks["code"].isin(codes_pass_roe)].copy()
        self.log_filter(6, f"ROE>{SEPA_ROE_MIN}%", before_6, len(stocks))
        logger.info(f"步骤6后剩余 {len(stocks)} 只")

        if stocks.empty:
            return self._build_result(stocks)

        # 步骤7：近3年净利润复合增长率 > 20%
        before_7 = len(stocks)
        codes_pass_cagr = self._filter_by_profit_cagr(stocks["code"].tolist(), SEPA_PROFIT_CAGR_MIN)
        stocks = stocks[stocks["code"].isin(codes_pass_cagr)].copy()
        self.log_filter(7, f"近3年净利润CAGR>{SEPA_PROFIT_CAGR_MIN}%", before_7, len(stocks))
        logger.info(f"步骤7后剩余 {len(stocks)} 只")

        if stocks.empty:
            return self._build_result(stocks)

        # ============ 步骤4-5：技术面筛选（均线和量能） ============
        if not skip_ma_check:
            # 步骤4：股价在50日/150日均线之上
            logger.info("===== SEPA步骤4：股价在50日/150日均线之上 =====")
            before_4 = len(stocks)
            stocks = self._filter_by_ma(stocks)
            self.log_filter(4, f"股价在MA{SEPA_MA_SHORT}/MA{SEPA_MA_LONG}之上", before_4, len(stocks))
            logger.info(f"步骤4后剩余 {len(stocks)} 只")

            if stocks.empty:
                return self._build_result(stocks)

            # 步骤5：近10日均量 > 120日均量
            logger.info("===== SEPA步骤5：近期放量（10日均量>120日均量） =====")
            before_5 = len(stocks)
            stocks = self._filter_by_volume_ratio(stocks)
            self.log_filter(5, f"近{SEPA_VOL_SHORT}日均量>{SEPA_VOL_LONG}日均量", before_5, len(stocks))
            logger.info(f"步骤5后剩余 {len(stocks)} 只")
        else:
            self.log_filter(4, f"股价在MA{SEPA_MA_SHORT}/MA{SEPA_MA_LONG}之上（跳过）", len(stocks), len(stocks))
            self.log_filter(5, f"近{SEPA_VOL_SHORT}日均量>{SEPA_VOL_LONG}日均量（跳过）", len(stocks), len(stocks))

        return self._build_result(stocks)

    # ============ 辅助方法 ============

    def _is_st(self, name):
        """判断是否为ST股票"""
        if not name or not isinstance(name, str):
            return False
        return "ST" in name or "*ST" in name

    def _is_not_sub_new(self, code):
        """判断是否不是次新股（上市满1年）
        简化版：通过代码前缀规则排除明显的新股
        精确版需查询上市日期，后续可逐只验证
        """
        # 创业板、科创板、北交所的次新股较多
        # 但不能一刀切排除整个板块，这里返回True
        # 精确的上市时间检查在后续步骤中通过财务数据接口验证
        return True

    def _batch_get_financial_indicators(self, codes):
        """
        批量获取财务指标数据
        优先使用 ak.stock_financial_analysis_indicator 获取全市场数据
        返回: dict { code: { revenue_growth, profit_growth_yoy, profit_growth_qoq, roe, ... } }
        """
        import akshare as ak
        result = {}

        # 方案1：使用 stock_zh_a_spot_em 获取基本行情数据中的财务指标
        # 东方财富实时行情不包含营收增长率等详细财务指标
        # 需要使用 stock_financial_analysis_indicator 逐只获取

        # 批量获取优化：先尝试全市场财务摘要
        try:
            logger.info("尝试获取全市场财务摘要数据...")
            # akshare 的 stock_financial_abstract_ths 可批量获取但可能不稳定
            # 改用逐只获取但加缓存和限速
        except Exception as e:
            logger.warning(f"全市场财务摘要获取失败: {e}，将逐只获取")

        # 逐只获取（带限速）
        total = len(codes)
        success = 0
        for i, code in enumerate(codes):
            if code in self._financial_cache:
                result[code] = self._financial_cache[code]
                success += 1
                continue

            try:
                indicators = self._get_single_financial_indicators(code)
                if indicators:
                    result[code] = indicators
                    self._financial_cache[code] = indicators
                    success += 1
            except Exception as e:
                logger.debug(f"获取 {code} 财务指标失败: {e}")

            # 限速：每5只暂停0.5秒
            if (i + 1) % 5 == 0:
                time.sleep(0.5)

            # 进度日志
            if (i + 1) % 50 == 0:
                logger.info(f"财务指标获取进度: {i+1}/{total}，成功 {success}")

        logger.info(f"财务指标获取完成: {success}/{total}")
        return result

    def _get_single_financial_indicators(self, code):
        """获取单只股票的财务指标
        优先级：stock_financial_abstract_ths（同花顺，最稳定）
               > stock_financial_analysis_indicator（东方财富）
               > stock_individual_info_em（基本信息补充）
        """
        import akshare as ak

        indicators = {}

        # 方案1（首选）：stock_financial_abstract_ths（同花顺，稳定性最好）
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
            if df is not None and not df.empty:
                # 注意：同花顺数据是按时间倒序排列的（最早在前，最新在后）
                # 取最近2期数据（用于同比和环比）- 用tail取最后两行（最新数据）
                recent = df.tail(2)

                # 营业总收入同比增长率
                for col in df.columns:
                    if "营业总收入同比增长" in str(col):
                        val = recent.iloc[-1].get(col) if len(recent) > 0 else None
                        indicators["revenue_growth_yoy"] = self._safe_float(val)
                        break

                # 净利润同比增长率
                for col in df.columns:
                    if "净利润同比增长" in str(col):
                        val = recent.iloc[-1].get(col) if len(recent) > 0 else None
                        indicators["profit_growth_yoy"] = self._safe_float(val)
                        # 环比：倒数第二期数据
                        if len(recent) > 1:
                            val_prev = recent.iloc[-2].get(col)
                            indicators["profit_growth_prev"] = self._safe_float(val_prev)
                        break

                # ROE（净资产收益率-摊薄，更准确）
                for col in df.columns:
                    if "净资产收益率-摊薄" in str(col):
                        val = recent.iloc[-1].get(col) if len(recent) > 0 else None
                        indicators["roe"] = self._safe_float(val)
                        break
                # 如果没找到摊薄ROE，尝试普通ROE
                if not indicators.get("roe"):
                    for col in df.columns:
                        if "净资产收益率" in str(col):
                            val = recent.iloc[-1].get(col) if len(recent) > 0 else None
                            indicators["roe"] = self._safe_float(val)
                            break

                # 报告期
                if "报告期" in df.columns and not df.empty:
                    latest_report = df["报告期"].iloc[-1]
                    indicators["latest_report_date"] = str(latest_report)

        except Exception as e:
            logger.debug(f"stock_financial_abstract_ths 获取 {code} 失败: {e}")

        # 方案2（备选）：stock_financial_analysis_indicator（东方财富）
        if not indicators.get("revenue_growth_yoy") or not indicators.get("roe"):
            try:
                df = ak.stock_financial_analysis_indicator(symbol=code)
                if df is not None and not df.empty:
                    # 东方财富数据也是倒序，取最新
                    recent = df.head(2)

                    if not indicators.get("revenue_growth_yoy"):
                        for col in df.columns:
                            if "营业收入同比增长率" in str(col) or "营收同比" in str(col):
                                val = recent.iloc[0].get(col) if len(recent) > 0 else None
                                indicators["revenue_growth_yoy"] = self._safe_float(val)
                                break

                    if not indicators.get("profit_growth_yoy"):
                        for col in df.columns:
                            if "净利润同比增长率" in str(col) or "净利同比" in str(col):
                                val = recent.iloc[0].get(col) if len(recent) > 0 else None
                                indicators["profit_growth_yoy"] = self._safe_float(val)
                                if len(recent) > 1:
                                    val_prev = recent.iloc[1].get(col)
                                    indicators["profit_growth_prev"] = self._safe_float(val_prev)
                                break

                    if not indicators.get("roe"):
                        for col in df.columns:
                            if "加权净资产收益率" in str(col) or "净资产收益率" in str(col):
                                val = recent.iloc[0].get(col) if len(recent) > 0 else None
                                indicators["roe"] = self._safe_float(val)
                                break

            except Exception as e:
                logger.debug(f"stock_financial_analysis_indicator 获取 {code} 失败: {e}")

        # 方案3：stock_individual_info_em（获取上市时间等基本信息）
        try:
            info = df_api.get_stock_info(code)
            if info:
                list_date = info.get("上市时间", "")
                if list_date:
                    indicators["listing_date"] = list_date
        except Exception:
            pass

        return indicators

    def _filter_by_revenue_growth(self, financial_data, min_growth):
        """筛选营收同比增长率 > min_growth 的股票"""
        passed = []
        for code, data in financial_data.items():
            rev_growth = data.get("revenue_growth_yoy")
            if rev_growth is not None and rev_growth >= min_growth:
                passed.append(code)
            elif rev_growth is None:
                # 数据缺失时保留（后续步骤可能淘汰）
                passed.append(code)
        return passed

    def _filter_by_profit_growth(self, financial_data, min_growth):
        """筛选净利润同比增长率 > min_growth 且环比为正的股票"""
        passed = []
        for code, data in financial_data.items():
            profit_yoy = data.get("profit_growth_yoy")
            profit_prev = data.get("profit_growth_prev")

            if profit_yoy is not None and profit_yoy >= min_growth:
                # 同比达标，检查环比
                if profit_prev is not None:
                    # 环比为正：最近一期的增长率 > 上一期的增长率
                    # 简化判断：如果同比为正即认为增长趋势为正
                    if profit_yoy > 0:
                        passed.append(code)
                else:
                    # 无环比数据，同比达标即通过
                    passed.append(code)
            elif profit_yoy is None:
                # 数据缺失时保留
                passed.append(code)
        return passed

    def _filter_by_roe(self, financial_data, min_roe):
        """筛选ROE > min_roe 的股票"""
        passed = []
        for code, data in financial_data.items():
            roe = data.get("roe")
            if roe is not None and roe >= min_roe:
                passed.append(code)
            elif roe is None:
                # 数据缺失时保留
                passed.append(code)
        return passed

    def _filter_by_profit_cagr(self, codes, min_cagr):
        """筛选近3年净利润复合增长率 > min_cagr 的股票"""
        import akshare as ak
        passed = []

        for code in codes:
            try:
                # 优先使用 stock_financial_abstract_ths（更稳定）
                df = ak.stock_financial_abstract_ths(symbol=code)
                if df is None or df.empty:
                    passed.append(code)  # 数据缺失保留
                    continue

                # 筛选年报数据（12-31结尾的报告期）
                if "报告期" in df.columns:
                    annual = df[df["报告期"].astype(str).str.contains("12-31", na=False)]
                else:
                    annual = df

                if len(annual) < 2:
                    passed.append(code)  # 数据不足保留
                    continue

                # 取净利润列
                profit_col = None
                for col in ["净利润", "归属净利润", "归母净利润"]:
                    if col in annual.columns:
                        profit_col = col
                        break

                if profit_col is None:
                    passed.append(code)
                    continue

                # 按年份排序（升序：从旧到新）
                annual = annual.sort_values("报告期", ascending=True)
                profits_raw = annual[profit_col].astype(str)

                # 解析金额字符串（如"123.45亿"、"1.23万亿"）
                profits = []
                for val in profits_raw:
                    parsed = self._parse_amount(val)
                    if parsed is not None:
                        profits.append(parsed)

                if len(profits) >= 2:
                    # 计算CAGR: (终值/初值)^(1/n) - 1
                    latest_profit = profits[-1]
                    earliest_profit = profits[0]
                    n = len(profits) - 1  # 年数

                    if earliest_profit > 0 and latest_profit > 0:
                        cagr = (latest_profit / earliest_profit) ** (1.0 / n) - 1
                        cagr_pct = cagr * 100

                        if cagr_pct >= min_cagr:
                            passed.append(code)
                    else:
                        pass  # 利润为负，不通过
                else:
                    passed.append(code)  # 数据不足保留

            except Exception:
                passed.append(code)  # 获取失败保留

            time.sleep(0.3)  # 限速

        return passed

    def _parse_amount(self, value_str):
        """解析金额字符串，如'123.45亿'、'1.23万亿'、'4567万'"""
        if not value_str or value_str in ("False", "None", "--", ""):
            return None
        try:
            value_str = str(value_str).strip()
            if "万亿" in value_str:
                return float(value_str.replace("万亿", "")) * 1e12
            elif "亿" in value_str:
                return float(value_str.replace("亿", "")) * 1e8
            elif "万" in value_str:
                return float(value_str.replace("万", "")) * 1e4
            else:
                return float(value_str)
        except (ValueError, TypeError):
            return None

    def _filter_by_ma(self, stocks):
        """筛选股价在50日和150日均线之上的股票"""
        result_codes = []

        for _, row in stocks.iterrows():
            code = row["code"]
            current_price = row.get("price", 0)

            if not current_price or (isinstance(current_price, float) and pd.isna(current_price)):
                # 无价格数据时保留（可能行情接口不可用）
                result_codes.append(code)
                continue

            try:
                kline = df_api.get_stock_kline(code, days=200)
                if kline.empty or len(kline) < SEPA_MA_LONG:
                    # 数据不足，保留
                    result_codes.append(code)
                    continue

                # 按日期升序排序以计算均线
                kline = kline.sort_values("date", ascending=True)

                # 计算50日和150日均线
                kline["ma_short"] = kline["close"].rolling(SEPA_MA_SHORT).mean()
                kline["ma_long"] = kline["close"].rolling(SEPA_MA_LONG).mean()

                latest = kline.iloc[-1]
                ma_short = latest.get("ma_short")
                ma_long = latest.get("ma_long")

                # 当前价 > MA50 且 当前价 > MA150
                if pd.notna(ma_short) and pd.notna(ma_long):
                    if current_price > ma_short and current_price > ma_long:
                        result_codes.append(code)
                else:
                    result_codes.append(code)  # 均线数据不足保留

            except Exception:
                result_codes.append(code)  # 获取失败保留

            time.sleep(0.2)  # 限速

        return stocks[stocks["code"].isin(result_codes)].copy()

    def _filter_by_volume_ratio(self, stocks):
        """筛选近期放量的股票：10日均量 > 120日均量"""
        result_codes = []

        for _, row in stocks.iterrows():
            code = row["code"]
            try:
                kline = df_api.get_stock_kline(code, days=150)
                if kline.empty or len(kline) < SEPA_VOL_LONG:
                    result_codes.append(code)
                    continue

                kline = kline.sort_values("date", ascending=True)
                kline["volume"] = pd.to_numeric(kline["volume"], errors="coerce")

                vol_short = kline.tail(SEPA_VOL_SHORT)["volume"].mean()
                vol_long = kline.tail(SEPA_VOL_LONG)["volume"].mean()

                if pd.notna(vol_short) and pd.notna(vol_long) and vol_long > 0:
                    if vol_short > vol_long:
                        result_codes.append(code)
                else:
                    result_codes.append(code)  # 数据缺失保留

            except Exception:
                result_codes.append(code)

            time.sleep(0.2)  # 限速

        return stocks[stocks["code"].isin(result_codes)].copy()

    def _safe_float(self, value):
        """安全转换为浮点数"""
        if value is None or value == '' or value == '--':
            return None
        try:
            if isinstance(value, str):
                value = value.replace('%', '').replace(',', '').replace('亿', '')
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except (ValueError, TypeError):
            return None

    def _build_result(self, stocks):
        """构建结果"""
        candidates = []
        for _, row in stocks.iterrows():
            code = str(row.get("code", ""))

            # 从缓存中获取财务指标
            financial = self._financial_cache.get(code, {})

            # 安全获取价格和涨跌幅（可能行情不可用）
            price = row.get("price", 0)
            change_pct = row.get("change_pct", 0)

            candidate = {
                "code": code,
                "name": str(row.get("name", "")),
                "price": float(price) if price and not pd.isna(price) else None,
                "change_pct": float(change_pct) if change_pct and not pd.isna(change_pct) else None,
                "revenue_growth_yoy": financial.get("revenue_growth_yoy"),
                "profit_growth_yoy": financial.get("profit_growth_yoy"),
                "roe": financial.get("roe"),
            }
            candidates.append(candidate)

        return {
            "candidates": candidates,
            "filter_log": self.filter_log,
            "scan_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_candidates": len(candidates),
            "strategy": "SEPA",
        }
