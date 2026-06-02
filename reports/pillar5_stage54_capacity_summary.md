# Pillar 5 Stage 5.4 Capacity & Live-Readiness Summary

## Executive Summary
Stage 5.4 surfaced three independent findings:

1. **Capacity ceiling <$5M** under live-readiness rules (Sharpe decay <20%, participation cap, borrow feasibility). Binding constraints are impact drag and short-book borrow feasibility.

2. **Impact drag is driven by tail rotation days, not normal-day trading.** Median daily turnover is 5.4%, but p95 is 106% and 181 days exceed 100% gross turnover. The turnover diagnostic isolates the source: non-rebalance-day mean turnover is about 4x rebalance-day mean turnover, indicating the daily beta-neutralization / sector-cap re-solve, not the weekly signal reshuffle, is the dominant turnover source. This is a V3 portfolio-construction issue addressable in V4 via a turnover penalty or no-trade band in the neutralization optimizer.

3. **Short book has structural concentration.** Top-10 short concentration is 48.7% and HTB-proxy share is 25.5%, independent of AUM. This fails prime-broker neutrality regardless of capacity sizing and should be addressed in V4 via an explicit short-side concentration constraint.

The capacity number in item 1 is conditional on item 2: if V4 fixes neutralization-layer turnover, the impact-based ceiling should revise materially upward. The structural short concentration in item 3 is unconditional.

## Headline
- Capacity ceiling (Sharpe decay < 20%): `<$5M` under the base c=0.5, 5% participation-cap scenario.
- Recommended AUM range: `not reached - not reached`.
- Hard ceiling (borrow infeasible): `<$5M`.
- Binding constraint: `impact / borrow`.
- Interim interpretation: under the specified live-readiness rules, V3 is not institution-ready as-is. The impact finding is driven by tail rotation days and is conditional on the turnover diagnostic below; the short-book concentration finding is unconditional.

## Capacity Curve
Paper Sharpe baseline is 0.498; the 20% decay line is 0.398. Production gross is 1.405x.
| AUM_usd | ann_sharpe_net | sharpe_decay_pct_vs_paper | p95_participation | max_participation | pct_days_above_participation_cap | naive_capacity_p50_usd | naive_capacity_p05_usd | naive_capacity_worst_day_usd | htb_share_short | top10_short_concentration | borrow_feasible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5000000 | 0.3913 | 0.2143 | 0.007 | 0.0379 | 0.0 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 10000000 | 0.3471 | 0.303 | 0.0141 | 0.0757 | 0.004 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 25000000 | 0.2594 | 0.4792 | 0.0352 | 0.1894 | 0.0246 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 50000000 | 0.1605 | 0.6777 | 0.0704 | 0.3787 | 0.1178 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 100000000 | 0.0208 | 0.9582 | 0.1408 | 0.7575 | 0.4588 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 250000000 | -0.2558 | 1.5136 | 0.3521 | 1.8937 | 0.953 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 500000000 | -0.5656 | 2.1358 | 0.7042 | 3.7874 | 0.978 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 1000000000 | -0.9985 | 3.0049 | 1.4083 | 7.5749 | 0.978 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 2000000000 | -1.5948 | 4.2024 | 2.8166 | 15.1497 | 0.978 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |
| 5000000000 | -2.6993 | 6.4202 | 7.0415 | 37.8743 | 0.978 | 103693571.33 | 35504046.9862 | 6600787.0782 | 0.2551 | 0.4865 | False |

## Constraint Trigger Points
| constraint | trigger_AUM_usd |
| --- | --- |
| Participation > 5% on >5% of days | 50000000.0 |
| Net Sharpe decay > 20% | 5000000.0 |
| Borrow infeasible | 5000000.0 |

