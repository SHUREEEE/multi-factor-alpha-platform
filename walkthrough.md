# Pillar 2 Factor Library Walkthrough

## 验收口径

- 输出文件：`data/factor_data/factors.parquet`。
- 兼容文件：`data/factor_data/all_factors.parquet`，保留给现有 research 脚本使用。
- 索引：所有因子使用 long format，`MultiIndex(date, ticker)`。
- 去重：保存前检查不能有重复 `(date, ticker)`。
- 非空性：保存前检查至少大部分日期有可用因子值。
- 防 look-ahead：最终保存前统一按 ticker 做 `shift(1)`，让 T 日信号只能从 T+1 开始用于交易。
- 低 beta 的 market proxy：如果传入 `market_returns` 就用外部市场收益；否则用当前股票池的等权平均收益作为 fallback。

## Momentum.py 三层解释

### Level 1：三个 momentum 因子在做什么

`Momentum12_1` 衡量股票过去约 12 个月的中期涨幅，但故意跳过最近 1 个月。经济逻辑是：中期赢家往往继续强，短期最近一个月却容易反转，所以要排除。

`ShortTermReversal` 衡量过去 1 个月收益的反方向。过去 1 个月跌得多，因子分数更高；过去 1 个月涨得多，因子分数更低。经济逻辑是短期价格冲击、流动性压力或过度反应可能回撤。

`Week52High` 衡量当前复权价离过去 52 周高点有多近。越接近 52 周高点，说明趋势和市场关注度越强，因子分数越高。

### Level 2：实现选择

`252` 约等于一年交易日数量，常用于 12 个月动量和 52 周高点。它不是日历天，而是交易日近似。

`126` 约等于半年交易日数量，用作 52 周高点的 `min_periods`。如果一只股票刚进入样本，不要求完整一年，但至少要半年数据才认为 rolling high 有意义。

`21` 约等于一个月交易日数量。`Momentum12_1` 使用 `pct_change(252).shift(21)`，明确跳过最近 21 个交易日；`ShortTermReversal` 使用 `pct_change(21)` 得到最近一个月收益。

look-ahead 主要在两处防止：第一，`Momentum12_1` 通过 `.shift(21)` 排除最近一个月；第二，`compute_all_factors.py` 在保存最终因子前统一 `groupby(level="ticker").shift(1)`，避免用当日收盘后才知道的信息做当日交易。

`st_reversal_1m` 使用负号，是因为因子方向要统一成“分数越高越看多”。如果过去一个月收益很差，短期反转假设认为未来可能修复，所以 `-past_1m_return` 会给它更高分。

`winsorize -> neutralize -> zscore` 不能反。先 winsorize 是为了防止极端值污染 OLS 中性化回归；再 neutralize 是为了去掉行业和规模等系统暴露；最后 zscore 是为了让每个交易日的横截面均值约为 0、标准差约为 1。

### Level 3：初学者最容易犯的 5 个 bug

1. 用 `close` 而不是 `adj_close`。这样拆股和分红会制造假收益。本代码用 `prices["adj_close"]`。

2. 把不同股票混在一起算收益。比如直接对 long table `pct_change()`，会让 AAPL 的价格和 MSFT 的价格相除。本代码先 `unstack("ticker")`，每列一只股票。

3. 忘记跳过最近 21 天。这样中期动量会混入短期反转。本代码用 `pct_change(252).shift(21)`。

4. 忘记保留 MultiIndex。后续 research、neutralize、zscore 都依赖 `(date, ticker)`。本代码用 `stack_wide_panel()` 再 `single_column_frame()` 转回标准格式。

5. 遇到除以 0 或无穷值不处理。`Week52High` 可能因为异常 rolling high 出现 inf。本代码用 `replace([np.inf, -np.inf], np.nan)`。

### Momentum.py 关键行解释

文件开头的 imports 和类定义是样板代码：导入 pandas/numpy、继承 `BaseFactor`、声明 `name/category/reference`。

`prices = get_prices(data)`：统一读取并验证价格数据，要求必须是 `(date, ticker)` MultiIndex，且包含 `adj_close`。

`adj_close = prices["adj_close"].unstack("ticker")`：把 long format 转成宽表，每只股票一列，保证收益计算不会串股票。

`momentum = adj_close.pct_change(252).shift(21)`：先算过去 252 个交易日收益，再整体往后错开 21 天，得到 12-1 动量。

