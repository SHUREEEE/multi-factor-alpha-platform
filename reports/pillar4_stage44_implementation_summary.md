# Pillar 4 Stage 4.4 Implementation Validation

## Setup
- Main portfolio: `dedup_3f_fm_weighted_idio`.
- Control portfolio: `dedup_3f_equal_weight_idio`.
- Rebalance modes: daily and weekly_5d.
- Liquidity modes: none and adv20_filtered.
- Cost levels: 0, 5, 10, and 20 one-way bps.
- Two-way interpretation: a 10 bps one-way setting is roughly 20 bps round-trip for a full exit and re-entry.

## Table 1: Implementation Grid
| portfolio | rebalance_frequency | liquidity_filter | cost_bps | annualized_return | annualized_sharpe | max_drawdown | average_daily_turnover | long_turnover | short_turnover | hit_rate | net_cumulative_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dedup_3f_equal_weight_idio | daily | none | 0 | 0.1527 | 0.8154 | -0.3163 | 0.2603 | 0.101 | 0.1595 | 0.5075 | 3.7034 |
| dedup_3f_equal_weight_idio | daily | none | 5 | 0.1153 | 0.6486 | -0.3199 | 0.2603 | 0.101 | 0.1595 | 0.4998 | 2.2815 |
| dedup_3f_equal_weight_idio | daily | none | 10 | 0.079 | 0.4817 | -0.3348 | 0.2603 | 0.101 | 0.1595 | 0.4933 | 1.2893 |
| dedup_3f_equal_weight_idio | daily | none | 20 | 0.01 | 0.1482 | -0.3866 | 0.2603 | 0.101 | 0.1595 | 0.4809 | 0.114 |
| dedup_3f_equal_weight_idio | daily | adv20_filtered | 0 | 0.143 | 0.7637 | -0.3268 | 0.2667 | 0.104 | 0.1629 | 0.5038 | 3.2868 |
| dedup_3f_equal_weight_idio | daily | adv20_filtered | 5 | 0.1049 | 0.5954 | -0.3311 | 0.2667 | 0.104 | 0.1629 | 0.4969 | 1.9644 |
| dedup_3f_equal_weight_idio | daily | adv20_filtered | 10 | 0.0681 | 0.427 | -0.3408 | 0.2667 | 0.104 | 0.1629 | 0.4896 | 1.0499 |
| dedup_3f_equal_weight_idio | daily | adv20_filtered | 20 | -0.0019 | 0.0905 | -0.4116 | 0.2667 | 0.104 | 0.1629 | 0.474 | -0.02 |
| dedup_3f_equal_weight_idio | weekly_5d | none | 0 | 0.1304 | 0.7198 | -0.3217 | 0.1175 | 0.0473 | 0.0707 | 0.5089 | 2.7964 |
| dedup_3f_equal_weight_idio | weekly_5d | none | 5 | 0.1136 | 0.6439 | -0.3234 | 0.1175 | 0.0473 | 0.0707 | 0.5042 | 2.2269 |
| dedup_3f_equal_weight_idio | weekly_5d | none | 10 | 0.0971 | 0.568 | -0.3253 | 0.1175 | 0.0473 | 0.0707 | 0.5005 | 1.7426 |
| dedup_3f_equal_weight_idio | weekly_5d | none | 20 | 0.0648 | 0.4161 | -0.3289 | 0.1175 | 0.0473 | 0.0707 | 0.4947 | 0.9809 |
| dedup_3f_equal_weight_idio | weekly_5d | adv20_filtered | 0 | 0.1053 | 0.6003 | -0.3444 | 0.1204 | 0.0491 | 0.0717 | 0.4987 | 1.9744 |
| dedup_3f_equal_weight_idio | weekly_5d | adv20_filtered | 5 | 0.0885 | 0.5236 | -0.3462 | 0.1204 | 0.0491 | 0.0717 | 0.4962 | 1.518 |
| dedup_3f_equal_weight_idio | weekly_5d | adv20_filtered | 10 | 0.072 | 0.447 | -0.3481 | 0.1204 | 0.0491 | 0.0717 | 0.4933 | 1.1315 |
| dedup_3f_equal_weight_idio | weekly_5d | adv20_filtered | 20 | 0.0397 | 0.2937 | -0.3517 | 0.1204 | 0.0491 | 0.0717 | 0.4896 | 0.5271 |
| dedup_3f_fm_weighted_idio | daily | none | 0 | 0.1477 | 0.798 | -0.2871 | 0.2132 | 0.0826 | 0.1308 | 0.5118 | 3.4825 |
| dedup_3f_fm_weighted_idio | daily | none | 5 | 0.117 | 0.6603 | -0.2971 | 0.2132 | 0.0826 | 0.1308 | 0.5049 | 2.3379 |
| dedup_3f_fm_weighted_idio | daily | none | 10 | 0.0872 | 0.5226 | -0.3193 | 0.2132 | 0.0826 | 0.1308 | 0.5013 | 1.4856 |
| dedup_3f_fm_weighted_idio | daily | none | 20 | 0.0299 | 0.2472 | -0.3712 | 0.2132 | 0.0826 | 0.1308 | 0.4871 | 0.3781 |
| dedup_3f_fm_weighted_idio | daily | adv20_filtered | 0 | 0.1348 | 0.733 | -0.2944 | 0.2191 | 0.0858 | 0.1335 | 0.5137 | 2.964 |
| dedup_3f_fm_weighted_idio | daily | adv20_filtered | 5 | 0.1036 | 0.5934 | -0.3115 | 0.2191 | 0.0858 | 0.1335 | 0.5049 | 1.9276 |
| dedup_3f_fm_weighted_idio | daily | adv20_filtered | 10 | 0.0734 | 0.4539 | -0.3334 | 0.2191 | 0.0858 | 0.1335 | 0.498 | 1.1621 |
| dedup_3f_fm_weighted_idio | daily | adv20_filtered | 20 | 0.0152 | 0.1748 | -0.3751 | 0.2191 | 0.0858 | 0.1335 | 0.4863 | 0.1791 |
| dedup_3f_fm_weighted_idio | weekly_5d | none | 0 | 0.1303 | 0.724 | -0.2896 | 0.0957 | 0.0384 | 0.0575 | 0.5086 | 2.7925 |
| dedup_3f_fm_weighted_idio | weekly_5d | none | 5 | 0.1166 | 0.6617 | -0.2913 | 0.0957 | 0.0384 | 0.0575 | 0.5067 | 2.3223 |
| dedup_3f_fm_weighted_idio | weekly_5d | none | 10 | 0.1031 | 0.5993 | -0.297 | 0.0957 | 0.0384 | 0.0575 | 0.5027 | 1.9102 |
| dedup_3f_fm_weighted_idio | weekly_5d | none | 20 | 0.0766 | 0.4746 | -0.3167 | 0.0957 | 0.0384 | 0.0575 | 0.498 | 1.2329 |
| dedup_3f_fm_weighted_idio | weekly_5d | adv20_filtered | 0 | 0.1012 | 0.5848 | -0.3114 | 0.0992 | 0.0406 | 0.0589 | 0.5064 | 1.8562 |
| dedup_3f_fm_weighted_idio | weekly_5d | adv20_filtered | 5 | 0.0874 | 0.5212 | -0.3131 | 0.0992 | 0.0406 | 0.0589 | 0.5031 | 1.4899 |
| dedup_3f_fm_weighted_idio | weekly_5d | adv20_filtered | 10 | 0.0738 | 0.4575 | -0.3168 | 0.0992 | 0.0406 | 0.0589 | 0.5016 | 1.1706 |
| dedup_3f_fm_weighted_idio | weekly_5d | adv20_filtered | 20 | 0.047 | 0.3302 | -0.3358 | 0.0992 | 0.0406 | 0.0589 | 0.4947 | 0.6494 |

