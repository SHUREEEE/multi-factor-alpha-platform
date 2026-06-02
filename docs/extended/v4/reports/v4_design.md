# V4 Design

## Status
Design only. This document does not authorize V4 implementation, create V4 modules, or modify production scripts. Implementation is a separate change-control event.

## 1. Canonical Book Reference
V4 starts from the post-ADR-0001 canonical V3 book. ADR-0001 accepted Option 1, the cache order / single-pass neutralization path, where `sector_cap_then_renormalize_beta(raw_weights, sectors, betas, cap=SECTOR_CAP)` is applied directly to raw weights.

The V3 source-of-truth issue is closed: `results/pillar5_stage58_v3_reconciliation_post_adr_summary.json` reports `accept_mean_l1 = true`, `accept_max_return_diff = true`, mean weight L1 = 0.0, max return diff = 0.0000 bps, and 2768 true-zero reconciliation days. V4 does not need provisional baseline labeling.

V4 must preserve the Pillar 5 mandate: it is not a Sharpe-maximization project. The design target is to remove launch-blocking risk, capacity, borrow, data-integrity, and operating-control failures while preserving the useful V3 regime behavior, especially high-volatility regime Sharpe of 1.62 and 2022 rate-shock Sharpe of 1.14.

## 2. Requirement To Design Mapping
| req_id | design module | primary function or artifact | design role |
| --- | --- | --- | --- |
| REQ-F-001 | `src/portfolio/v4/optimization.py` | `solve_turnover_aware_weights` | Turnover-aware neutralization with turnover penalty and no-trade band. |
| REQ-F-002 | `src/portfolio/v4/optimization.py` | `build_sector_net_constraints` | Sector-net constraints inside the optimizer. |
| REQ-F-003 | `src/portfolio/v4/regime.py` | `compute_trend_sizing_multiplier` | SPY 60d trailing-return percentile and trend-down sizing. |
| REQ-F-004 | `src/portfolio/v4/beta_monitoring.py` | `compute_realized_beta_monitor_20d` | Fast residual-beta monitor. |
| REQ-F-005 | `src/portfolio/v4/beta_monitoring.py` | `compute_realized_beta_monitor_60d` | Persistent residual-beta monitor. |
| REQ-F-006 | `src/portfolio/v4/borrow.py` | `enforce_short_concentration_limits` | Short top-10 and single-name concentration limits. |
| REQ-F-007 | `src/portfolio/v4/borrow.py` | `apply_pb_borrow_caps` | PB locate/utilization HTB cap and borrow-data block. |
| REQ-F-008 | `src/portfolio/v4/drawdown.py` | `evaluate_drawdown_halts` | Soft, hard, single-day, and terminal drawdown tiers. |
| REQ-F-009 | `src/portfolio/v4/capacity.py` | `check_order_participation` | Pre-trade 5% ADV participation cap. |
| REQ-F-010 | `src/portfolio/v4/risk_budget.py` | `compute_var_es_budget` | Rolling historical VaR and expected shortfall budget. |
| REQ-F-011 | `src/portfolio/v4/slippage.py` | `attribute_slippage_vs_model` | Realized slippage and square-root impact attribution. |
| REQ-F-012 | `src/portfolio/v4/data_integrity.py` | `validate_adv20_freshness` | Daily ADV20 freshness gate. |
| REQ-F-013 | `src/portfolio/v4/data_integrity.py` | `run_pit_pre_signal_audit` | PIT audit before signal generation. |
| REQ-F-014 | `src/portfolio/v4/builder.py` | `build_v4_weights` | Single canonical builder for V4 production and reconstruction. |
| REQ-F-015 | `src/portfolio/v4/data_integrity.py` | `enforce_pit_launch_gate` | Launch block on PIT audit failure. |
| REQ-N-001 | `scripts/run_v4_pipeline.py` | CLI command contract | One documented reproducibility command. |
| REQ-N-002 | `tests/test_v4_*.py` | Requirement-mapped tests | One automated test path per REQ-F. |
| REQ-N-003 | `scripts/run_v4_reports.py` | Report-generation contract | V4 attribution, capacity, stress, and checklist reports. |
| REQ-N-004 | `src/portfolio/v4/reconciliation.py` | `reconcile_cache_to_builder` | Cache/reconstruction agreement by construction. |