`one_month_return = adj_close.pct_change(21)`：计算最近 1 个月收益，作为短期反转的原始输入。

`reversal = -1.0 * one_month_return`：方向反转，让过去跌得多的股票分数更高。

`rolling_high = adj_close.rolling(window=252, min_periods=126).max()`：计算过去约 52 周高点，至少半年数据才输出。

`factor_values = adj_close / rolling_high`：价格越接近 52 周高点，值越接近 1，动量越强。

`single_column_frame(stack_wide_panel(...), self.name)`：把宽表转回标准 long format，列名为因子名。

## 全 Pillar 2 因子说明

### Value

`book_to_market = book_value / market_cap`。逻辑：账面价值相对市值越高，估值越便宜。字段：`book_value`, `market_cap`。坑：market cap 缺失时不能用价格代替。

`earnings_yield = net_income / market_cap`。逻辑：单位市值对应的盈利越高，估值越便宜。字段：`net_income`, `market_cap`。坑：净利润必须 PIT lag，否则财报未来信息泄露。

`sales_to_price = revenue / market_cap`。逻辑：收入相对市值越高，估值越低。字段：`revenue`, `market_cap`。坑：收入不能使用未发布财报。

### Momentum

`momentum_12_1 = adj_close.pct_change(252).shift(21)`。逻辑：中期趋势延续，同时排除最近一个月反转。字段：`adj_close`。坑：忘记 `shift(21)`。

`short_term_reversal = -adj_close.pct_change(21)`。逻辑：短期涨跌可能反转，过去跌的未来可能反弹。字段：`adj_close`。负号让高分代表更看多。

`week_52_high = adj_close / rolling_252d_high`。逻辑：越接近一年高点，趋势越强。字段：`adj_close`。坑：rolling high 不能包含未来价格。

### Quality

`roe = net_income / book_value`。逻辑：股东权益创造利润的效率越高越好。字段：`net_income`, `book_value`。坑：book value 为负或接近 0 时会很不稳定。

`gross_profitability = gross_profit / total_assets`。逻辑：单位资产创造毛利的能力越强越好。字段：`gross_profit`, `total_assets`。坑：当前 Yahoo 下载字段可能没有 `gross_profit`。

`accruals = -(net_income - operating_cashflow) / total_assets`。逻辑：应计利润越高，盈利质量可能越差，所以取负号。字段：`net_income`, `operating_cashflow`, `total_assets`。坑：现金流字段缺失时不能硬填 0。

### Low Volatility

`idiosyncratic_vol = -rolling_CAPM_residual_volatility`。逻辑：市场解释不了的特异波动越低越好，所以取负号。字段：`return_1d` 或 `adj_close`。market proxy：优先外部 `market_returns`，否则当前股票池等权收益。

`beta_inverse = -rolling_beta`。逻辑：低 beta 股票更 defensive，高分代表低系统风险。字段：`return_1d` 或 `adj_close`，以及 market proxy。坑：市场收益口径会影响 beta。

`realized_vol = -rolling_60d_std(return_1d)`。逻辑：低波动股票更稳健，所以取负号。字段：`return_1d` 或 `adj_close`。坑：用价格标准差而不是收益标准差是错的。

### Size

`log_market_cap = -ln(market_cap)`。逻辑：小市值股票得分更高。字段：`market_cap`。坑：market cap 必须大于 0。

`log_total_assets = -ln(total_assets)`。逻辑：资产规模小的公司得分更高。字段：`total_assets`。坑：资产为 0 或负数不能取 log。

`log_revenue = -ln(revenue)`。逻辑：收入规模小的公司得分更高。字段：`revenue`。坑：收入为 0 或负数不能取 log。

## 时间对齐和 Look-Ahead 防护

价格类因子只使用当前及历史价格。最终因子保存前统一 `shift(1)`，保证 T 日收盘后形成的信号不会用于 T 日交易。

基本面类因子要求输入已经通过 Pillar 1 做 PIT lag，当前配置是 45 个 business days。若使用 `daily_fundamentals.parquet`，它应该已经是每日 as-of 面板；若使用 long fundamentals，则只按 `available_date` 向后可用。

## 缺失值来源和影响

缺失值主要来自：上市时间不足、rolling window 样本不足、基本面数据为空、缺少 market cap、缺少现金流/毛利字段、除数为 0 或负数不能取 log。

