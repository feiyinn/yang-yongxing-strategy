---
name: yang-yongxing-strategy
description: 杨永兴短线战法A股尾盘选股辅助工具。This skill should be used when the user asks about 杨永兴战法, 尾盘选股, 隔夜套利, T+1套利, 短线选股扫描, or needs to scan/filter A-share stocks based on Yang Yongxing's rules. Also triggers when the user wants stock analysis for next-day trading, sell signal checks, or portfolio tracking based on this specific short-term strategy.
---

# 杨永兴短线战法

## Overview

基于游资大佬杨永兴"隔夜套利法"的A股短线选股辅助系统。核心逻辑：**尾盘14:30买入，次日早盘10:30前卖出**，通过九步过滤法筛选高确定性标的，把T+1制度玩出T+0效果。提供选股扫描、卖出信号检查、持仓跟踪三大功能。

## 首次使用 - 环境安装

当用户首次使用本 Skill 时，执行以下安装步骤：

1. 确定 Skill 安装路径：
```bash
# Skill 安装在 ~/.codebuddy/skills/yang-yongxing-strategy/
SKILL_DIR="$HOME/.codebuddy/skills/yang-yongxing-strategy"
```

2. 创建 Python 虚拟环境并安装依赖：
```bash
cd "$SKILL_DIR/scripts"
python3 -m venv venv
./venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

3. 验证安装：
```bash
./venv/bin/python -c "import akshare; print(f'akshare {akshare.__version__} 安装成功')"
```

安装完成后，后续所有命令都在 `$SKILL_DIR/scripts` 目录下执行，使用 `./venv/bin/python` 运行。

## Workflow Decision Tree

```
用户触发场景
├── "扫描/选股/筛选股票" → 执行选股扫描流程
├── "卖出/卖出信号/该不该卖" → 执行卖出检查流程
├── "持仓/我的股票" → 查看持仓
├── "添加持仓/买入记录" → 记录持仓
├── "删除持仓/已卖出" → 移除持仓
├── "大盘/市场环境" → 分析大盘趋势
└── "战法/规则/杨永兴" → 讲解战法知识
```

## 核心交易规则

### 时间规则
- **买入时间**：14:30-14:50（尾盘30分钟）
- **卖出时间**：次日9:30-10:30（开盘1小时内）
- **持股时长**：严格≤2小时交易时间，绝不过夜

### 生死铁律
- 次日早盘必须清仓，除非缩量涨停或一字涨停
- 不要贪后续涨幅，"只赚属于我的那部分利润"
- 大盘放量大跌当日，直接空仓不操作

## 选股扫描流程

### 前置条件
- 确认当前为交易日且已过14:30
- 确认项目环境已就绪（akshare已安装）

### 执行步骤

1. 运行选股扫描脚本：
```bash
cd "$HOME/.codebuddy/skills/yang-yongxing-strategy/scripts"
./venv/bin/python run.py scan
```

如需快速扫描（跳过分时数据检查）：
```bash
./venv/bin/python run.py scan --skip-intraday
```

2. 解读扫描结果：
   - 查看大盘环境判断（趋势方向、是否放量大跌）
   - 查看九步过滤过程的淘汰情况
   - 关注最终候选股列表

3. 如果有候选股，根据三个买入时机给出建议：
   - **第一买点**：14:30左右股价创当日新高，大单拉升
   - **第二买点**：突破后回踩不破均价线，勾头向上
   - **第三买点**：突破短期前高

4. 用户决定买入后，记录持仓：
```bash
./venv/bin/python run.py add <代码> <名称> <买入价>
```

### 九步过滤法详解

执行扫描后，根据用户追问可详细解释每步逻辑（详见 `references/strategy-details.md`）：

| 步骤 | 维度 | 标准 | 逻辑 |
|------|------|------|------|
| 1 | 排除ST/非主板 | 只留主板票 | 减少风险 |
| 2 | 涨幅范围 | 3%-5% | 盈利空间充足但不追高 |
| 3 | 涨停基因 | 近20天有涨停 | 主力活跃，有人气 |
| 4 | 量比 | ≥1 | 有资金关注 |
| 5 | 流通市值 | 50-200亿 | 盘子适中易撬动 |
| 6 | 换手率 | 5%-10% | 健康换手，非出货 |
| 7 | 振幅 | ≤8% | 波动适中 |
| 8 | K线形态 | 上方无压力，无长上影线 | 上涨阻力小 |
| 9 | 分时走势 | 全天站均价线上方 | 买方主导，主力护盘 |

## 卖出信号检查流程

### 执行步骤

1. 运行卖出信号检查（次日9:35后）：
```bash
cd "$HOME/.codebuddy/skills/yang-yongxing-strategy/scripts"
./venv/bin/python run.py sell-check
```

2. 根据检查结果给出明确操作建议：

| 开盘情况 | 卖出标准 | 紧急程度 |
|---------|---------|---------|
| 高开高走/平开高走/低开高走 | 破分时均价线或趋势线时卖 | 🟡 关注 |
| 平开平走/平开低走 | 破前低卖出 | 🟠 重要 |
| 高开低走/低开低走 | 破前低卖出 | 🔴 紧急 |
| 亏损达3% | 止损卖出 | 🔴 重要 |
| 亏损达5% | 强制止损 | ‼️ 极紧急 |

3. 用户确认卖出后，清除持仓记录：
```bash
./venv/bin/python run.py remove <代码>
```

## 持仓管理

```bash
cd "$HOME/.codebuddy/skills/yang-yongxing-strategy/scripts"

