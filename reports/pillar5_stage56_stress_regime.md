# Pillar 5 Stage 5.6 - Stress & Regime Testing

## Plan

1. Use the locked Pillar 5 V3 cache (`results/pillar5_artifacts/v3_weights.parquet` and `v3_daily_returns.parquet`) as the sole source of V3 weights and P&L.
2. Do not reconstruct V3 from Pillar 4 Stage 4.5; if the cache is insufficient, document the gap rather than substituting another book.
3. Reuse Stage 5.1 production sizing and 10 bps cost assumptions for all stress and regime statistics.
4. Compute the five requested stress windows exactly, including V3 return, volatility, Sharpe, max drawdown, hit rate, and market proxy comparison.
5. Build regime splits using VIX if available; otherwise use SPY 20d realized volatility as the VIX proxy, and fall back to the locked market proxy if SPY is unavailable.
6. Cross-reference Stage 5.4 high-turnover days (`production gross turnover > 100%`) and Stage 5.5 residual-beta drift (`|rolling 60d residual beta| > 0.4`) against stress windows.
7. Save CSV deliverables and report whether high-vol/dislocation regimes are where V3 underperforms and where neutralization becomes expensive or ineffective.

## Executive Summary
1. **Worst requested stress window: `2023 Aug-Oct rates spike`**, return -9.1%, max DD -11.7%, beta 0.097. No requested window breaches the -20% kill switch.

2. **The high-vol weakness assumption is not supported by this split.** SPY 20d vol top-quartile Sharpe is 1.624 versus 0.500 in bottom-quartile vol. The real weak regime is negative 60d market momentum: bottom-quartile SPY trailing-return Sharpe is -0.074.

3. **Tail turnover and residual-beta drift do cluster in the tested stress windows, but not exclusively.** The five windows contain 49 of 181 >100% turnover days and 129 high residual-beta days (`|beta| > 0.4`). This links Stage 5.4's expensive neutralization episodes to stress regimes, while leaving a meaningful normal-regime turnover problem for V4.

## Setup
- Production sizing: target vol 10%, gross 1.405x, 10 bps cost.
- Source of truth: locked Pillar 5 cache only. No Stage 4.5 reconstruction is used in Stage 5.6.
- VIX is not present in local market data. Regime split uses SPY 20d realized volatility as the VIX/high-vol proxy.
- SPY 20d vol top quartile threshold: 17.7%; bottom quartile threshold: 8.8%.

## Stress Windows
| window | start_date | end_date | n_days | return | vol | sharpe | max_dd | hit_rate | market_return | beta_to_market | residual_alpha_return | mean_residual_alpha_pnl | mean_rolling_60d_residual_beta | kill_switch_triggered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COVID crash | 2020-02-19 | 2020-03-23 | 24 | -0.0242 | 0.2551 | -0.8843 | -0.1227 | 0.4583 | -0.334 | 0.065 | -0.071 | -0.0028 | 0.1104 | False |
| COVID rebound | 2020-03-24 | 2020-06-08 | 53 | 0.1699 | 0.2496 | 3.1151 | -0.0869 | 0.5283 | 0.4497 | 0.2224 | 0.2968 | 0.0051 | 0.1927 | False |
| 2022 rate shock | 2022-01-03 | 2022-10-14 | 198 | 0.1193 | 0.1332 | 1.143 | -0.0671 | 0.4899 | -0.2383 | 0.1945 | 0.0679 | 0.0004 | 0.4326 | False |
| 2023 regional bank stress | 2023-03-08 | 2023-05-01 | 38 | -0.0149 | 0.1011 | -0.9353 | -0.0357 | 0.4474 | 0.0473 | 0.2211 | -0.0026 | -0.0 | 0.3297 | False |
| 2023 Aug-Oct rates spike | 2023-08-01 | 2023-10-27 | 63 | -0.0909 | 0.1086 | -3.4545 | -0.1169 | 0.4921 | -0.0997 | 0.0969 | -0.0524 | -0.0008 | 0.379 | False |