影响：该股票该日期没有因子分数，不参与当天该因子的横截面标准化或后续研究。不会 forward fill 因子值，因为填充可能引入过期信息和假 alpha。

## 最容易出现的假 Alpha Bug

最大风险是 look-ahead：用未滞后的财报、用当天收盘信号当天交易、rolling window 不小心包含未来数据。

第二个风险是 survivorship bias：当前免费数据 universe 是当前成分股，历史上退市或被剔除的股票不在样本里。

第三个风险是横截面和时序混淆：zscore 必须每天单独做，不能把 10 年数据混在一起标准化。

第四个风险是错误 market proxy：低 beta 如果用股票池等权收益，只是 fallback，不等价于真实市场指数。

第五个风险是缺失值乱填：基本面缺失不能填 0，market cap 缺失不能用价格代替。

## Pillar 3 Stage 1 Price-Only Research Conclusions

This section summarizes the first single-factor research pass for the six price-only factors. All signals were evaluated with forward returns, no automatic sign flips, and sector-neutral versions using Wikipedia GICS sectors with 96.9% ticker coverage.

### Main conclusion

`short_term_reversal` is the only price-only factor recommended for Pillar 4. Its IC, long-short return, and monotonicity all point in the same positive direction, and sector neutralization improved its long-short Sharpe from 0.47 to 0.60. Its sector-neutral Fama-MacBeth t-stat is 1.57, which is still below the classic 2.0 threshold but stronger than the pre-neutralization result.

### Momentum interpretation

`momentum_12_1` has a weak positive 1-day IC before neutralization, but after sector neutralization its long-short Sharpe is nearly zero and its Fama-MacBeth t-stat is only 0.41. This suggests that in this large-cap US universe, the measured momentum effect is mostly sector momentum rather than stock-specific trend continuation. It should not be used as a standalone Pillar 4 candidate yet.

### Low-volatility interpretation

`idiosyncratic_vol`, `realized_vol`, and `beta_inverse` do not look like clean defensive factors in this sample. The negative signs in their construction are correct, but the realized long-short spreads are negative. After sector neutralization, `idiosyncratic_vol` and `realized_vol` remain significant in the opposite direction, with Fama-MacBeth t-stats of -2.61 and -2.35. This is a useful regime finding: during 2014-2024, high-volatility growth stocks dominated the sample, so low-volatility premia were weak or reversed.

### Week 52 high interpretation

`week_52_high` is not recommended as a standalone raw trend factor in this universe. Its negative spread persists after sector neutralization and its sector-neutral Fama-MacBeth t-stat is -2.11. However, in this sample it behaves empirically as a reversal-style signal, so Pillar 4 includes it with `direction = -1` as an optional, research-approved transform.

### Practical Pillar 4 input

For the raw standalone interpretation, `short_term_reversal` remains the cleanest price-only candidate. For the combination layer, Pillar 4 now also permits research-approved transforms of `idiosyncratic_vol`, `realized_vol`, and `week_52_high`, with directions recorded in `config/pillar4_candidate_factors.yaml`.

## Pillar 4 Handoff: Direction Transform in Combination Layer

Stage 4.1 has adopted Path B: the active portfolio-construction path uses `data/factor_data/factors_sector_neutral.parquet` as the source input. The raw Pillar 2 factor definitions are not rewritten after research. Instead, Pillar 4 applies a separate direction transform before combination: `short_term_reversal` keeps direction `+1`, while `idiosyncratic_vol`, `realized_vol`, and `week_52_high` use direction `-1` so that every adjusted score means "higher score = higher expected return".

This separation is important. Raw factor definitions remain auditable and tied to their original economic meaning, while the combination layer records research-approved transforms needed for portfolio construction. The current 4-factor equal-weight baseline is now called `baseline_4f`; Stage 4.2 will test whether the highly correlated volatility pair, especially `idiosyncratic_vol` versus `realized_vol`, should be de-duplicated or downweighted before moving to Stage 4.3.

Stage 4.3 completed the baseline selection after transaction costs. `dedup_3f_equal_weight_idio` is the no-cost research winner, while `dedup_3f_fm_weighted_idio` is the implementation-aware default baseline after transaction costs. Keep the equal-weight version as the robustness benchmark rather than deleting it.
