# 杨永兴短线战法 + SEPA策略 - A股选股辅助工具

> ⚠️ **免责声明**：本工具仅供学习研究，不构成任何投资建议。股市有风险，投资需谨慎。

基于游资大佬杨永兴"隔夜套利法" + 马克·米勒维尼《股票魔法师》SEPA策略的 A 股选股辅助系统，也是一个 [CodeBuddy Skill](https://skillhub.cn)。

## 核心策略

**先SEPA筛选基本面优质标的，再杨永兴寻找短线买点，双重验证提高确定性。**

### 杨永兴短线战法
- **买入**：14:30-14:50（尾盘30分钟）
- **卖出**：次日9:30-10:30（开盘1小时内）
- **持股时长**：严格 ≤ 2小时交易时间

### SEPA策略（米勒维尼《股票魔法师》）
- 营收增长 >25%、净利增长 >30%、ROE >15%
- 股价在MA50/MA150之上、量能放大
- 3年净利润CAGR >20%

## 九步过滤法

| 步骤 | 维度 | 标准 | 逻辑 |
|------|------|------|------|
| 1 | 排除ST/非主板 | 只留主板票 | 减少风险 |
| 2 | 涨幅范围 | 3%-5% | 盈利空间充足但不追高 |
| 3 | 涨停基因 | 近20天有涨停 | 主力活跃，有人气 |
| 4 | 量比 | ≥ 1 | 有资金关注 |
| 5 | 流通市值 | 50-200亿 | 盘子适中易撬动 |
| 6 | 换手率 | 5%-10% | 健康换手，非出货 |
| 7 | 振幅 | ≤ 8% | 波动适中 |
| 8 | K线形态 | 上方无压力，无长上影线 | 上涨阻力小 |
| 9 | 分时走势 | 全天站均价线上方 | 买方主导，主力护盘 |

## 快速开始

### 作为独立工具使用

```bash
# 1. 克隆项目
git clone https://github.com/chenhe81/yang-yongxing-strategy.git
cd yang-yongxing-strategy/scripts

# 2. 安装环境
python3 setup.py

# 3. 运行选股扫描（14:30后使用）
./venv/bin/python run.py scan

# 4. 快速扫描（跳过分时数据，更快）
./venv/bin/python run.py scan --skip-intraday
```

### 作为 CodeBuddy Skill 使用

1. 将项目复制到 `~/.codebuddy/skills/yang-yongxing-strategy/`
2. 在 CodeBuddy 对话中直接说"帮我扫描股票"即可触发
3. 或在 [SkillHub](https://skillhub.cn) 搜索安装

## 命令列表

```bash
cd scripts

# 联合扫描（推荐：SEPA基本面+杨永兴技术面，双战法验证）
./venv/bin/python run.py combined-scan [--skip-ma] [--skip-intraday] [--relax] [--openviking]

# 杨永兴选股扫描（14:30后使用）
./venv/bin/python run.py scan [--skip-intraday]

# SEPA策略选股扫描（基本面筛选）
./venv/bin/python run.py sepa-scan [--skip-ma]

# 启用OpenViking上下文管理（记忆+经验积累）
./venv/bin/python run.py combined-scan --openviking

# 卖出信号检查（次日9:35后使用）
./venv/bin/python run.py sell-check

# 查看持仓
./venv/bin/python run.py portfolio

# 添加持仓（买入后记录）
./venv/bin/python run.py add 000001 平安银行 15.50

# 移除持仓（卖出后清除）
./venv/bin/python run.py remove 000001

# 清空所有持仓
./venv/bin/python run.py clear

# 自选股管理
./venv/bin/python run.py watchlist
./venv/bin/python run.py watch-add 000001 平安银行
./venv/bin/python run.py watch-remove 000001
```

## 项目结构

```
yang-yongxing-strategy/
├── SKILL.md              # Skill 定义（知识+工作流）
├── LICENSE               # MIT 许可证 + 免责声明
├── README.md             # 本文件
├── .gitignore
├── references/
│   └── strategy-details.md   # 战法完整知识体系
└── scripts/
    ├── setup.py          # 一键安装脚本
    ├── config.py         # 参数配置
    ├── data_fetcher.py   # 数据获取层（腾讯/东方财富/新浪三源）
    ├── scanner.py        # 杨永兴九步过滤筛选引擎
    ├── sepa_filter.py    # SEPA七步基本面筛选引擎
    ├── combined_scanner.py # SEPA+杨永兴联合扫描引擎
    ├── openviking_adapter.py # OpenViking上下文管理适配层
    ├── openviking_init_knowledge.py # 策略知识导入脚本
    ├── sell_checker.py   # 卖出信号检查
    ├── portfolio.py      # 持仓跟踪管理
    ├── report.py         # 报告生成（含联合扫描报告）
    ├── run.py            # CLI 入口
    └── requirements.txt  # Python 依赖
```

## 卖出规则

| 开盘情况 | 操作 | 紧急程度 |
|---------|------|---------|
| 高开高走/平开高走/低开高走 | 破分时均价线或趋势线时卖 | 🟡 关注 |
| 平开平走/平开低走 | 破前低卖出 | 🟠 重要 |
| 高开低走/低开低走 | 破前低卖出 | 🔴 紧急 |
| 亏损 ≥ 3% | 止损卖出 | 🔴 重要 |
| 亏损 ≥ 5% | 强制止损 | ‼️ 极紧急 |

## 技术栈

- **数据源**：[akshare](https://github.com/akfamily/akshare) + 腾讯股票API（qt.gtimg.cn），三源自动切换
- **策略**：杨永兴短线战法 + 米勒维尼SEPA策略
- **上下文管理**：[OpenViking](https://github.com/volcengine/OpenViking)（可选，提供记忆和经验积累）
- **语言**：Python 3.9+
- **框架**：CodeBuddy Skill

## 致谢

本工具的选股逻辑源自杨永兴公开分享的短线战法，仅供学习研究。

## License

MIT License - 详见 [LICENSE](LICENSE)

⚠️ 本工具不构成任何投资建议，使用者需自行承担投资风险。
