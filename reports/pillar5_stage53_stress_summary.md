# Pillar 5 Stage 5.3 Stress Testing & Regime Robustness Summary

## Setup
- Production sizing: target vol 10%, gross 1.40x.
- Primary return stream includes 10 bps transaction costs.

## Historical Stress Windows
| window | start_date | end_date | return | max_dd_in_window | vol | sharpe | beta_to_market_in_window | n_days | kill_switch_triggered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2015 China crash | 2015-06-01 | 2015-09-30 | -0.0872 | -0.0998 | 0.0703 | -3.7627 | 0.0855 | 86 | False |
| 2018 Q4 sell-off | 2018-10-01 | 2018-12-31 | 0.0291 | -0.0211 | 0.0871 | 1.3577 | 0.0751 | 63 | False |
| 2020-03 COVID | 2020-02-15 | 2020-04-15 | -0.0084 | -0.1227 | 0.2549 | -0.0794 | 0.0907 | 41 | False |
| 2022 bear | 2022-01-01 | 2022-12-31 | 0.1035 | -0.0671 | 0.1299 | 0.8264 | 0.2039 | 251 | False |
| 2023-10 deep DD | 2023-09-15 | 2023-11-15 | -0.0073 | -0.0729 | 0.1412 | -0.2279 | 0.3943 | 44 | False |

No historical stress window triggered the -20% kill switch.

## Realized Beta Shock Stress
| beta_assumption | realized_beta | market_shock | production_gross | expected_portfolio_loss |
| --- | --- | --- | --- | --- |
| full_sample | 0.216 | -0.1 | 1.405 | -0.0303 |
| full_sample | 0.216 | -0.2 | 1.405 | -0.0607 |
| full_sample | 0.216 | -0.3 | 1.405 | -0.091 |
| post_2020 | 0.236 | -0.1 | 1.405 | -0.0332 |
| post_2020 | 0.236 | -0.2 | 1.405 | -0.0663 |
| post_2020 | 0.236 | -0.3 | 1.405 | -0.0995 |

## Borrow Cost Stress
| borrow_cost_bps_annualized | ann_return | ann_sharpe | max_dd | break_even_borrow_cost_bps |
| --- | --- | --- | --- | --- |
| 0 | 0.0458 | 0.498 | -0.1732 | 708.7161 |
| 50 | 0.0421 | 0.4628 | -0.1755 | 708.7161 |
| 100 | 0.0385 | 0.4277 | -0.1778 | 708.7161 |
| 200 | 0.0312 | 0.3574 | -0.1882 | 708.7161 |

Break-even borrow cost is reported as a single analytic threshold, not a grid-search output. It equals the annualized mean production return divided by short-leg gross notional, so it is constant across the displayed 0/50/100/200 bps stress rows. The ~700 bps level means the strategy would need roughly 7% annualized borrow drag on the short book before Sharpe falls to zero under this linear approximation.

## Proxy Quality Stress
| proxy | realized_beta | delta_vs_equal_weight | n_days |
| --- | --- | --- | --- |
| out_of_portfolio_equal_weight | 0.1538 | 0.0 | 2707 |
| volume_weighted_pool_proxy | 0.1379 | -0.0158 | 2707 |

## 2023-10 Root Cause
The 2023-10 drawdown is a lagged-beta-in-regime-shift example, not evidence of broad factor decay. Window return was -0.7%, and realized beta jumped to 0.394, about 1.8x the full-sample 0.216 reference despite ex-ante beta targeting. Losses were led by the `short_book` and concentrated in `Consumer Discretionary` plus `Communication Services`, consistent with long-short spreads compressing inside cyclical/growth sectors during the sell-off. Proxy-quality stress moves realized beta from 0.154 to 0.138, so the issue is regime beta drift rather than a bad proxy alone.

### 2023-10 Attribution
Rows tagged `daily_beta_drift_20d` report trailing 20-day realized beta through each date; sector and book rows report lagged-weight PnL contribution and average exposure for the same 2023-09-15 to 2023-11-15 window.
| bucket_type | bucket | contribution | share_of_loss | net_exposure | long_exposure | short_exposure | full_sample_beta_reference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sector | Consumer Discretionary | -0.0172 | 0.411 | -0.0826 | 0.0835 | -0.1661 | nan |
| sector | Communication Services | -0.0161 | 0.3848 | -0.1272 | 0.0578 | -0.185 | nan |
| sector | Real Estate | -0.0087 | 0.2082 | 0.0185 | 0.0401 | -0.0216 | nan |
| sector | Industrials | -0.0036 | 0.0868 | 0.0804 | 0.1366 | -0.0562 | nan |
| sector | Unknown | -0.003 | 0.0717 | -0.0536 | 0.021 | -0.0747 | nan |
| sector | Energy | -0.0027 | 0.0634 | 0.0215 | 0.0265 | -0.005 | nan |
| sector | Information Technology | -0.0013 | 0.0304 | -0.204 | 0.1091 | -0.3131 | nan |
| sector | Materials | -0.0009 | 0.0215 | -0.0241 | 0.0597 | -0.0839 | nan |
| sector | Consumer Staples | -0.0004 | 0.0106 | 0.1116 | 0.1199 | -0.0083 | nan |
| sector | Health Care | 0.0001 | -0.0026 | 0.1688 | 0.1822 | -0.0134 | nan |
| book_side | short_book | -0.0329 | 0.7856 | -1.0 | 0.0 | -1.0 | nan |
| book_side | long_book | -0.009 | 0.2144 | 1.0 | 1.0 | 0.0 | nan |
| daily_beta_drift_20d | 2023-09-15 | 0.4407 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-18 | 0.449 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-19 | 0.4472 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-20 | 0.4332 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-21 | 0.3804 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-22 | 0.3606 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-25 | 0.3531 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-26 | 0.2143 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-27 | 0.1312 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-28 | 0.2316 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-09-29 | 0.225 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-02 | 0.5265 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-03 | 0.5587 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-04 | 0.4122 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-05 | 0.4116 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-06 | 0.3415 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-09 | 0.3186 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-10 | 0.3574 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-11 | 0.3207 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-12 | 0.2737 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-13 | 0.3334 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-16 | 0.3851 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-17 | 0.405 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-18 | 0.348 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-19 | 0.3073 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-20 | 0.2842 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-23 | 0.2827 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-24 | 0.3801 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-25 | 0.2663 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-26 | 0.2273 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-27 | 0.2587 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-30 | 0.0938 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-10-31 | 0.0638 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-01 | 0.1374 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-02 | 0.1822 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-03 | 0.2656 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-06 | 0.3212 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-07 | 0.3102 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-08 | 0.3285 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-09 | 0.3194 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-10 | 0.2889 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-13 | 0.271 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-14 | 0.3777 | nan | nan | nan | nan | 0.216 |
| daily_beta_drift_20d | 2023-11-15 | 0.4125 | nan | nan | nan | nan | 0.216 |
| single_factor_sleeve | short_term_reversal | 0.025 | nan | nan | nan | nan | nan |
| single_factor_sleeve | idiosyncratic_vol | 0.0185 | nan | nan | nan | nan | nan |
| single_factor_sleeve | week_52_high | 0.0092 | nan | nan | nan | nan | nan |

## Recommendation
The worst historical window is `2015 China crash` with return -8.7% and max drawdown -10.0%. Borrow-cost break-even is 709 bps annualized on the short leg.