The paths above are proposed implementation targets only. This design document does not create them.

## 3. REQ-F-001: Turnover-Aware Neutralization
**ADR-0003 supersedes the original scalar turnover-penalty design.** The original hybrid of one scalar turnover penalty plus one no-trade band passed unit-level D2 tests but failed the E1/ADR-0002 full-sample decision point: turnover reduction can be made to pass, but not simultaneously with high-volatility and 2022 rate-shock Sharpe preservation. ADR-0003 keeps all acceptance thresholds unchanged and revises the optimizer form toward regime-preserving turnover control.

Design pattern: hybrid turnover penalty plus no-trade band.

The no-trade band suppresses immaterial name-level churn. The turnover penalty handles larger optimization choices where several feasible portfolios meet the same risk objectives. This hybrid is preferred because Stage 5.4 identified a tail-turnover problem, not a simple mean-turnover problem.

Draft interface:

```python
def solve_turnover_aware_weights(
    raw_weights: pd.Series,
    prior_weights: pd.Series,
    betas: pd.Series,
    sectors: pd.Series,
    *,
    sector_net_cap: float,
    gross_target: float,
    turnover_penalty: float,
    no_trade_band_bps: float,
    short_top10_cap: float,
    single_short_cap: float,
) -> pd.Series:
    """Return one date of V4 weights after turnover-aware risk constraints."""
```

Objective, by date:

```text
minimize
    alpha_tracking_error(x, raw_weights)
  + lambda_turnover * sum(abs(x - prior_weights))
  + lambda_beta * beta_residual_penalty(x, betas)

subject to
    long_sum(x) = 1
    short_abs_sum(x) = 1
    sector_net_constraints(x, sectors)
    borrow_and_concentration_constraints(x)
    no_trade_band keeps prior weight when abs(raw - prior) is below threshold and constraints remain feasible
```

Acceptance focus:
- Reduce days with daily gross turnover >100% by at least 75%.
- Keep p95 non-rebalance-day turnover below 1.5x p95 rebalance-day turnover.
- Preserve full-sample Sharpe at least 0.9x V3 baseline.
- Preserve 2022 rate-shock Sharpe >=1.0 and avoid sector-net widening versus V3.

ADR-0003 revised design focus:
- Preserve the no-trade band for immaterial name-level churn.
- Replace scalar-only turnover suppression with regime-preserving turnover control.
- Treat high-volatility and 2022-style rate-shock windows as protected validation slices during optimizer design, not as post-hoc reporting only.
- Do not relax the locked E1 thresholds; a D-hotfix must prove the revised optimizer form with a full E1 rerun before REQ-F-001 can merge.

## 4. REQ-F-002: Sector-Net Inside Optimizer
Solver choice: cvxpy-style convex quadratic program for the primary design. The dependency decision is deferred to implementation approval, but the mathematical contract should remain a convex QP so an implementation can be reviewed independently of solver plumbing.

Constraint structure for one date:

```text
x                 vector of signed weights, length n
A_long x = 1      sum positive-side exposure to 1 through split variables
A_short x = 1     sum short-side absolute exposure to 1 through split variables
B x = beta_net    beta exposure from stock beta vector
S x               sector net exposure vector using one-hot sector matrix
```

Required sector constraints:

```text
abs(S x) <= sector_net_cap_by_sector
p95 max(abs(S x)) <= 15% in backtest acceptance
average max(abs(S x)) <= raw baseline
```

The optimizer must not satisfy beta neutrality by pushing risk into sector tilts. Sector net exposure is therefore a hard constraint, not a post-solve diagnostic.

## 5. REQ-F-003, REQ-F-004, REQ-F-005: Regime And Beta Monitoring
Market proxy:
- Use the locked Pillar 5 market proxy convention for historical comparability.
- SPY is the named regime proxy for the 60d trend signal when SPY data is present in the canonical price tape.
- If SPY is not in the repository price universe for a historical run, use the existing out-of-portfolio market proxy and label the report accordingly.

Trend sizing:
- Compute SPY 60d trailing return daily.
- Compute percentile versus the trailing 3-year distribution using only information available as of that date.
- Bottom quartile is the trend-down regime.
- Sizing reduction is triggered by trend-down state, not high volatility.

Draft interface:

