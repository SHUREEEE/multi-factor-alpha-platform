# Elevator Pitch

## 30-Second English Version

I built an end-to-end US equity multi-factor research and risk-engineering
platform covering 2014 to 2024. It includes universe construction, data
cleaning, factor research, portfolio construction, T+1 backtesting,
risk-attribution diagnostics, and production-style launch gates. The point is
not to sell a finished high-Sharpe strategy. The v1 result is weak, with a 0.39
net Sharpe and high turnover, but the platform clearly diagnoses the leak:
about 0.46 cumulative return points of implementation drag between gross and
net PnL. I also added fail-closed attribution controls so the system refuses to
publish Barra-style claims without a valid market-cap panel.

## 90-Second English Version

This project is a full-stack quant research platform for US equity
multi-factor strategies. It starts with universe construction and data
engineering, builds reusable factor definitions, runs IC and Fama-MacBeth-style
research, combines selected signals, constructs a long-short portfolio, runs a
T+1 backtest, and then attempts Barra-style risk attribution.

The v1 strategy is intentionally presented honestly. It has a 0.39 net Sharpe,
4.54% annual return, 26.19% max drawdown, and 85.6x annual turnover. I do not
pitch that as investable. Instead, I use the platform to diagnose where the
strategy breaks: gross PnL sums to about 1.055, while net PnL sums to 0.595, so
the main issue is implementation drag in portfolio construction and trading.

The project also has a production-engineering track. V4 adds turnover-aware
construction, acceptance gates, risk controls, replay evidence, kill-switch
runbooks, PB borrow-feed validation boundaries, and a machine-readable launch
go/no-go guard. The local v4 acceptance gates pass, but live launch is still
blocked until a real PB borrow feed is wired and validated. That boundary is
important: I want the repo to show disciplined research and engineering
judgment, not just an optimized backtest.

## 90-Second Chinese Version

这个项目是一个端到端的美股多因子研究和风险工程平台，覆盖 2014 到 2024
年。它不是单个 notebook，而是一套完整 pipeline：股票池构建、数据清洗、
因子计算、因子研究、alpha 组合、组合构建、T+1 回测，以及 Barra-style 风险
归因诊断。

我不会把它包装成一个已经可以实盘的高 Sharpe 策略。v1 的结果其实偏弱：
净 Sharpe 是 0.39，年化收益 4.54%，最大回撤 26.19%，年化换手 85.6x。
但这正是项目有价值的地方：系统能把问题定位出来。gross PnL 大约是 1.055，
net PnL 是 0.595，中间大约 0.46 的累计收益差距主要来自组合构建和交易层的
implementation drag。

另一个重点是研究纪律。项目原本设计的是 sqrt(market_cap) 加权的
Barra-style 横截面回归归因，但当前 fundamentals 数据里没有可用的
market-cap panel。所以我没有用 equal-cap fallback 去冒充 Barra 结果，而是
让归因脚本默认 fail closed，并把旧归因结论 quarantine。

后面我又加了 v4 工程候选层，包括换手控制、acceptance gates、风险约束、
replay 证据、kill-switch runbook、PB borrow feed 校验边界和机器可读的
launch go/no-go。v4 本地工程门槛已经通过，但 live launch 仍然被真实 PB
借券数据卡住。我的定位不是说这个策略已经可交易，而是展示我能把一个量化
研究想法做成可复现、可诊断、能自我否定、也有生产边界意识的工程系统。
