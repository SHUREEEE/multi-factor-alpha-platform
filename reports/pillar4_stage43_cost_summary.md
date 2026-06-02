# Pillar 4 Stage 4.3 Transaction Cost Summary

## Setup
- Factor source: `data/factor_data/factors_sector_neutral.parquet`.
- Evaluated portfolios: `dedup_3f_equal_weight_idio` and `dedup_3f_fm_weighted_idio`.
- `dedup_3f_equal_weight_idio` is the no-cost research winner, while `dedup_3f_fm_weighted_idio` is the implementation-aware default baseline after transaction costs.
- Cost model: `net_return = gross_return - (cost_bps / 10000) * turnover`.
- Cost levels: 0, 5, 10, and 20 one-way basis points.
- Portfolio construction remains top decile long, bottom decile short, daily rebalance, and 1-day lag.

## Cost Comparison
| portfolio | cost_bps | annualized_return | annualized_sharpe | max_drawdown | avg_turnover | hit_rate | net_cum_return | break_even_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dedup_3f_equal_weight_idio | 0 | 0.1527 | 0.8154 | -0.3163 | 0.2603 | 0.5075 | 3.7034 | 24.6387 |
| dedup_3f_equal_weight_idio | 5 | 0.1153 | 0.6486 | -0.3199 | 0.2603 | 0.4998 | 2.2815 | 24.6387 |
| dedup_3f_equal_weight_idio | 10 | 0.079 | 0.4817 | -0.3348 | 0.2603 | 0.4933 | 1.2893 | 24.6387 |
| dedup_3f_equal_weight_idio | 20 | 0.01 | 0.1482 | -0.3866 | 0.2603 | 0.4809 | 0.114 | 24.6387 |
| dedup_3f_fm_weighted_idio | 0 | 0.1477 | 0.798 | -0.2871 | 0.2132 | 0.5118 | 3.4825 | 29.2149 |
| dedup_3f_fm_weighted_idio | 5 | 0.117 | 0.6603 | -0.2971 | 0.2132 | 0.5049 | 2.3379 | 29.2149 |
| dedup_3f_fm_weighted_idio | 10 | 0.0872 | 0.5226 | -0.3193 | 0.2132 | 0.5013 | 1.4856 | 29.2149 |
| dedup_3f_fm_weighted_idio | 20 | 0.0299 | 0.2472 | -0.3712 | 0.2132 | 0.4871 | 0.3781 | 29.2149 |

## Sensitivity
- 0 bps winner: `dedup_3f_equal_weight_idio` with Sharpe 0.815.
- 5 bps winner: `dedup_3f_fm_weighted_idio` with Sharpe 0.660.
- 10 bps winner: `dedup_3f_fm_weighted_idio` with Sharpe 0.523.
- 20 bps winner: `dedup_3f_fm_weighted_idio` with Sharpe 0.247.

## Recommendation
Use `dedup_3f_fm_weighted_idio` as the default Stage 4.4 baseline. At 10 bps, equal-weight Sharpe is 0.482 and FM-weighted Sharpe is 0.523. The choice balances cost-adjusted Sharpe with implementation realism.