## Table 2: Yearly Diagnostics Summary
| portfolio | rebalance_frequency | liquidity_filter | mean_annual_return | mean_annual_sharpe | worst_year_return | best_year_return | mean_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dedup_3f_equal_weight_idio | daily | adv20_filtered | 0.159 | 0.9021 | -0.0389 | 0.6632 | 0.2667 |
| dedup_3f_equal_weight_idio | daily | none | 0.17 | 0.9686 | -0.0646 | 0.6368 | 0.2603 |
| dedup_3f_equal_weight_idio | weekly_5d | adv20_filtered | 0.1146 | 0.6789 | -0.0839 | 0.4273 | 0.1204 |
| dedup_3f_equal_weight_idio | weekly_5d | none | 0.1412 | 0.8508 | -0.0559 | 0.4517 | 0.1175 |
| dedup_3f_fm_weighted_idio | daily | adv20_filtered | 0.1536 | 0.8203 | -0.0971 | 0.6836 | 0.2191 |
| dedup_3f_fm_weighted_idio | daily | none | 0.1686 | 0.896 | -0.0927 | 0.6988 | 0.2131 |
| dedup_3f_fm_weighted_idio | weekly_5d | adv20_filtered | 0.1149 | 0.6602 | -0.1157 | 0.4711 | 0.0992 |
| dedup_3f_fm_weighted_idio | weekly_5d | none | 0.1454 | 0.8357 | -0.1117 | 0.502 | 0.0957 |

