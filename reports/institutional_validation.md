# v2 Institutional Research Validation Pack

## Executive Summary

- This report validates signal stability, statistical significance, factor interaction, OOS behavior, regime behavior, and implementation constraints.
- It is a research evidence pack, not a production/live-readiness claim.
- Full-universe fundamentals-dependent attribution remains fail-closed when coverage is insufficient, but the market-cap-ready 416-name subset now has a passing real-market-cap contract and a no-fallback Barra attribution run.

## Factor Validation

| factor_name | ic_mean_1d | ic_ir_1d | ic_tstat_1d | ic_p_value_1d | ic_hit_rate_1d | long_short_sharpe | monotonicity | rank_autocorr_mean | signal_half_life_days | ic_fdr_p_value_1d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 0.0124 | 0.0522 | 2.7378 | 0.0062 | 0.5359 | 0.0773 | -0.1152 | 0.9945 | 124.8196 | 0.0371 |
| short_term_reversal | 0.0053 | 0.0280 | 1.5914 | 0.1115 | 0.5031 | 0.4690 | 0.8303 | 0.9369 | 10.6276 | 0.3345 |
| week_52_high | 0.0043 | 0.0185 | 0.9815 | 0.3263 | 0.5365 | -0.5914 | -0.9273 | 0.9741 | 26.3765 | 0.6526 |
| idiosyncratic_vol | 0.0013 | 0.0077 | 0.4147 | 0.6784 | 0.4886 | -0.7723 | -0.9273 | 0.9931 | 100.5830 | 0.9968 |
| beta_inverse | 0.0000 | 0.0001 | 0.0040 | 0.9968 | 0.4967 | -0.4075 | -0.7697 | 0.9938 | 111.0590 | 0.9968 |

## IC Decay

| factor_name | horizon | ic_mean | ic_std | ic_ir | ic_tstat | ic_p_value | hit_rate | n_obs | decay_ratio_vs_1d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 1 | 0.0124 | 0.2383 | 0.0522 | 2.7378 | 0.0062 | 0.5359 | 2493.0000 | 1.0000 |
| momentum_12_1 | 5 | 0.0123 | 0.2331 | 0.0527 | 1.4258 | 0.1539 | 0.5319 | 2489.0000 | 0.9867 |
| momentum_12_1 | 10 | 0.0101 | 0.2235 | 0.0450 | 1.0529 | 0.2924 | 0.5366 | 2484.0000 | 0.8092 |
| momentum_12_1 | 21 | 0.0046 | 0.2085 | 0.0219 | 0.4788 | 0.6321 | 0.5386 | 2473.0000 | 0.3678 |
| momentum_12_1 | 63 | -0.0070 | 0.1850 | -0.0377 | -0.7795 | 0.4357 | 0.5282 | 2431.0000 | -0.5602 |
| short_term_reversal | 1 | 0.0053 | 0.1895 | 0.0280 | 1.5914 | 0.1115 | 0.5031 | 2745.0000 | 1.0000 |
| short_term_reversal | 5 | 0.0130 | 0.1790 | 0.0724 | 2.1286 | 0.0333 | 0.5210 | 2741.0000 | 2.4448 |
| short_term_reversal | 10 | 0.0164 | 0.1693 | 0.0971 | 2.4645 | 0.0137 | 0.5270 | 2736.0000 | 3.1001 |
| short_term_reversal | 21 | 0.0199 | 0.1630 | 0.1220 | 2.9010 | 0.0037 | 0.5273 | 2725.0000 | 3.7496 |
| short_term_reversal | 63 | 0.0162 | 0.1498 | 0.1082 | 2.4685 | 0.0136 | 0.5334 | 2683.0000 | 3.0579 |
| week_52_high | 1 | 0.0043 | 0.2316 | 0.0185 | 0.9815 | 0.3263 | 0.5365 | 2641.0000 | 1.0000 |
| week_52_high | 5 | -0.0046 | 0.2278 | -0.0202 | -0.5560 | 0.5782 | 0.4983 | 2637.0000 | -1.0718 |
| week_52_high | 10 | -0.0094 | 0.2230 | -0.0420 | -1.0004 | 0.3171 | 0.4977 | 2632.0000 | -2.1827 |
| week_52_high | 21 | -0.0146 | 0.2154 | -0.0676 | -1.5143 | 0.1299 | 0.5109 | 2621.0000 | -3.3987 |
| week_52_high | 63 | -0.0245 | 0.1858 | -0.1316 | -2.8287 | 0.0047 | 0.4719 | 2579.0000 | -5.7042 |
| idiosyncratic_vol | 1 | 0.0013 | 0.1746 | 0.0077 | 0.4147 | 0.6784 | 0.4886 | 2726.0000 | 1.0000 |
| idiosyncratic_vol | 5 | -0.0042 | 0.1701 | -0.0249 | -0.6931 | 0.4882 | 0.4827 | 2722.0000 | -3.1616 |
| idiosyncratic_vol | 10 | -0.0080 | 0.1659 | -0.0481 | -1.1594 | 0.2463 | 0.4696 | 2717.0000 | -5.9612 |
| idiosyncratic_vol | 21 | -0.0125 | 0.1582 | -0.0788 | -1.7772 | 0.0755 | 0.4715 | 2706.0000 | -9.3122 |
| idiosyncratic_vol | 63 | -0.0318 | 0.1604 | -0.1981 | -4.2535 | 0.0000 | 0.4264 | 2664.0000 | -23.7265 |

