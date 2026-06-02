# Pillar 5 Stage 5.2 Drawdown & Capital-at-Risk Summary

## Setup
- Production sizing from Stage 5.1: target vol 10%, gross 1.40x.
- Returns use the 10 bps primary transaction cost assumption.

## Top Drawdown Events
| start_date | trough_date | recovery_date | peak_to_trough | drawdown_duration_days | recovery_duration_days | market_proxy_return_same_window |
| --- | --- | --- | --- | --- | --- | --- |
| 2015-04-30 | 2016-02-11 | 2018-03-12 | -0.1732 | 198 | 523 | 0.5766 |
| 2021-03-01 | 2022-01-27 | 2022-11-14 | -0.1711 | 231 | 201 | 0.1873 |
| 2020-02-28 | 2020-03-18 | 2020-04-29 | -0.1227 | 13 | 29 | -0.0242 |
| 2023-08-01 | 2023-10-12 | ongoing | -0.1169 | 51 |  | 0.2691 |
| 2019-02-19 | 2019-08-27 | 2019-12-12 | -0.0885 | 132 | 75 | 0.1619 |

## Limit Simulation
| limit_line | threshold | n_triggers | fp_rate | post_trigger_60d_mean_ret | with_derisk_vs_without |
| --- | --- | --- | --- | --- | --- |
| soft_warning | -0.06 | 45 | 0.6667 | 0.0182 | -0.009 |
| hard_stop_derisk_50 | -0.12 | 18 | 0.7222 | 0.0362 | -0.0182 |
| kill_switch | -0.2 | 0 | 0.0 | nan | nan |

## Drawdown Reconciliation
- Daily reconciliation saved to `results/pillar5_stage52_dd_reconciliation.csv`.
- The lowest Pillar 4 rolling-return drawdown in the 2023-09/11 reconciliation window is -45.8% on 2023-10-12.
- On that same date, true Stage 4 V3 2x/10bps capital wealth DD is -16.3%, and Stage 5 sized 1.405x/10bps capital wealth DD is -11.7%.
- Multiplying the rolling-return DD by k would imply -32.2%, but that is the wrong risk object.
- The Pillar 4 `rolling_drawdown.csv` field is the drawdown of the trailing 252-day return series, not the capital wealth-curve drawdown used for production kill switches.
- Therefore the 2023-10 ~-45% value is not comparable to Stage 5 capital DD and should not be multiplied by k to infer a -31% live capital drawdown.

## Recommendation
Keep the -6% soft warning as an operational early-warning line; it triggered 45 times with 67% positive 60-day reversals. Keep the -12% hard-stop de-risk line as a capital-at-risk control; it triggered 18 times and the 50% de-risk simulation changed average 60-day return by -1.82%. Keep the -20% kill switch; it was not triggered historically at production sizing.