## Impact Formula Audit
Single-day audit rows decompose participation, impact bps, `|Delta w|`, and NAV-bps cost for AUM=$100M, c=0.5. `delta_weight_gross` sums to portfolio gross turnover; `cost_bps_of_nav` sums to that day's impact drag.
| audit_date | ticker | participation | daily_vol | delta_weight | delta_weight_gross | impact_bps_i | cost_bps_of_nav | annualized_cost_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-06-15 | __TOTAL__ | 0.0013 | 0.018 | 0.0258 | 0.0362 | 1.4252 | 0.2806 | 70.7085 |
| 2023-06-15 | PDD | 0.0018 | 0.0387 | 0.0017 | 0.0023 | 8.1076 | 0.019 | 4.7872 |
| 2023-06-15 | ARES | 0.0253 | 0.0191 | 0.0009 | 0.0012 | 15.1862 | 0.0182 | 4.5797 |
| 2023-06-15 | SYF | 0.0166 | 0.0199 | 0.0008 | 0.0012 | 12.814 | 0.0152 | 3.8244 |
| 2023-06-15 | GNRC | 0.0104 | 0.0334 | 0.0005 | 0.0007 | 17.0192 | 0.0118 | 2.983 |
| 2023-06-15 | APO | 0.0191 | 0.0206 | 0.0006 | 0.0008 | 14.2318 | 0.0114 | 2.8643 |
| 2023-06-15 | MSTR | 0.0043 | 0.0499 | 0.0005 | 0.0006 | 16.4144 | 0.0105 | 2.6535 |
| 2023-06-15 | KKR | 0.024 | 0.0188 | 0.0005 | 0.0007 | 14.5753 | 0.0101 | 2.5358 |
| 2023-06-15 | FSLR | 0.0058 | 0.042 | 0.0004 | 0.0005 | 16.033 | 0.0088 | 2.2207 |
| 2023-06-15 | COF | 0.009 | 0.0213 | 0.0006 | 0.0008 | 10.1268 | 0.008 | 2.0216 |
| 2023-06-15 | JBL | 0.0144 | 0.0167 | 0.0005 | 0.0008 | 10.0111 | 0.0077 | 1.9349 |
| 2023-06-15 | DDOG | 0.0046 | 0.0363 | 0.0004 | 0.0006 | 12.2868 | 0.0077 | 1.9325 |
| 2023-06-15 | OMC | 0.0145 | 0.015 | 0.0006 | 0.0008 | 9.0275 | 0.0073 | 1.8387 |
| 2023-06-15 | CIEN | 0.014 | 0.0243 | 0.0003 | 0.0005 | 14.3382 | 0.007 | 1.7634 |
| 2023-06-15 | MRNA | 0.0046 | 0.0253 | 0.0004 | 0.0006 | 8.5289 | 0.0053 | 1.3301 |
| 2023-06-15 | DLTR | 0.0045 | 0.0222 | 0.0005 | 0.0007 | 7.4284 | 0.0049 | 1.2224 |
| 2023-06-15 | MCO | 0.0058 | 0.0113 | 0.0007 | 0.001 | 4.2935 | 0.0045 | 1.136 |
| 2023-06-15 | WBD | 0.003 | 0.0322 | 0.0004 | 0.0005 | 8.8175 | 0.0045 | 1.1238 |
| 2023-06-15 | KLAC | 0.0044 | 0.0238 | 0.0004 | 0.0006 | 7.9071 | 0.0045 | 1.1238 |
| 2023-06-15 | COHR | 0.0054 | 0.0405 | 0.0002 | 0.0003 | 14.9088 | 0.0042 | 1.0625 |
| 2023-06-15 | DG | 0.0028 | 0.0285 | 0.0003 | 0.0005 | 7.562 | 0.0037 | 0.9336 |
| 2023-04-20 | __TOTAL__ | 0.0016 | 0.0187 | 1.2453 | 1.7496 | 1.4395 | 16.7564 | 4222.6191 |
| 2023-04-20 | BLDR | 0.0306 | 0.0212 | 0.0734 | 0.1031 | 18.5475 | 1.9121 | 481.8423 |
| 2023-04-20 | CPAY | 0.0644 | 0.0213 | 0.0496 | 0.0697 | 27.0313 | 1.883 | 474.5039 |
| 2023-04-20 | ARES | 0.0711 | 0.0207 | 0.0357 | 0.0501 | 27.5257 | 1.3789 | 347.4768 |
| 2023-04-20 | VST | 0.0395 | 0.0273 | 0.0267 | 0.0376 | 27.1665 | 1.0206 | 257.2038 |
| 2023-04-20 | MELI | 0.0099 | 0.0227 | 0.0379 | 0.0533 | 11.3196 | 0.6028 | 151.9108 |
| 2023-04-20 | TPL | 0.0374 | 0.0223 | 0.0192 | 0.027 | 21.5442 | 0.5824 | 146.7611 |
| 2023-04-20 | NEM | 0.0115 | 0.0218 | 0.032 | 0.045 | 11.6683 | 0.5249 | 132.2622 |
| 2023-04-20 | TRGP | 0.0315 | 0.0185 | 0.0215 | 0.0302 | 16.4417 | 0.4965 | 125.1079 |
| 2023-04-20 | FICO | 0.0279 | 0.0164 | 0.0236 | 0.0332 | 13.7277 | 0.456 | 114.9136 |
| 2023-04-20 | PPG | 0.0213 | 0.0171 | 0.0257 | 0.0361 | 12.4774 | 0.451 | 113.642 |
| 2023-04-20 | NTAP | 0.0268 | 0.0153 | 0.0231 | 0.0324 | 12.5558 | 0.4074 | 102.6543 |
| 2023-04-20 | BALL | 0.0296 | 0.0181 | 0.0163 | 0.0229 | 15.5526 | 0.3564 | 89.8004 |
| 2023-04-20 | BAX | 0.011 | 0.0229 | 0.0204 | 0.0287 | 12.0189 | 0.3448 | 86.8796 |
| 2023-04-20 | DELL | 0.0173 | 0.0173 | 0.0214 | 0.0301 | 11.37 | 0.3419 | 86.1607 |
| 2023-04-20 | CF | 0.0144 | 0.0217 | 0.0182 | 0.0255 | 13.0203 | 0.3324 | 83.7644 |
| 2023-04-20 | MRNA | 0.005 | 0.0272 | 0.0244 | 0.0343 | 9.6291 | 0.3299 | 83.1353 |
| 2023-04-20 | OKE | 0.0245 | 0.0159 | 0.0188 | 0.0264 | 12.4229 | 0.3284 | 82.7522 |
| 2023-04-20 | UAL | 0.006 | 0.0253 | 0.0202 | 0.0284 | 9.7723 | 0.2775 | 69.9304 |