```python
def compute_trend_sizing_multiplier(
    spy_returns: pd.Series,
    *,
    trailing_return_window: int = 60,
    percentile_window: int = 756,
    bottom_quartile_multiplier: float,
) -> pd.Series:
    """Return daily V4 sizing multipliers from SPY trend percentile."""
```

Residual beta monitors:
- 20d realized beta: refreshed daily, warning at `abs(beta_20d) > 0.30`, hard review at `abs(beta_20d) > 0.50` for 3 consecutive days.
- 60d realized beta: refreshed daily, warning at `abs(beta_60d) > 0.25`, hard review at `abs(beta_60d) > 0.40` for 5 consecutive days.
- Both monitors use realized V4 daily returns versus the locked market proxy.
- 20d monitoring is mandatory because 60d-only monitoring missed fast-event beta drift in Stage 5.6.

## 6. REQ-F-006 And REQ-F-007: Short Concentration And Borrow
Short concentration:
- Launch threshold: top-10 short concentration <=25% of short book.
- Stretch goal: <=20%.
- Single-name short threshold: no single short >5% of short book without approval.

Prime broker borrow feed schema:

| field | type | required | purpose |
| --- | --- | --- | --- |
| `date` | date | yes | As-of date for locate and utilization. |
| `symbol` | string | yes | Security identifier aligned to V4 weights. |
| `locate_available_shares` | float | yes | Shares available to short. |
| `borrow_rate_bps` | float | yes | Annualized borrow cost estimate. |
| `utilization_pct` | float | yes | Borrow utilization. |
| `htb_flag` | bool | yes | Hard-to-borrow classification. |
| `feed_timestamp_utc` | timestamp | yes | Freshness and PIT audit field. |

HTB threshold:
- HTB notional must be <25% of short book.
- Missing PB borrow data blocks order generation for affected short names.
- ADV or market cap remains useful for liquidity, but cannot stand in for borrow availability once the PB feed is required.

## 7. REQ-F-008: Multi-Tier Drawdown Halt
| tier | trigger | action | sizing factor |
| --- | --- | --- | --- |
| Soft halt | rolling 60d drawdown <= -10% | Require documented risk review before ordinary rebalance. | 0.50 pending approval |
| Hard halt | rolling 60d drawdown <= -15% | Block new risk; allow risk-reducing trades only. | 0.00 for risk adds |
| Single-day halt | one-day loss <= -8% | Same-day incident review and next-day order block until cleared. | 0.00 until review |
| Terminal kill switch | portfolio drawdown <= -20% | Strategy disabled for live consideration pending owner decision. | 0.00 |

The -20% kill switch is retained, but it must not be the first review trigger.

## 8. REQ-F-009 And REQ-F-010: Participation, VaR, And ES
Participation cap:
- No planned order may exceed 5% ADV20 without explicit approval.
- Capacity reporting must include p50, p95, and max participation.
- Capacity calculations must multiply by gross exposure, not just AUM.

Draft interface:

```python
def check_order_participation(
    target_weights: pd.Series,
    current_weights: pd.Series,
    adv20_usd: pd.Series,
    *,
    aum_usd: float,
    gross: float,
    max_participation: float = 0.05,
) -> pd.DataFrame:
    """Return name-level order notional, ADV20, participation, and pass/fail."""
```

VaR and ES:
- Use rolling historical daily net returns.
- Primary window: 252 trading days.
- Confidence levels: 95% and 99%.
- Refresh cadence: daily after return finalization.
- Breach report must reconcile VaR/ES to realized P&L and must not replace drawdown halts or residual-beta monitoring.

## 9. REQ-F-011, REQ-F-012, REQ-F-013, REQ-F-015: Execution And Data Integrity
PIT audit schema:

| field | type | gate |
| --- | --- | --- |
| `date` | date | Required. |
| `dataset` | string | Required. |
| `max_asof_timestamp_utc` | timestamp | Must be <= decision timestamp. |
| `missing_symbol_count` | int | Must be 0 for required fields. |
| `future_timestamp_count` | int | Must be 0. |
| `stale_field_count` | int | Must be 0 for order-blocking fields. |
| `corporate_action_audit_pass` | bool | Must be true. |
| `audit_status` | enum | Must be `PASS` before signal generation. |

