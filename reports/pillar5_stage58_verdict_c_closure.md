# Pillar 5 Stage 5.8 Verdict C Closure

## Executive Summary
ADR-0001 Option 1 was executed and post-ADR reconciliation passed exactly: mean weight L1 0.00e+00, max return diff 0.0000 bps. Stage 4 drift check flagged 12 material metric moves under the strict published-precision rule. REQ-F-014 and REQ-N-004 are now SATISFIED-POST-ADR, and the V4 gate is GO; provisional labeling is no longer required.

## Change Applied
```diff
 def _variant_weights(raw_weights: pd.DataFrame, betas: pd.DataFrame, sectors: pd.Series) -> dict[str, pd.DataFrame]:
     beta_neutral = beta_neutralize_weights(raw_weights, betas)
-    capped = sector_cap_then_renormalize_beta(beta_neutral, sectors, betas, cap=SECTOR_CAP)
+    capped = sector_cap_then_renormalize_beta(raw_weights, sectors, betas, cap=SECTOR_CAP)
     return {
         "V1_raw_fm_weekly_adv20": raw_weights,
         "V2_beta_neutral_fm_weekly_adv20": beta_neutral,
```

## Acceptance Evidence
- Reconstructed post-ADR weights: `results/pillar4_stage45_v3_reconstructed_post_adr.parquet`.
- Post-ADR reconciliation: `results/pillar5_stage58_v3_reconciliation_post_adr.csv`.
- True-zero days: 2768.
- FP-noise days: 0.
- Material-diff days: 0.
- Mean weight L1: 0.00e+00.
- Max weight L1: 0.00e+00.
- Max return diff: 0.0000 bps.

## Stage 4 Drift Table
Material metric count: 12.
Stage 4 documentation needs a separate update workstream because at least one published metric moved under the strict published-precision rule.
| metric | pre_value | post_value | abs_diff | rel_diff_pct | materiality_threshold | published_precision_abs_threshold | material_Y_N |
| --- | --- | --- | --- | --- | --- | --- | --- |
| annualized_return | 0.0610195470121799 | 0.0626513699786888 | 0.0016318229665089 | 2.674262668949645 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| annualized_sharpe | 0.4911325180889453 | 0.4979589547477876 | 0.0068264366588423 | 1.3899378288786044 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| average_abs_net_beta | 3.1445980326916406e-16 | 0.0044843899267839 | 0.0044843899267836 | inf | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| average_daily_turnover | 0.1710949906079515 | 0.1661586145239035 | 0.0049363760840479 | 2.885166927744388 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| average_gross_leverage | 1.9559248554913296 | 1.9559248554913296 | 0.0 | 0.0 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | N |
| average_net_beta | 1.1560550981389584e-17 | 0.0027321378319784 | 0.0027321378319784 | inf | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| average_sector_concentration_long | 0.1962879791456923 | 0.1963087249614747 | 2.07458157824858e-05 | 0.0105690709501306 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | N |
| average_sector_concentration_short | 0.2552680039193978 | 0.3230105135849656 | 0.0677425096655677 | 26.537798950689417 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| hit_rate | 0.5086811968969339 | 0.5072035463612855 | 0.0014776505356484 | 0.290486564996387 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| large_beta_exposure_days | 0.0 | 0.0 | 0.0 | 0.0 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.5 | N |
| long_turnover | 0.0614962374824946 | 0.0605262633748279 | 0.0009699741076666 | 1.5772901682688405 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| max_drawdown | -0.2442149432332118 | -0.2385509553880652 | 0.0056639878451465 | 2.3192634202313123 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| max_gross_leverage | 2.000000000000001 | 2.000000000000001 | 0.0 | 0.0 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | N |
| n_days | 2707.0 | 2707.0 | 0.0 | 0.0 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.5 | N |
| net_cumulative_return | 0.8893927043342629 | 0.9208423332560012 | 0.0314496289217383 | 3.5360790310596597 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| realized_beta_to_proxy | 0.2156847078573169 | 0.2190955615671078 | 0.0034108537097909 | 1.5814072975666595 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |
| short_turnover | 0.1097710989477398 | 0.1058093597901607 | 0.003961739157579 | 3.609091277718931 | rel_diff_pct > 5% OR abs_diff > published_precision_threshold | 0.0005 | Y |

## Hash Audit Trail
| path | pre_hash | post_hash | changed |
| --- | --- | --- | --- |
| scripts/run_pillar4_stage45_neutralization.py | 8af443cca703384703b78f10251ed50efe06857ea94a3281912cec00c88ef06a | d8395e75e590cfa36da3b30e66086e0217a911dbd64ec0d071359781bcb17149 | True |
| scripts/pillar5_common.py | efcad96678508604cdd9b7b340cc833fa37fc4b466d00287aa876f305df246eb | efcad96678508604cdd9b7b340cc833fa37fc4b466d00287aa876f305df246eb | False |
| src/portfolio/neutralization.py | 238bf9efe414944b7a00ebd8f086752b0d883ae01e15efd7d4147fc716e4f852 | 238bf9efe414944b7a00ebd8f086752b0d883ae01e15efd7d4147fc716e4f852 | False |
| results/pillar5_artifacts/v3_weights.parquet | cc90916e3411e78b8c8c385e99f1f7de5f5212108991e6e0d504ff8e1446506a | cc90916e3411e78b8c8c385e99f1f7de5f5212108991e6e0d504ff8e1446506a | False |
| results/pillar5_stage58_v3_reconciliation.csv | 7f8264c0bbeeb5df1a8b47a198feb2f94960bb8c5340d7066deb35455a6b7b13 | 7f8264c0bbeeb5df1a8b47a198feb2f94960bb8c5340d7066deb35455a6b7b13 | False |
| reports/pillar5_reconciliation_diagnosis.md | 1486b336009f33cd47fd59d6c22263c55129df477be2569d47fffb133b8fb300 | 1486b336009f33cd47fd59d6c22263c55129df477be2569d47fffb133b8fb300 | False |

Cache parquet hash unchanged: True.
Source files changed since Step 2: scripts/run_pillar4_stage45_neutralization.py.

## REQ-F-014 / REQ-N-004 Closure Citations
- `results/pillar5_v4_unblock_classification.csv`: REQ-F-014 and REQ-N-004 are `SATISFIED-POST-ADR`.
- `reports/pillar5_v4_unblock_gate.md`: Formal Verdict is `GO`.
- `results/pillar5_stage58_v3_reconciliation_post_adr.csv`: source-of-truth reconciliation passes exactly.

## V4 Unblock Status
GO. Provisional labeling is no longer required for V4 kickoff, subject to the separate Stage 4 documentation update workstream noted above.
