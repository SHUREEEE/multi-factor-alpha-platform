# Elevator Pitch

## 30-Second English Version

I built a multi-factor US equity research platform covering 2014 to 2024,
organized as seven pillars from universe construction through Barra-style risk
attribution. The interesting part is not a hero Sharpe. The v1 net Sharpe is
only 0.39. The interesting part is what the platform exposes: roughly 0.46
cumulative implementation drag between gross and net PnL, and a fail-closed
attribution layer that refuses to publish a Barra report when the market-cap
panel is missing. I treat it as a research-discipline and risk-engineering
project, not as a finished alpha product.

## 90-Second English Version

This project is an end-to-end multi-factor US equity research platform. It
starts with universe and data engineering, builds reusable factor definitions,
runs IC and Fama-MacBeth style research, combines selected signals, constructs
a long-short portfolio, backtests it with T+1 alignment, and then attempts
Barra-style risk attribution.

The main result is intentionally modest. The v1 strategy has a 0.39 net Sharpe,
4.54% annual return, 26.19% max drawdown, and 85.6x annual turnover. I did not
try to hide that. Instead, I used the system to diagnose where the result
breaks down. Gross PnL sums to about 1.055, while net PnL sums to 0.595, so
the main leak is implementation drag in portfolio construction and trading.

The project also has a strong research-control story. The attribution layer is
designed to use sqrt-market-cap weighted cross-sectional regressions, but the
current local fundamentals panel does not contain usable market caps. Rather
than silently falling back to equal weights and calling it Barra-style, the
pipeline now fails closed and quarantines that attribution claim. So the story
is not that v1 is an investable strategy. The story is that the platform can
separate gross signal, implementation cost, data limitations, and unsupported
claims in a reproducible way.

## 90-Second Chinese Version

这个项目是一个端到端的美股多因子研究平台，覆盖 2014 到 2024 年。结构上分成七层：股票池和数据工程、因子库、因子研究、alpha 组合、组合构建、T+1 回测，以及 Barra-style 风险归因。

我不会把它包装成一个高 Sharpe 策略。v1 的净 Sharpe 只有 0.39，年化收益 4.54%，最大回撤 26.19%，年化换手 85.6x。这个结果本身偏弱，但项目的价值在于它能把问题定位清楚：gross PnL 大约是 1.055，net PnL 是 0.595，中间 0.46 的累计差距主要来自组合构建和交易层的 implementation drag。

另一个重点是归因纪律。项目原本设计的是 sqrt(market_cap) 加权的 Barra-style 横截面回归，但当前 fundamentals 数据里没有可用的 market-cap panel。所以我没有用 equal-weight fallback 冒充 Barra 结果，而是让归因脚本默认 fail closed，并把旧归因结论 quarantine。我的定位不是说 v1 已经可实盘，而是展示一个可复现、能自我否定、能暴露数据和实现问题的量化研究平台。