ADV20 freshness:
- ADV20 must be recomputed or validated daily.
- Stale means missing current as-of metadata, older than one trading day, or built from fewer than 20 valid historical observations unless an event-day override is documented.
- Missing or stale ADV20 blocks order generation for affected names.

Slippage attribution formula:

```text
order_notional_i = abs(target_weight_i - current_weight_i) * AUM * gross
participation_i = order_notional_i / ADV20_i
modeled_impact_bps_i = impact_coefficient * daily_vol_i * sqrt(participation_i) * 10000
slippage_residual_bps_i = realized_slippage_bps_i - modeled_impact_bps_i
```

Daily output must attribute slippage by name, order, sector, and rotation-day tag. Tail rotation-day impact must be reported separately.

Launch gate:
- `run_pit_pre_signal_audit` must pass before signal generation.
- `enforce_pit_launch_gate` must block order files and open an incident record when required data checks fail.

## 10. REQ-N-001: Reproducibility Command
Draft command:

```powershell
python scripts\run_v4_pipeline.py --config config\v4.yaml --asof 2026-05-30 --output results\v4_artifacts
```

Command contract:
- One command builds V4 weights, diagnostics, and run hashes.
- Inputs, config hash, output hash, code version marker, and run timestamp are written to a manifest.
- No hidden notebook state or mutable intermediate file may be required.

## 11. REQ-N-002: Planned Test Coverage
| req_id | planned test path | main assertion |
| --- | --- | --- |
| REQ-F-001 | `tests/test_v4_turnover_aware_neutralization.py` | Tail turnover reduction and non-rebalance turnover ratio pass. |
| REQ-F-002 | `tests/test_v4_sector_net_constraints.py` | Sector net constraints hold inside solver output. |
| REQ-F-003 | `tests/test_v4_regime_sizing.py` | Trend-down sizing triggers on bottom-quartile SPY 60d return, not high vol alone. |
| REQ-F-004 | `tests/test_v4_beta_monitoring.py` | 20d warning and hard-review thresholds trigger correctly. |
| REQ-F-005 | `tests/test_v4_beta_monitoring.py` | 60d warning and hard-review thresholds trigger correctly. |
| REQ-F-006 | `tests/test_v4_borrow_concentration.py` | Top-10 and single-name short limits pass/fail as specified. |
| REQ-F-007 | `tests/test_v4_borrow_concentration.py` | Missing PB borrow data and HTB cap block affected shorts. |
| REQ-F-008 | `tests/test_v4_drawdown_halts.py` | Soft, hard, single-day, and terminal halt tiers map to correct actions. |
| REQ-F-009 | `tests/test_v4_participation_capacity.py` | 5% ADV cap uses order notional and gross exposure. |
| REQ-F-010 | `tests/test_v4_var_es_budget.py` | 95%/99% VaR and ES are produced and breaches are flagged. |
| REQ-F-011 | `tests/test_v4_slippage_monitoring.py` | Impact is applied to traded notional and tail rotation days are tagged. |
| REQ-F-012 | `tests/test_v4_data_integrity.py` | Stale or missing ADV20 blocks order generation. |
| REQ-F-013 | `tests/test_v4_data_integrity.py` | PIT audit blocks future-adjusted or missing required fields. |
| REQ-F-014 | `tests/test_v4_reconciliation.py` | Builder output and cache output reconcile bit-for-bit or within documented tolerance. |
| REQ-F-015 | `tests/test_v4_data_integrity.py` | Failed PIT audit blocks launch/order artifacts. |

These files are not created by this workflow.

## 12. REQ-N-003: Documentation Parity
| V4 report | Pillar 5 analog | required content |
| --- | --- | --- |
| `reports/v4_capacity_summary.md` | Stage 5.4 | Capacity ceiling, p50/p95/max participation, short concentration, borrow limits. |
| `reports/v4_risk_decomposition.md` | Stage 5.5 | Market, sector, and residual decomposition; factor-tape limitation if unresolved. |
| `reports/v4_stress_regime.md` | Stage 5.6 | Stress windows, high-vol regime, trend-down regime, 2022 rate-shock guard. |
| `reports/v4_live_readiness_checklist.md` | Stage 5.7 | End-to-end P0 launch checklist, pass/partial/fail status, mitigations. |
| `reports/v4_acceptance_gate.md` | Stage 5.8 | V4 supersession decision against all acceptance gates. |