# 查看当前持仓
./venv/bin/python run.py portfolio

# 添加持仓（买入后记录）
./venv/bin/python run.py add 000001 平安银行 15.50

# 移除持仓（卖出后清除）
./venv/bin/python run.py remove 000001

# 清空所有持仓
./venv/bin/python run.py clear
```

## 仓位管理原则

| 情况 | 仓位 |
|------|------|
| 看不懂 | 坚决空仓 |
| 半懂 | 分仓2-3只 |
| 看懂 | 重仓但≤50% |

- 单票仓位 ≤ 总资金20%
- 每日操作 ≤ 3笔
- 单次目标收益1%-3%，复利积累

## 战法深层心法

当用户问及战法背后的逻辑时，参考 `references/strategy-details.md` 进行讲解：

1. **核心思路**：趋势投机 + 事件驱动
2. **三大要诀**：看准大市 > 控制仓位 > 操盘技巧
3. **判断大市**：自下而上，从龙头股看板块，从板块看大盘
4. **操作精髓**：等待、发现、跟随——长时间持币，短时间持股
5. **提前量思维**：考虑对手在想什么，将要做什么，早他一步
6. **短线也看基本面**：从公告、券商研报中掘金

## 大盘环境判断

当用户问大盘时，运行：
```bash
cd "$HOME/.codebuddy/skills/yang-yongxing-strategy/scripts"
./venv/bin/python -c "
from data_fetcher import get_market_trend, get_market_status
import json
trend = get_market_trend()
status = get_market_status()
print(json.dumps({**trend, **status}, ensure_ascii=False, default=str, indent=2))
"
```

根据结果判断：
- trend=up + 非放量大跌 → 可操作，仓位根据趋势强度调整
- trend=down 或 is_crash=True → 空仓观望

## Important Notes

- ⚠️ **免责声明**：本工具仅供学习研究，不构成任何投资建议。股市有风险，投资需谨慎。
- 战法依赖盘中数据，非交易日运行可能获取不到实时行情
- 分时数据获取较慢，如候选股不多可用完整扫描；候选股多时建议 `--skip-intraday` 先快速筛选
- 量化时代很多超短线已被程序化交易取代，战法有效性需持续验证