## Turnover Distribution Diagnostic
This separates normal-day impact from tail rotation-day impact. Production gross turnover is computed from normalized 1x weights multiplied by 1.405x production gross.
Turnover is highly right-tailed: median production gross turnover is 5.4%, but p95 is 106.3%, p99 is 140.9%, and 181 days exceed 100% gross turnover. Among the top-10 turnover days, 90% are not weekly signal rebalance days, which points to the daily beta-neutralization / sector-cap re-solve as the likely source of final-weight rotation rather than the raw weekly ranking schedule alone. Crucially, non-rebalance-day mean turnover (27.4%) exceeds rebalance-day mean turnover (7.0%) by about 3.9x. This inverts the expected ordering for a weekly-rebalanced strategy and isolates the source of turnover to the daily post-processing layer. The single-name top-delta footprints on rotation days are consistent with the neutralization optimizer wholesale-flipping individual positions when beta/sector drift crosses a constraint boundary.
| metric | value |
| --- | --- |
| mean | 0.2335 |
| median | 0.0542 |
| p75 | 0.1712 |
| p95 | 1.0626 |
| p99 | 1.4086 |
| max | 1.7844 |
| rotation_days_gt_50pct | 551.0 |
| rotation_days_gt_100pct | 181.0 |
| rebalance_day_mean | 0.0698 |
| non_rebalance_day_mean | 0.2744 |
| non_rebalance_day_p95 | 1.1037 |
| hist_0-5% | 1311.0 |
| hist_5-10% | 516.0 |
| hist_10-25% | 338.0 |
| hist_25-50% | 51.0 |
| hist_50-100% | 370.0 |
| hist_>100% | 181.0 |

### Top Rotation Days
| date | production_gross_turnover | turnover_1x | is_rebalance_day | weekday | month | calendar_context | top_delta_names | n_names_changed_gt_1pct_gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014-10-17 | 1.7844 | 1.27 | False | Friday | 10 | earnings-season | ROP:24.97%; FDX:17.61%; SHW:10.30%; INTU:8.39%; HUBB:7.22% | 51 |
| 2023-04-20 | 1.7496 | 1.2453 | False | Thursday | 4 | earnings-season, Thursday | BLDR:10.31%; CPAY:6.97%; ASML:6.64%; LULU:6.17%; MELI:5.33% | 52 |
| 2023-09-27 | 1.6765 | 1.1932 | False | Wednesday | 9 | month-end | LULU:70.25%; INTC:11.36%; INTU:8.03%; BX:4.29%; QQQ:4.04% | 31 |
| 2022-08-30 | 1.6181 | 1.1517 | False | Tuesday | 8 | month-end | ALB:36.80%; ANET:17.77%; AMP:17.23%; HLT:13.91%; QQQ:10.65% | 21 |
| 2023-04-27 | 1.5829 | 1.1266 | False | Thursday | 4 | earnings-season, Thursday, month-end | PPG:13.41%; TYL:8.53%; TEL:7.70%; SHW:7.25%; CPAY:6.93% | 41 |
| 2024-01-30 | 1.5756 | 1.1214 | False | Tuesday | 1 | earnings-season, month-end | ASML:17.68%; DHI:13.27%; MELI:10.76%; OMC:10.08%; COO:9.92% | 38 |
| 2023-08-30 | 1.5643 | 1.1134 | True | Wednesday | 8 | month-end | INTU:70.25%; IR:35.06%; DELL:11.01%; CTSH:8.06%; ETN:7.14% | 8 |
| 2023-10-04 | 1.5638 | 1.113 | False | Wednesday | 10 | month-start | CTAS:70.25%; META:9.91%; WELL:7.77%; GOOG:7.59%; HPE:7.46% | 18 |
| 2022-09-28 | 1.516 | 1.079 | False | Wednesday | 9 | month-end | ALB:37.63%; PTC:25.35%; QQQ:19.84%; TEL:7.21%; MAR:6.94% | 20 |
| 2022-08-02 | 1.5141 | 1.0776 | False | Tuesday | 8 | month-start | CDNS:17.58%; GDDY:9.53%; SNPS:7.70%; LEN:7.31%; MRVL:6.98% | 44 |