V4 readiness may not be claimed from Sharpe-only backtests.

## 13. REQ-N-004: Source-Of-Truth Discipline
V4 must have one shared builder function used by both production cache generation and reconstruction:

```python
def build_v4_weights(
    inputs: V4InputBundle,
    config: V4Config,
) -> V4BuildResult:
    """Return weights, diagnostics, run manifest, and validation status."""
```

Design rules:
- Cache generation calls `build_v4_weights`.
- Reconstruction calls the same `build_v4_weights`.
- No second script may independently reimplement the optimization sequence.
- The run manifest records input hashes, config hash, builder version marker, and output weight hash.
- `reconcile_cache_to_builder` runs automatically after cache write and fails the pipeline on mismatch.

This is the by-construction guard against repeating the Stage 5.5 cache-vs-reconstruction ambiguity.

## 14. Out Of Scope
- No V4 implementation code is authorized by this document.
- No new V4 module, script, test file, or config file is created by this workflow.
- No new alpha signals are introduced; V4 inherits the Pillar 4 alpha.
- No intraday execution design is included; V4 remains daily cadence.
- No live trading infrastructure is included.
- No multi-asset or non-equity extension is included.
- No replacement of the factor-tape limitation is included beyond documenting the inherited limitation in V4 attribution.

## 15. Implementation Status Tracker
Status values are limited to `NOT-STARTED`, `IN-PROGRESS`, and `MERGED`. Each implementation PR must update this table before merge.

**Status semantics in design phase.** `IN-PROGRESS` here means the test scaffolding and module namespace are reserved and the meta-coverage test (`test_v4_requirement_coverage.py`) passes. It does not mean the underlying REQ-F business logic is implemented. Transition to `MERGED` requires the implementation workflow to land the production code, pass its assertion-level test, and remove any `pytest.skip` shielding REQ-F coverage.

**REQ-F acceptance gates pending.** "Workflow Dx implemented" in PR-ref means the unit-level optimizer/borrow/regime/risk logic is in place and unit-tested. Full-sample acceptance gates (e.g. REQ-F-001 tail-turnover >=75% reduction, p95 non-rebalance / rebalance ratio, full-sample Sharpe >=0.9x V3, 2022 rate-shock Sharpe >=1.0) remain pending the V4 full-sample replay artifact and acceptance-gate workflow (planned D7 / E1). No REQ-F may transition to MERGED until its design-section acceptance gate is evidenced by a results artifact.

| REQ-ID | status | PR-ref | test-ref |
| --- | --- | --- | --- |
| REQ-F-001 | MERGED | Workflow D2 implemented + Workflow E1 evaluated FAIL + ADR-0002 ESCALATE-B + ADR-0003 D-hotfix E1 rerun PASS | `tests/test_v4_turnover_aware_neutralization.py` |
| REQ-F-002 | MERGED | Workflow D2 implemented + Workflow E1 evaluated | `tests/test_v4_sector_net_constraints.py` |
| REQ-F-003 | MERGED | Workflow D4 implemented + Workflow E1 evaluated | `tests/test_v4_regime_sizing.py` |
| REQ-F-004 | MERGED | Workflow D4 implemented + Workflow E1 evaluated | `tests/test_v4_beta_monitoring.py` |
| REQ-F-005 | MERGED | Workflow D4 implemented + Workflow E1 evaluated | `tests/test_v4_beta_monitoring.py` |
| REQ-F-006 | MERGED | Workflow D3 implemented + Workflow E1 evaluated | `tests/test_v4_borrow_concentration.py` |
| REQ-F-007 | MERGED | Workflow D3 implemented + Workflow E1 evaluated | `tests/test_v4_borrow_concentration.py` |
| REQ-F-008 | MERGED | Workflow D5 implemented + Workflow E1 evaluated | `tests/test_v4_drawdown_halts.py` |
| REQ-F-009 | MERGED | Workflow D5 implemented + Workflow E1 evaluated | `tests/test_v4_participation_capacity.py` |
| REQ-F-010 | MERGED | Workflow D5 implemented + Workflow E1 evaluated | `tests/test_v4_var_es_budget.py` |
| REQ-F-011 | MERGED | Workflow D6 implemented + Workflow E1 evaluated | `tests/test_v4_slippage_monitoring.py` |
| REQ-F-012 | MERGED | Workflow D6 implemented + Workflow E1 evaluated | `tests/test_v4_data_integrity.py` |
| REQ-F-013 | MERGED | Workflow D6 implemented + Workflow E1 evaluated | `tests/test_v4_data_integrity.py` |
| REQ-F-014 | MERGED | Workflow D7 implemented + Workflow E1 evaluated | `tests/test_v4_reconciliation.py` |
| REQ-F-015 | MERGED | Workflow D6 implemented + Workflow E1 evaluated | `tests/test_v4_data_integrity.py` |
| REQ-N-001 | MERGED | Workflow D7 partial + Workflow E1 evaluated + E2 prod loader scaffold | `tests/test_v4_reproducibility.py` |
| REQ-N-002 | MERGED | Workflow C10 + E2 coverage closure | `tests/test_v4_requirement_coverage.py` |
| REQ-N-003 | MERGED | Workflow C9 + Workflow E1 evaluated | `tests/test_v4_report_generation.py` |
| REQ-N-004 | MERGED | Workflow D7 implemented + Workflow E1 evaluated | `tests/test_v4_reconciliation.py` |

