# Pillar 5 Stage 5.1 Volatility Targeting Summary

## Production Choice
- Baseline variant: `V3_beta_neutral_sector_capped_fm_weekly_adv20`.
- Selected target volatility: 10%.
- Leverage scaler: k = 0.7025.
- Production gross: 1.4050x.
- Sharpe at 10 bps: 0.498.
- Max drawdown at 10 bps: -17.3%.

## Volatility Diagnostics
| metric | period | ann_vol |
| --- | --- | --- |
| full_sample | full | 0.1424 |
| rolling_60d_mean | full | 0.131 |
| rolling_60d_max | full | 0.3786 |
| rolling_252d_mean | full | 0.1369 |
| rolling_252d_max | full | 0.239 |
| calendar_year | 2014 | 0.0866 |
| calendar_year | 2015 | 0.0969 |
| calendar_year | 2016 | 0.1151 |
| calendar_year | 2017 | 0.0876 |
| calendar_year | 2018 | 0.0969 |
| calendar_year | 2019 | 0.1068 |
| calendar_year | 2020 | 0.2338 |
| calendar_year | 2021 | 0.1772 |
| calendar_year | 2022 | 0.1854 |
| calendar_year | 2023 | 0.1411 |
| calendar_year | 2024 | 0.1434 |

## Targeting Grid
| sigma_target | cost_bps | leverage_scaler | production_gross | ann_return | ann_sharpe | max_dd | dd_duration_days | hit_rate | ann_vol_realized |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6% | 5 | 0.4215 | 0.843 | 0.0378 | 0.6483 | -0.1019 | 450 | 0.5109 | 0.06 |
| 6% | 10 | 0.4215 | 0.843 | 0.0285 | 0.498 | -0.1072 | 680 | 0.5072 | 0.06 |
| 6% | 20 | 0.4215 | 0.843 | 0.0101 | 0.1971 | -0.1313 | 1555 | 0.4969 | 0.06 |
| 8% | 5 | 0.562 | 1.124 | 0.0499 | 0.6483 | -0.134 | 450 | 0.5109 | 0.08 |
| 8% | 10 | 0.562 | 1.124 | 0.0373 | 0.498 | -0.1408 | 720 | 0.5072 | 0.08 |
| 8% | 20 | 0.562 | 1.124 | 0.0127 | 0.1971 | -0.1718 | 1555 | 0.4969 | 0.08 |
| 10% | 5 | 0.7025 | 1.405 | 0.0617 | 0.6483 | -0.165 | 451 | 0.5109 | 0.1 |
| 10% | 10 | 0.7025 | 1.405 | 0.0458 | 0.498 | -0.1732 | 720 | 0.5072 | 0.1 |
| 10% | 20 | 0.7025 | 1.405 | 0.0148 | 0.1971 | -0.2107 | 1555 | 0.4969 | 0.1001 |
| 12% | 5 | 0.843 | 1.686 | 0.0731 | 0.6483 | -0.1952 | 451 | 0.5109 | 0.12 |
| 12% | 10 | 0.843 | 1.686 | 0.054 | 0.498 | -0.2046 | 720 | 0.5072 | 0.12 |
| 12% | 20 | 0.843 | 1.686 | 0.0166 | 0.1971 | -0.248 | 1555 | 0.4969 | 0.1201 |

## Recommendation
Use the 10% production volatility setting because it is the selected post-cost Sharpe/DD row under the 10 bps primary cost assumption. The resulting production gross is 1.40x, outside the pre-task 0.8-1.3x sanity band; this is driven by the realized full-sample volatility of the 2x research stream.

## Static Volatility Caveat
Production uses static 1.405x gross leverage based on full-sample volatility. Realized volatility will exceed the 10% target in high-volatility regimes: the 60-day max annualized vol scales to approximately 26.6%. A dynamic volatility-targeting overlay that scales leverage by trailing realized vol should be evaluated in Pillar 5 live-readiness.