## Structural Short-Book Concentration Constraint
Independent of AUM scaling, the short book exhibits structural concentration: 48.7% of short notional sits in the top-10 short names, and 25.5% sits in the HTB-proxy tier. This is a portfolio-construction issue, not merely a capacity issue. Even at sub-$10M AUM, the rule flags V3 as prime-broker dependent rather than broker-neutral.

## Impact Coefficient Sensitivity
| impact_coefficient | impact_only_capacity_ceiling_usd | borrow_adjusted_capacity_ceiling_usd |
| --- | --- | --- |
| 0.3 | 10000000.0 | 0.0 |
| 0.5 | 0.0 | 0.0 |
| 1.0 | 0.0 | 0.0 |

## Top Per-Name Capacity Bottlenecks
| ticker | mean_weight | mean_abs_weight | mean_adv20_usd | implied_individual_ceiling_at_5pct_adv | pct_days_above_5pct_participation_at_500M |
| --- | --- | --- | --- | --- | --- |
| QQQ | -0.0251 | 0.0251 | 9720914692.4582 | 19395257219.7517 | 0.0 |
| SPY | -0.0141 | 0.0141 | 24670806036.958 | 87528369880.9981 | 0.0 |
| APH | -0.012 | 0.012 | 144093037.9373 | 598498911.2353 | 0.4346 |
| BK | -0.0095 | 0.0095 | 196299625.7459 | 1032810865.1814 | 0.1853 |
| ASML | -0.0085 | 0.0095 | 360625667.8347 | 1907208220.0205 | 0.1521 |
| TSLA | 0.0088 | 0.0093 | 11270939147.5286 | 60426679671.873 | 0.0 |
| CVX | -0.0093 | 0.0093 | 774680587.269 | 4153714963.1853 | 0.0145 |
| MRNA | 0.0091 | 0.0091 | 1145251096.1242 | 6327282823.5703 | 0.0213 |
| TEL | -0.009 | 0.009 | 149608223.0104 | 835799582.5741 | 0.2402 |
| WBD | 0.0085 | 0.0089 | 181704167.9601 | 1019563288.2493 | 0.2283 |

## Short Book Constraints
| AUM_usd | n_short_names | short_gross_usd | htb_notional_usd | htb_share | top10_concentration | borrow_feasible |
| --- | --- | --- | --- | --- | --- | --- |
| 5000000 | 36 | 3512468.4016 | 896147.5655 | 0.2551 | 0.4865 | False |
| 10000000 | 36 | 7024936.8032 | 1792295.131 | 0.2551 | 0.4865 | False |
| 25000000 | 36 | 17562342.0079 | 4480737.8274 | 0.2551 | 0.4865 | False |
| 50000000 | 36 | 35124684.0158 | 8961475.6548 | 0.2551 | 0.4865 | False |
| 100000000 | 36 | 70249368.0316 | 17922951.3095 | 0.2551 | 0.4865 | False |
| 250000000 | 36 | 175623420.0789 | 44807378.2738 | 0.2551 | 0.4865 | False |
| 500000000 | 36 | 351246840.1578 | 89614756.5475 | 0.2551 | 0.4865 | False |
| 1000000000 | 36 | 702493680.3156 | 179229513.095 | 0.2551 | 0.4865 | False |
| 2000000000 | 36 | 1404987360.6313 | 358459026.1901 | 0.2551 | 0.4865 | False |
| 5000000000 | 36 | 3512468401.5781 | 896147565.4751 | 0.2551 | 0.4865 | False |

## Caveats
- Square-root impact is a first-order approximation; live impact depends on order schedule (VWAP/TWAP/POV), intraday liquidity, spread, and crowding.
- Borrow availability is proxied by average dollar-volume quintiles because live float, utilization, and rebate data are unavailable; live capacity is subject to prime-broker confirmation.
- ADV20 is treated as a stationary liquidity estimate; live capacity should re-evaluate ADV in real time, especially around earnings and index events.
- Impact is applied to `|Delta weight|` turnover, not gross exposure. Participation is computed as `(AUM x gross x |w|) / ADV20`.