REQ-F-002 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-002-sector-p95 PASS, G-REQ-F-002-sector-avg PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-003 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-003-trend-regime PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-004 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-004-beta20-warning PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-005 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-005-beta60-warning PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-006 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-006-short-top10 PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-007 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-007-htb-block PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-008 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-008-halt-tiers PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-009 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-009-participation PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-010 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-010-var-es PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-011 MERGED 2026-05-31 via Workflow E1, gates: G-REQ-F-011-slippage-tail PASS; evidence: results/v4_e1_acceptance_gates.json
REQ-F-012 MERGED 2026-05-31 via Workflow E1, gates: ADV20/PIT replay integrity PASS; evidence: results/v4_e1_replay/v4_pit_audit_log.parquet
REQ-F-013 MERGED 2026-05-31 via Workflow E1, gates: PIT replay integrity PASS; evidence: results/v4_e1_replay/v4_pit_audit_log.parquet
REQ-F-014 MERGED 2026-05-31 via Workflow E1, gates: source-of-truth replay artifacts generated PASS; evidence: results/v4_e1_replay/v4_replay_manifest.json
REQ-F-015 MERGED 2026-05-31 via Workflow E1, gates: PIT launch replay gate evaluated PASS; evidence: results/v4_e1_replay/v4_pit_audit_log.parquet
ADR-0002 initial grid completed 2026-05-31 with decision=ESCALATE-B but exposed dead replay-path calibration wiring; evidence: results/adr0002_grid/adr0002_manifest.json
ADR-0002 A-prime wiring repair rerun completed 2026-05-31 with sanity_probe=PARAMETER_SENSITIVE and decision=ESCALATE-B; evidence: results/adr0002_grid/adr0002_manifest.json; next: ADR-0003 design revision
ADR-0003 design revision accepted 2026-05-31; REQ-F-001 remains IN-PROGRESS pending D-hotfix implementation and full E1 rerun evidence; evidence: docs/extended/adr/ADR-0003-v4-turnover-design-revision.md
REQ-F-001 MERGED 2026-05-31 via ADR-0003 D-hotfix E1 rerun, gates: G-REQ-F-001-tail-turnover PASS (observed 1.000000), G-REQ-F-001-fullsample-sharpe PASS (observed 1.053387), G-REQ-F-001-2022-shock PASS (observed 1.140416), G-Preserve-HighVol-Sharpe PASS (observed 1.465894), G-Preserve-2022-Sharpe PASS (observed 1.140416); evidence: results/v4_e1_acceptance_gates.json
The ADR-0003 pending line above is superseded by the subsequent REQ-F-001 MERGED evidence line.
REQ-N-001 MERGED 2026-05-31 via E2 prod loader scaffold, gates: CLI accepts --inputs-prod, reads canonical V3 cache inputs, writes cache, and auto-reconciles; evidence: tests/test_v4_cli_smoke.py
REQ-N-002 MERGED 2026-05-31 via E2 coverage closure, gates: every REQ-F has a test file, every mapped test references its REQ id, status tracker consistency passes, module namespace import checks pass; evidence: tests/test_v4_requirement_coverage.py
