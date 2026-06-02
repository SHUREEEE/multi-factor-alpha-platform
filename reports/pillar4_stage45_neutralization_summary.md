# Pillar 4 Stage 4.5 Neutralization Summary

Updated 2026-05-30: V3 metrics realigned to post-ADR-0001 canonical book (Option 1, cache order / single-pass). See `reports/stage4_drift_triage.md`.

## Setup
- Main configuration: `dedup_3f_fm_weighted_idio + weekly_5d + adv20_filtered`.
- V1 is raw Stage 4.4 baseline; V2 adds ex-ante beta neutralization; V3 adds a 25% sector cap per side.
- Market proxy source: out-of-portfolio equal-weight fallback, saved to `data/market_data/market_proxy.parquet`.
- Leverage convention: all variants target dollar-neutral 100/100 books, approximately 2.0x gross exposure. Reported returns are on this long-short portfolio return stream, not a separately de-levered 1x capital allocation.
- Neutrality convention: V2/V3 are ex-ante beta-neutral to the rolling 60-day proxy estimate; realized beta remains a residual risk.

## Neutralization Grid
| variant | cost_bps | annualized_return | annualized_sharpe | max_drawdown | average_daily_turnover | average_gross_leverage | max_gross_leverage | average_net_beta | average_sector_concentration_long | average_sector_concentration_short | hit_rate | net_cumulative_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1_raw_fm_weekly_adv20 | 0 | 0.1012 | 0.5848 | -0.3114 | 0.0992 | 1.9819 | 2.0 | 0.4423 | 0.1959 | 0.2569 | 0.5064 | 1.8562 |
| V1_raw_fm_weekly_adv20 | 5 | 0.0874 | 0.5212 | -0.3131 | 0.0992 | 1.9819 | 2.0 | 0.4423 | 0.1959 | 0.2569 | 0.5031 | 1.4899 |
| V1_raw_fm_weekly_adv20 | 10 | 0.0738 | 0.4575 | -0.3168 | 0.0992 | 1.9819 | 2.0 | 0.4423 | 0.1959 | 0.2569 | 0.5016 | 1.1706 |
| V1_raw_fm_weekly_adv20 | 20 | 0.047 | 0.3302 | -0.3358 | 0.0992 | 1.9819 | 2.0 | 0.4423 | 0.1959 | 0.2569 | 0.4947 | 0.6494 |
| V2_beta_neutral_fm_weekly_adv20 | 0 | 0.1076 | 0.788 | -0.217 | 0.1653 | 1.9559 | 2.0 | 0.0017 | 0.1976 | 0.3398 | 0.5146 | 1.9975 |
| V2_beta_neutral_fm_weekly_adv20 | 5 | 0.0843 | 0.6388 | -0.2276 | 0.1653 | 1.9559 | 2.0 | 0.0017 | 0.1976 | 0.3398 | 0.5105 | 1.3849 |
| V2_beta_neutral_fm_weekly_adv20 | 10 | 0.0614 | 0.4894 | -0.2383 | 0.1653 | 1.9559 | 2.0 | 0.0017 | 0.1976 | 0.3398 | 0.5065 | 0.8975 |
| V2_beta_neutral_fm_weekly_adv20 | 20 | 0.0172 | 0.1905 | -0.2879 | 0.1653 | 1.9559 | 2.0 | 0.0017 | 0.1976 | 0.3398 | 0.4976 | 0.2008 |
| V3_beta_neutral_sector_capped_fm_weekly_adv20 | 0 | 0.1091 | 0.7985 | -0.2172 | 0.1662 | 1.9559 | 2.0 | 0.0027 | 0.1963 | 0.323 | 0.5157 | 2.0415 |
| V3_beta_neutral_sector_capped_fm_weekly_adv20 | 5 | 0.0856 | 0.6483 | -0.2278 | 0.1662 | 1.9559 | 2.0 | 0.0027 | 0.1963 | 0.323 | 0.5109 | 1.4172 |
| V3_beta_neutral_sector_capped_fm_weekly_adv20 | 10 | 0.0627 | 0.498 | -0.2386 | 0.1662 | 1.9559 | 2.0 | 0.0027 | 0.1963 | 0.323 | 0.5072 | 0.9208 |
| V3_beta_neutral_sector_capped_fm_weekly_adv20 | 20 | 0.0181 | 0.1971 | -0.288 | 0.1662 | 1.9559 | 2.0 | 0.0027 | 0.1963 | 0.323 | 0.4969 | 0.2128 |

## Proxy Diagnostics
| variant | proxy_source | proxy_start | proxy_end | proxy_n_days | average_ex_ante_beta | average_abs_ex_ante_beta | average_gross_leverage | max_gross_leverage | large_beta_exposure_days | realized_beta_to_proxy | realized_beta_2014_2019 | realized_beta_2020_2024 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1_raw_fm_weekly_adv20 | out_of_portfolio_equal_weight | 2014-01-03 | 2024-12-31 | 2767 | 0.4423 | 0.4462 | 1.9819 | 2.0 | 2466 | 0.5356 | 0.3736 | 0.6015 |
| V2_beta_neutral_fm_weekly_adv20 | out_of_portfolio_equal_weight | 2014-01-03 | 2024-12-31 | 2767 | 0.0017 | 0.002 | 1.9559 | 2.0 | 0 | 0.2176 | 0.1568 | 0.2419 |
| V3_beta_neutral_sector_capped_fm_weekly_adv20 | out_of_portfolio_equal_weight | 2014-01-03 | 2024-12-31 | 2767 | 0.0027 | 0.0045 | 1.9559 | 2.0 | 0 | 0.2191 | 0.1579 | 0.2437 |

## Ex-2020 Stress Summary
| variant | mean_annual_return_ex2020 | mean_annual_sharpe_ex2020 | worst_year_ex2020 | best_year_ex2020 | n_years_ex2020 |
| --- | --- | --- | --- | --- | --- |
| V1_raw_fm_weekly_adv20 | 0.0793 | 0.6033 | -0.1157 | 0.4094 | 10 |
| V2_beta_neutral_fm_weekly_adv20 | 0.0709 | 0.5759 | -0.0826 | 0.2099 | 10 |
| V3_beta_neutral_sector_capped_fm_weekly_adv20 | 0.0724 | 0.5897 | -0.0825 | 0.2108 | 10 |

## Recommendation
Final Pillar 4 production baseline: `V3_beta_neutral_sector_capped_fm_weekly_adv20`. The candidate passes the Stage 4.5 lock-in thresholds. At 10 bps, V1 Sharpe is 0.458, V2 Sharpe is 0.489, and V3 Sharpe is 0.498; the V2/V3 Sharpe difference is noise-level. V3 is preferred because the short-side sector concentration falls from 0.340 to 0.323 at comparable Sharpe. V3 average ex-ante beta is 0.003; realized beta remains non-zero and is carried into Pillar 5.