## Factor Turnover

| factor_name | rank_autocorr_mean | rank_autocorr_median | signal_half_life_days | quantile_turnover_mean | top_quantile_turnover_mean | bottom_quantile_turnover_mean |
| --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 0.9945 | 0.9952 | 124.8196 | 0.3316 | 0.1074 | 0.1042 |
| short_term_reversal | 0.9369 | 0.9424 | 10.6276 | 0.9709 | 0.3839 | 0.3891 |
| week_52_high | 0.9741 | 0.9799 | 26.3765 | 0.6103 | 0.6352 | 0.1037 |
| idiosyncratic_vol | 0.9931 | 0.9955 | 100.5830 | 0.2164 | 0.1070 | 0.0543 |
| beta_inverse | 0.9938 | 0.9975 | 111.0590 | 0.3046 | 0.1048 | 0.1014 |
| realized_vol | 0.9947 | 0.9965 | 129.8838 | 0.2167 | 0.1038 | 0.0562 |

## Factor Interaction

- Max absolute off-diagonal correlation: 0.8934
- PC1 explained variance: 0.4528

## Rolling Factor Correlations

| left_factor | right_factor | window | mean_rolling_corr | min_rolling_corr | max_rolling_corr | n_obs |
| --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | short_term_reversal | 252 | 0.0036 | -0.0742 | 0.1173 | 2369 |
| momentum_12_1 | week_52_high | 252 | 0.4916 | 0.0880 | 0.7332 | 2369 |
| momentum_12_1 | idiosyncratic_vol | 252 | 0.0722 | -0.2493 | 0.2734 | 2369 |
| momentum_12_1 | beta_inverse | 252 | 0.0391 | -0.4787 | 0.5394 | 2369 |
| momentum_12_1 | realized_vol | 252 | 0.0876 | -0.3925 | 0.4215 | 2369 |
| short_term_reversal | week_52_high | 252 | -0.4828 | -0.6083 | -0.3238 | 2517 |
| short_term_reversal | idiosyncratic_vol | 252 | -0.0064 | -0.1018 | 0.1043 | 2602 |
| short_term_reversal | beta_inverse | 252 | -0.0167 | -0.1702 | 0.1184 | 2602 |
| short_term_reversal | realized_vol | 252 | -0.0120 | -0.1430 | 0.1396 | 2602 |
| week_52_high | idiosyncratic_vol | 252 | 0.4083 | 0.3192 | 0.5256 | 2517 |
| week_52_high | beta_inverse | 252 | 0.2836 | -0.0333 | 0.6401 | 2517 |
| week_52_high | realized_vol | 252 | 0.4480 | 0.2956 | 0.6137 | 2517 |
| idiosyncratic_vol | beta_inverse | 252 | 0.3280 | 0.1971 | 0.4076 | 2602 |
| idiosyncratic_vol | realized_vol | 252 | 0.8913 | 0.8007 | 0.9665 | 2602 |
| beta_inverse | realized_vol | 252 | 0.6483 | 0.5070 | 0.8055 | 2602 |

## Orthogonalized Factor Diagnostics

