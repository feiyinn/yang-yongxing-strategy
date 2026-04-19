"""
杨永兴短线战法 - 报告生成
"""

import os
import json
import datetime
import numpy as np
from config import REPORTS_DIR


class NumpyEncoder(json.JSONEncoder):
    """处理numpy类型的JSON编码器"""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def generate_scan_report(scan_result):
    """生成选股扫描报告"""
    candidates = scan_result.get("candidates", [])
    market = scan_result.get("market", {})
    filter_log = scan_result.get("filter_log", [])
    scan_time = scan_result.get("scan_time", "")

    lines = []
    lines.append("=" * 70)
    lines.append("📊 杨永兴短线战法 - 尾盘选股扫描报告")
    lines.append(f"📅 扫描时间：{scan_time}")
    lines.append("=" * 70)

    # 大盘环境
    lines.append("\n📈 大盘环境")
    lines.append("-" * 40)
    trend = market.get("trend", "unknown")
    trend_emoji = {"up": "🟢 上升", "down": "🔴 下降", "flat": "🟡 横盘"}.get(trend, "⚪ 未知")
    lines.append(f"  趋势：{trend_emoji}")
    if market.get("change_pct") is not None:
        lines.append(f"  涨跌幅：{market['change_pct']:.2f}%")
    if market.get("is_crash"):
        lines.append("  ⚠️ 大盘放量大跌，建议空仓！")

    # 过滤步骤
    if filter_log:
        lines.append("\n🔍 筛选过程")
        lines.append("-" * 40)
        for log in filter_log:
            filtered = log.get("filtered", 0)
            lines.append(
                f"  步骤{log['step']}：{log['action']} → "
                f"过滤 {filtered} 只，剩余 {log['count_after']} 只"
            )

    # 候选股
    if not candidates:
        lines.append("\n❌ 今日无符合条件的候选股")
    else:
        lines.append(f"\n✅ 符合条件的候选股（共{len(candidates)}只）")
        lines.append("=" * 70)
        lines.append(
            f"{'序号':<4} {'代码':<8} {'名称':<10} {'现价':<8} "
            f"{'涨幅%':<8} {'量比':<6} {'换手%':<8} {'流通市值(亿)':<12}"
        )
        lines.append("-" * 70)
        for i, c in enumerate(candidates, 1):
            lines.append(
                f"{i:<4} {c.get('code', ''):<8} {c.get('name', ''):<10} "
                f"{c.get('price', 0):<8.2f} {c.get('change_pct', 0):<8.2f} "
                f"{c.get('volume_ratio', 0):<6.2f} {c.get('turnover_rate', 0):<8.2f} "
                f"{c.get('circ_mv_billion', 0):<12.1f}"
            )
        lines.append("-" * 70)

        # 操作建议
        lines.append("\n💡 操作建议")
        lines.append("-" * 40)
        lines.append("  1. 14:30-14:50 观察候选股走势")
        lines.append("  2. 重点关注：创新高大单拉升 → 第一买点")
        lines.append("  3. 回踩不破均价线勾头向上 → 第二买点")
        lines.append("  4. 突破短期前高 → 第三买点")
        lines.append("  5. ⚠️ 次日早盘10:30前必须清仓！")

    # 存量提示
    lines.append("\n" + "=" * 70)
    lines.append("⚠️ 免责声明：本报告仅供学习研究，不构成投资建议。")
    lines.append("=" * 70)

    report_text = "\n".join(lines)

    # 保存到文件
    today = datetime.date.today().strftime("%Y%m%d")
    filepath = os.path.join(REPORTS_DIR, f"scan_{today}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 同时保存JSON数据
    json_filepath = os.path.join(REPORTS_DIR, f"scan_{today}.json")
    with open(json_filepath, "w", encoding="utf-8") as f:
        json.dump(scan_result, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)

    return report_text, filepath


def generate_sell_report(sell_result):
    """生成卖出信号报告"""
    signals = sell_result.get("signals", [])
    check_time = sell_result.get("check_time", "")

    lines = []
    lines.append("=" * 70)
    lines.append("🔔 杨永兴短线战法 - 次日卖出信号检查")
    lines.append(f"📅 检查时间：{check_time}")
    lines.append("=" * 70)

    if not signals:
        lines.append("\n📋 当前无持仓，无需检查")
    else:
        sell_signals = [s for s in signals if s.get("action") == "sell"]
        watch_signals = [s for s in signals if s.get("action") == "watch"]
        hold_signals = [s for s in signals if s.get("action") == "hold"]

        # 需要卖出的
        if sell_signals:
            lines.append(f"\n🔴 需要卖出（{len(sell_signals)}只）")
            lines.append("-" * 60)
            for s in sell_signals:
                urgency = {"critical": "‼️紧急", "urgent": "⚠️重要", "normal": "📌普通"}.get(
                    s.get("urgency", "normal"), "📌普通"
                )
                profit = s.get("profit_pct", "")
                profit_str = f"（盈亏 {profit:+.2f}%）" if isinstance(profit, (int, float)) else ""
                lines.append(f"  {urgency} {s.get('code', '')} {s.get('name', '')}{profit_str}")
                lines.append(f"       原因：{s.get('reason', '')}")
                lines.append(f"       现价：{s.get('current_price', 0):.2f}  开盘类型：{s.get('open_type', '')}")

        # 需要观察的
        if watch_signals:
            lines.append(f"\n🟡 需要观察（{len(watch_signals)}只）")
            lines.append("-" * 60)
            for s in watch_signals:
                profit = s.get("profit_pct", "")
                profit_str = f"（盈亏 {profit:+.2f}%）" if isinstance(profit, (int, float)) else ""
                lines.append(f"  📌 {s.get('code', '')} {s.get('name', '')}{profit_str}")
                lines.append(f"       {s.get('reason', '')}")

        # 继续持有的
        if hold_signals:
            lines.append(f"\n🟢 继续持有观察（{len(hold_signals)}只）")
            lines.append("-" * 60)
            for s in hold_signals:
                profit = s.get("profit_pct", "")
                profit_str = f"（盈亏 {profit:+.2f}%）" if isinstance(profit, (int, float)) else ""
                lines.append(f"  📌 {s.get('code', '')} {s.get('name', '')}{profit_str}")
                lines.append(f"       {s.get('reason', '')}")

    lines.append("\n" + "=" * 70)
    lines.append("⚠️ 铁律：次日早盘必须清仓，除非缩量涨停或一字涨停！")
    lines.append("=" * 70)

    report_text = "\n".join(lines)

    # 保存
    today = datetime.date.today().strftime("%Y%m%d")
    filepath = os.path.join(REPORTS_DIR, f"sell_{today}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)

    json_filepath = os.path.join(REPORTS_DIR, f"sell_{today}.json")
    with open(json_filepath, "w", encoding="utf-8") as f:
        json.dump(sell_result, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)

    return report_text, filepath
