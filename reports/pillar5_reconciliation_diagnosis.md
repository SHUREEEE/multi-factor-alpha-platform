# Pillar 5 Reconciliation Diagnosis

## Executive Summary
T_jump is 2014-04-01, not assumed. The most-supported hypothesis is H6: solver/config drift between Stage 4.5 and the Pillar 5 cache builder. Phase 3 severity is cosmetic economically, despite weight-level mismatch: Sharpe diff 0.007, return correlation 0.993. Recommended canonical path is neither-pending-fix. V3 NO-GO invariance is Y under the tested capacity proxy.

## Phase 1 Findings
- `T_jump`: 2014-04-01 (derived from first `weight_l1 >= 1e-10`, not hardcoded).
- True-zero days (`weight_l1 < 1e-12`): 414.
- Floating-point-noise days (`1e-12 <= weight_l1 < 1e-10`): 0.
- Material-diff days (`weight_l1 >= 1e-10`): 2354.
- Top-50 sector distribution is sector-spread by the >50% rule.
| sector | n_top50 | share_top50 |
| --- | --- | --- |
| Information Technology | 18 | 0.36 |
| Health Care | 8 | 0.16 |
| Consumer Discretionary | 7 | 0.14 |
| Unknown | 6 | 0.12 |
| Communication Services | 3 | 0.06 |
| Consumer Staples | 3 | 0.06 |
| Industrials | 2 | 0.04 |
| Financials | 1 | 0.02 |
| Materials | 1 | 0.02 |
| Real Estate | 1 | 0.02 |

## Phase 2 Hypothesis Table
| hypothesis_id | hypothesis | check_performed | result | supports_hypothesis_Y_N | evidence_pointer |
| --- | --- | --- | --- | --- | --- |
| H1 | Sector mapping changed on T_jump | Compared sector assignments available to both paths for top-50 diff names. | Both paths read the same static sector map artifact; no per-path sector assignment difference is observable in repo. | N | scripts/run_pillar4_stage45_neutralization.py:59-61; scripts/pillar5_common.py:157-158 |
| H2 | Beta input drift | Recomputed rolling 60d beta input from the locked market proxy for top-50 names on T_jump. | Single beta input source is used by both paths in current repo; 50/50 top names have beta values. No second historical beta snapshot exists for per-path comparison. | N | scripts/run_pillar4_stage45_neutralization.py:58; scripts/pillar5_common.py:156 |
| H3 | Universe membership retroactive change | Compared active symbol sets on T_jump and three trading days before/after. | 2014-04-01: recon_only=1, cache_only=2; 2014-04-02: recon_only=1, cache_only=1; 2014-04-03: recon_only=1, cache_only=1; 2014-04-04: recon_only=1, cache_only=2 | Y | results/diag_jump_date_top50.csv; active-set comparison in diagnosis script |
| H4 | Corporate-action retroactive adjustment | Searched repository for split/dividend/corporate-action files. | data unavailable: no split, dividend, or corporate-action dataset found under data/. | N/A | data/ recursive filename search for split/dividend/action returned no files |
| H5 | Price source divergence | Checked available price source for top-50 names on T_jump. | Only one price panel exists in repo; 50/50 top names found for T_jump. No second per-path price snapshot exists for comparison. | N | data/processed/prices.parquet; config/pillar4_candidate_factors.yaml |
| H6 | Neutralization solver / config drift between scripts | Compared Stage 4.5 reconstruction and Pillar 5 cache generation call signatures and input transform order. | Supported: Stage 4.5 applies beta_neutralize_weights(raw_weights, betas) then sector_cap_then_renormalize_beta(beta_neutral, sectors, betas, cap=SECTOR_CAP). Pillar 5 cache builder applies sector_cap_then_renormalize_beta(raw_weights, sectors, betas, cap=SECTOR_CAP) directly. Because sector_cap_then_renormalize_beta itself caps then beta-neutralizes, the cache path omits the initial beta-neutralization before sector capping. | Y | scripts/run_pillar4_stage45_neutralization.py:89-95; scripts/pillar5_common.py:146-159; src/portfolio/neutralization.py:52-60 |

### Most-Supported Hypothesis
H6 is the most-supported hypothesis. The day-of-jump pattern appears when rolling beta inputs first become available, and the code paths differ in neutralization order: Stage 4.5 runs beta-neutralization before sector capping, while the Pillar 5 cache builder applies the sector-cap-then-beta-neutralize helper directly to raw weights. This explains zero diffs before beta constraints bind and structural diffs afterward without requiring universe, price, or sector-map changes.

## Phase 3 Severity Numbers
| t_jump | sharpe_recon_post_jump | sharpe_cache_post_jump | sharpe_abs_diff | return_corr_post_jump | recon_top10_short_concentration_mean | recon_top10_short_concentration_p95 | recon_p95_participation_at_5m | recon_naive_participation_aum_ceiling_usd | recon_borrow_feasible_by_5_4_rule | recon_live_readiness_aum_ceiling_usd | cache_top10_short_concentration_mean | cache_top10_short_concentration_p95 | cache_p95_participation_at_5m | cache_naive_participation_aum_ceiling_usd | cache_borrow_feasible_by_5_4_rule | cache_live_readiness_aum_ceiling_usd | no_go_invariant_both_lt_5m | severity_classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014-04-01 | 0.4918 | 0.4986 | 0.0068 | 0.993 | 0.4986 | 0.995 | 0.0075 | 33371289.4407 | False | 0.0 | 0.4865 | 0.9766 | 0.007 | 35504046.9862 | False | 0.0 | True | cosmetic economically, despite weight-level mismatch |

## Recommended Canonical Path
Recommended path: **neither-pending-fix**. H6 shows implementation drift between the Stage 4.5 locked V3 definition and the Pillar 5 cache builder. The economic impact is cosmetic and the V3 NO-GO capacity conclusion is invariant, but REQ-F-014 / REQ-N-004 still require code-path convergence before a canonical path is declared.

## Required Changes To Converge Paths
| file | required_change |
| --- | --- |
| scripts/pillar5_common.py | Align `_build_baseline_artifacts()` with the Stage 4.5 V3 construction order or explicitly document a new canonical order. |
| scripts/run_pillar4_stage45_neutralization.py | Keep `_variant_weights()` as the declared Stage 4.5 V3 reference or deprecate it via an ADR if cache-builder order is chosen. |
| reports/pillar5_stage58_v4_specification.md | Update Section 0/2 after canonical-path decision and rerun reconciliation to satisfy REQ-F-014 / REQ-N-004. |

## V4 Unblock Recommendation
V4 should wait for a bounded remediation/ADR before implementation. The mismatch is economically cosmetic and the V3 NO-GO conclusion is invariant, but REQ-F-014 and REQ-N-004 are not satisfied because cache and reconstruction do not agree by construction.

## Deliverables
- `results/diag_jump_date_top50.csv`
- `results/diag_hypothesis_table.csv`
- `results/diag_severity.csv`
- `reports/pillar5_reconciliation_diagnosis.md`