## Table 3: Risk Checks
| portfolio | rebalance_frequency | liquidity_filter | average_net_beta | average_sector_concentration_long | average_sector_concentration_short | average_cross_sectional_names_long | average_cross_sectional_names_short |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dedup_3f_equal_weight_idio | daily | none | 0.5846 | 0.1948 | 0.2405 | 49.8466 | 49.9082 |
| dedup_3f_equal_weight_idio | daily | adv20_filtered | 0.5883 | 0.199 | 0.2479 | 44.7938 | 44.9042 |
| dedup_3f_equal_weight_idio | weekly_5d | none | 0.5722 | 0.1952 | 0.2396 | 49.8436 | 49.9056 |
| dedup_3f_equal_weight_idio | weekly_5d | adv20_filtered | 0.5736 | 0.1993 | 0.248 | 44.7944 | 44.9056 |
| dedup_3f_fm_weighted_idio | daily | none | 0.5862 | 0.1943 | 0.2505 | 49.8466 | 49.9082 |
| dedup_3f_fm_weighted_idio | daily | adv20_filtered | 0.5862 | 0.1973 | 0.2595 | 44.7938 | 44.9042 |
| dedup_3f_fm_weighted_idio | weekly_5d | none | 0.5724 | 0.1941 | 0.2503 | 49.8436 | 49.9056 |
| dedup_3f_fm_weighted_idio | weekly_5d | adv20_filtered | 0.5744 | 0.1977 | 0.2593 | 44.7944 | 44.9056 |

## Interpretation
- Weekly_5d is the main Stage 4.4 discovery: it cuts turnover by more than half for the FM baseline and improves cost-adjusted Sharpe at 10 bps and 20 bps.
- The ADV20 filter reduces Sharpe by roughly 0.05-0.14 across matched configurations. This means part of the alpha comes from less liquid names, but the qualitative FM/weekly conclusion does not collapse.
- The portfolio carries average net beta around 0.57-0.59 against the equal-weight pool proxy. A significant part of realized return, especially in strong market years, may be directional beta rather than pure factor alpha.
- Performance is partially concentrated in 2020; the strongest 2020 slice is `dedup_3f_fm_weighted_idio` with `daily` and annual return 69.9%. Stage 4.5 should report results with and without 2020.

## Recommendation
Use `dedup_3f_fm_weighted_idio` with `weekly_5d` as the Stage 4.5 implementation baseline, with `daily` kept as a high-frequency challenger. At 10 bps without filtering, FM daily Sharpe is 0.523 and FM weekly Sharpe is 0.599; with ADV20 filtering, daily Sharpe is 0.454 and weekly Sharpe is 0.458. The grid-selected practical winner is `dedup_3f_fm_weighted_idio` with `daily`, but the larger research conclusion is that weekly rebalance is the cost-aware default. Stage 4.5 must beta-neutralize this configuration before it can be treated as deployable.