## Regime Split
| regime | n_days | ann_return | ann_vol | ann_sharpe | max_dd | hit_rate | market_ann_return | beta_to_market |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VIX proxy > 25 | 231 | 0.1193 | 0.1674 | 0.7564 | -0.1352 | 0.4978 | 0.4133 | 0.1337 |
| VIX proxy <= 25 | 2476 | 0.0392 | 0.0912 | 0.4672 | -0.1721 | 0.5081 | 0.109 | 0.1297 |
| SPY 20d realized vol top quartile | 687 | 0.2404 | 0.1386 | 1.6242 | -0.1227 | 0.524 | 0.1406 | 0.1344 |
| SPY 20d realized vol bottom quartile | 683 | 0.0308 | 0.0648 | 0.4997 | -0.0853 | 0.5007 | 0.2077 | 0.0934 |
| SPY 60d trailing return top quartile | 677 | 0.1297 | 0.0957 | 1.3224 | -0.1013 | 0.5406 | 0.5103 | 0.1031 |
| SPY 60d trailing return bottom quartile | 677 | -0.0176 | 0.1288 | -0.0739 | -0.1683 | 0.4712 | -0.2922 | 0.1276 |

## Stress x Turnover x Residual Beta Contingency
| stress_window | start_date | end_date | n_days | n_high_turnover_days | n_high_residual_beta_days_abs_gt_0_4 | mean_residual_alpha_pnl | pct_days_high_turnover | pct_days_high_residual_beta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COVID crash | 2020-02-19 | 2020-03-23 | 24 | 3 | 0 | -0.0028 | 0.125 | 0.0 |
| COVID rebound | 2020-03-24 | 2020-06-08 | 53 | 3 | 0 | 0.0051 | 0.0566 | 0.0 |
| 2022 rate shock | 2022-01-03 | 2022-10-14 | 198 | 25 | 112 | 0.0004 | 0.1263 | 0.5657 |
| 2023 regional bank stress | 2023-03-08 | 2023-05-01 | 38 | 6 | 0 | -0.0 | 0.1579 | 0.0 |
| 2023 Aug-Oct rates spike | 2023-08-01 | 2023-10-27 | 63 | 12 | 17 | -0.0008 | 0.1905 | 0.2698 |

## Worst-Window Narrative
`2023 Aug-Oct rates spike` is the weakest requested window with return -9.1% and max drawdown -11.7%. The window has 12 high-turnover days and 17 high-residual-beta days. Mean residual alpha PnL is -0.0833% per day, so the stress loss is not just market beta; it includes residual-alpha weakness consistent with Stage 5.5's finding that the neutralization layer is beta-effective but not risk-complete.

## Regime Conditioning
The weakest regime by Sharpe is `SPY 60d trailing return bottom quartile` with Sharpe -0.074 over 677 days. This refutes a simplistic high-vol-only story: V3 does not die whenever volatility is high; it struggles most when the market's 60-day trend is in the bottom quartile. This gives a direct live-readiness hook: V4 should monitor regime-conditioned Sharpe and realized beta, not only full-sample Sharpe.

## Connection to Stage 5.4 and 5.5
Stage 5.4 identified 181 days with production gross turnover above 100%; 49 (27.1%) fall inside the five requested stress windows. The densest stress-window cluster is `2022 rate shock` with 25 high-turnover days and 112 high-residual-beta days. Stage 5.5 identified residual beta drift after beta neutralization; Stage 5.6 shows that this drift should be monitored specifically during high-vol/rates-stress regimes.

## Outputs
- Stress windows: `results/pillar5_stage56_stress_windows.csv`.
- Regime split: `results/pillar5_stage56_regime_split.csv`.
- Turnover/residual-beta contingency: `results/pillar5_stage56_stress_turnover_beta_contingency.csv`.