| factor_name | raw_ic_mean_1d | raw_ic_tstat_1d | orthogonalized_ic_mean_1d | orthogonalized_ic_tstat_1d | orthogonalized_ic_retention | controls |
| --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 0.0124 | 2.7378 | 0.0097 | 4.2579 | 0.7829 | short_term_reversal,week_52_high,idiosyncratic_vol,beta_inverse,realized_vol |
| short_term_reversal | 0.0053 | 1.5914 | 0.0005 | 0.2263 | 0.0874 | momentum_12_1,week_52_high,idiosyncratic_vol,beta_inverse,realized_vol |
| week_52_high | 0.0043 | 0.9815 | 0.0008 | 0.4147 | 0.1799 | momentum_12_1,short_term_reversal,idiosyncratic_vol,beta_inverse,realized_vol |
| idiosyncratic_vol | 0.0013 | 0.4147 | 0.0014 | 0.8226 | 1.0195 | momentum_12_1,short_term_reversal,week_52_high,beta_inverse,realized_vol |
| beta_inverse | 0.0000 | 0.0040 | 0.0019 | 0.9784 | n/a | momentum_12_1,short_term_reversal,week_52_high,idiosyncratic_vol,realized_vol |
| realized_vol | 0.0008 | 0.1809 | -0.0009 | -0.5472 | n/a | momentum_12_1,short_term_reversal,week_52_high,idiosyncratic_vol,beta_inverse |

## OOS Validation

| window_id | split | start_date | end_date | n_days | sharpe | annual_return | annual_vol | max_drawdown | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014_2018_to_2019_2019 | test | 2019-01-02 | 2019-12-31 | 252 | 1.2133 | 0.1316 | 0.1066 | 0.1052 | 0.5516 |
| 2015_2019_to_2020_2020 | test | 2020-01-02 | 2020-12-31 | 253 | 2.0415 | 0.5667 | 0.2334 | 0.1673 | 0.5652 |
| 2016_2020_to_2021_2021 | test | 2021-01-04 | 2021-12-31 | 252 | -0.0752 | -0.0285 | 0.1769 | 0.1593 | 0.4841 |
| 2017_2021_to_2022_2022 | test | 2022-01-03 | 2022-12-30 | 251 | 1.1309 | 0.2117 | 0.1850 | 0.0924 | 0.5060 |
| 2018_2022_to_2023_2023 | test | 2023-01-03 | 2023-12-29 | 250 | 1.3184 | 0.1921 | 0.1408 | 0.1496 | 0.5480 |
| 2019_2023_to_2024_2024 | test | 2024-01-02 | 2024-12-31 | 252 | 0.0862 | 0.0021 | 0.1431 | 0.1001 | 0.5000 |

## Train-Locked Factor OOS Validation

| window_id | split | start_date | end_date | n_days | sharpe | annual_return | max_drawdown | selected_factors | locked_weights |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014_2018_to_2019_2019 | test | 2019-01-03 | 2019-12-31 | 251 | 0.8684 | 0.0460 | -0.0412 | momentum_12_1,short_term_reversal | {"momentum_12_1": 0.56018, "short_term_reversal": 0.43982} |
| 2015_2019_to_2020_2020 | test | 2020-01-03 | 2020-12-31 | 252 | 0.2545 | 0.0278 | -0.1236 | momentum_12_1,short_term_reversal | {"momentum_12_1": 0.470569, "short_term_reversal": 0.529431} |
| 2016_2020_to_2021_2021 | test | 2021-01-05 | 2021-12-31 | 251 | -0.3776 | -0.0420 | -0.0954 | momentum_12_1,short_term_reversal | {"momentum_12_1": 0.536727, "short_term_reversal": 0.463273} |
| 2017_2021_to_2022_2022 | test | 2022-01-04 | 2022-12-30 | 250 | 0.5630 | 0.0590 | -0.0789 | momentum_12_1 | {"momentum_12_1": 1.0} |
| 2018_2022_to_2023_2023 | test | 2023-01-04 | 2023-12-29 | 249 | -1.6900 | -0.1460 | -0.1444 | momentum_12_1,week_52_high,beta_inverse | {"beta_inverse": 0.244511, "momentum_12_1": 0.460299, "week_52_high": 0.29519} |
| 2019_2023_to_2024_2024 | test | 2024-01-03 | 2024-12-31 | 251 | 1.9425 | 0.1811 | -0.0506 | momentum_12_1,week_52_high | {"momentum_12_1": 0.688108, "week_52_high": 0.311892} |

## Regime Validation

| regime | n_days | ann_return | ann_sharpe | max_dd | hit_rate | beta_to_market |
| --- | --- | --- | --- | --- | --- | --- |
| full_sample | 2707 | 0.1091 | 0.7985 | -0.2172 | 0.5157 | 0.1865 |
| high_vol | 687 | 0.4172 | 1.8663 | -0.1673 | 0.5328 | 0.1903 |
| low_vol | 683 | 0.0829 | 0.9095 | -0.1061 | 0.5066 | 0.1309 |
| market_drawdown | 677 | 0.0177 | 0.1870 | -0.2171 | 0.4786 | 0.1814 |
| market_uptrend | 677 | 0.2376 | 1.6338 | -0.1318 | 0.5495 | 0.1452 |
| covid_crash_2020 | 24 | -0.2734 | -0.7048 | -0.1673 | 0.4583 | 0.0915 |
| rate_shock_2022 | 198 | 0.2922 | 1.4422 | -0.0924 | 0.5000 | 0.2765 |

## Exposure And Risk Decomposition

| factor_name | mean_exposure | exposure_std | variance_share | mean_factor_pnl | pnl_tstat |
| --- | --- | --- | --- | --- | --- |
| momentum_12_1 | -0.5425 | 0.5683 | -0.1805 | 0.0001 | 0.5031 |
| short_term_reversal | 1.3602 | 0.4786 | 0.2578 | 0.0001 | 1.2844 |
| week_52_high | -2.2726 | 0.6350 | -0.4847 | -0.0002 | -1.7869 |
| idiosyncratic_vol | -2.0113 | 0.3923 | -0.3724 | -0.0003 | -2.5414 |
| beta_inverse | -0.0719 | 0.0703 | -0.3611 | -0.0002 | -1.3599 |
| realized_vol | -1.6692 | 0.4100 | -0.4353 | -0.0003 | -2.2066 |

## Feature Importance

| factor_name | importance_score | ic_abs_component | long_short_sharpe_abs_component | oos_selected_window_share | orthogonalized_ic_retention | variance_share_abs |
| --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 3.2844 | 0.0124 | 0.0773 | 1.0000 | 0.7829 | 0.1805 |
| idiosyncratic_vol | 2.2981 | 0.0013 | 0.7723 | 0.0000 | 1.0195 | 0.3724 |
| week_52_high | 2.0180 | 0.0043 | 0.5914 | 0.3333 | 0.1799 | 0.4847 |
| short_term_reversal | 1.8443 | 0.0053 | 0.4690 | 0.5000 | 0.0874 | 0.2578 |
| realized_vol | 1.0677 | 0.0008 | 0.5496 | 0.0000 | 0.0000 | 0.4353 |
| beta_inverse | 0.9375 | 0.0000 | 0.4075 | 0.1667 | 0.0000 | 0.3611 |

## Capacity And Impact

| aum_usd | impact_coefficient | gross | status | mean_participation | p95_participation | mean_daily_impact_cost | borrow_feasible_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 25000000.0000 | 0.1000 | 1.5000 | proxy_adv_assumption | 0.0029 | 0.0201 | 0.0001 | False |
| 25000000.0000 | 0.5000 | 1.5000 | proxy_adv_assumption | 0.0029 | 0.0201 | 0.0003 | False |
| 25000000.0000 | 1.0000 | 1.5000 | proxy_adv_assumption | 0.0029 | 0.0201 | 0.0005 | False |
| 50000000.0000 | 0.1000 | 1.5000 | proxy_adv_assumption | 0.0058 | 0.0403 | 0.0001 | False |
| 50000000.0000 | 0.5000 | 1.5000 | proxy_adv_assumption | 0.0058 | 0.0403 | 0.0004 | False |
| 50000000.0000 | 1.0000 | 1.5000 | proxy_adv_assumption | 0.0058 | 0.0403 | 0.0008 | False |
| 100000000.0000 | 0.1000 | 1.5000 | proxy_adv_assumption | 0.0116 | 0.0805 | 0.0001 | False |
| 100000000.0000 | 0.5000 | 1.5000 | proxy_adv_assumption | 0.0116 | 0.0805 | 0.0005 | False |
| 100000000.0000 | 1.0000 | 1.5000 | proxy_adv_assumption | 0.0116 | 0.0805 | 0.0011 | False |
| 250000000.0000 | 0.1000 | 1.5000 | proxy_adv_assumption | 0.0291 | 0.2013 | 0.0002 | False |
| 250000000.0000 | 0.5000 | 1.5000 | proxy_adv_assumption | 0.0291 | 0.2013 | 0.0008 | False |
| 250000000.0000 | 1.0000 | 1.5000 | proxy_adv_assumption | 0.0291 | 0.2013 | 0.0017 | False |

## Artifact Contract

- `factor_validation_summary.csv`
- `ic_decay.csv`
- `factor_turnover.csv`
- `quantile_portfolio_returns.csv`
- `quantile_returns_by_regime.csv`
- `factor_correlation_matrix.csv`
- `rolling_factor_correlations.csv`
- `pca_factor_diagnostics.csv`
- `orthogonalized_factor_diagnostics.csv`
- `oos_validation_windows.csv`
- `locked_factor_oos_windows.csv`
- `factor_exposure_timeseries.csv`
- `risk_decomposition.csv`
- `risk_decomposition_summary.csv`
- `feature_importance.csv`
- `capacity_impact_grid.csv`
