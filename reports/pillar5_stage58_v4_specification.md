# Pillar 5 Stage 5.8 - V4 Specification

## Section 0 - Launch Posture
V4 implementation BLOCKED pending V3 reconciliation resolution; see Section 2.
Part A verdict: C - BLOCKING DIFF; mean L1=0.1775, p95 return diff=22.27 bps, max return diff=137.65 bps.

## Section 1 - V3 Recap & V4 Mandate
V3 production sizing is 10% target vol with 1.405x gross, Sharpe about 0.498 at 10 bps, max drawdown -17.3%, and no tested Stage 5.6 stress window breached the -20% kill switch. It is still **NO-GO for live capital** because Stage 5.4 capacity is <$5M, driven by tail rotation days and short-book concentration, and Stage 5.7 has 16 launch-blocking checklist items.

V4 is **not** a Sharpe-maximization project. V4 must resolve launch-blocking live-readiness items while preserving V3's useful regime behavior, especially high-volatility regime Sharpe of 1.62 and 2022 rate-shock window Sharpe of 1.14. The design goal is institutional viability: capacity, turnover, borrow, data integrity, and risk controls must improve without silently removing the exposures that made V3 resilient in some stress regimes.

## Section 2 - Pre-V4 Prerequisites
### V3 Canonical Reconciliation
- Verdict: **C - BLOCKING DIFF**.
- Canonical path: `unresolved; temporary analysis source remains results/pillar5_artifacts/v3_weights.parquet`.
- Deprecation notice: No path may be deprecated until reconstruction/cache mismatch is resolved.
- Reconciliation summary:
| common_dates | common_symbols | recon_only_dates | cache_only_dates | recon_only_symbols | cache_only_symbols | mean_weight_l1 | p50_weight_l1 | p95_weight_l1 | max_weight_l1 | mean_gross_diff | max_gross_diff | mean_return_diff_bps | p50_return_diff_bps | p95_return_diff_bps | max_return_diff_bps | mean_beta_diff | max_beta_diff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2768.0 | 516.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1775 | 0.1205 | 0.5484 | 0.8974 | 0.0 | 0.0 | 5.1698 | 1.8388 | 22.2694 | 137.6476 | 0.002 | 0.0537 |

Factor-tape decision: no canonical size/value/momentum factor-return tape exists in the repository. V4 attribution may proceed with market + sector + residual decomposition if no factor tape is sourced, but it inherits the limitation that residual alpha cannot be proven free of hidden factor exposure.

## Section 3 - V4 Functional Requirements (REQ-F-xxx)
### REQ-F-001: Turnover-aware neutralization
Source: PT-003, 5.4, 5.5, 5.6, 5.7
Requirement: V4 neutralization must include turnover-aware behavior, such as a no-trade band or turnover penalty, while preserving the daily risk-control objective.
Acceptance criteria:
- n_days with daily gross turnover > 100% reduced by >=75%
- p95 non-rebalance-day turnover < 1.5x p95 rebalance-day turnover
- full-sample Sharpe >= 0.9x V3 baseline.
Anti-criteria:
- Must not reduce 2022 rate-shock Sharpe below 1.0
- must not widen post-solve sector net exposure above V3
- must not claim capacity improvement without rerunning 5.4-style capacity.
Priority: P0
Depends on: REQ-F-002, REQ-F-004, REQ-N-004

### REQ-F-002: Sector-net constraint inside optimizer
Source: PT-005, 5.5, 5.7
Requirement: V4 optimizer must constrain sector net exposure inside the beta-neutral solve rather than relying only on side caps.
Acceptance criteria:
- Post-solve average max abs sector net <= raw baseline
- p95 max abs sector net <=15%
- sector exposure covariance share is not negative by more than V3 baseline.
Anti-criteria:
- Must not use sector tilts to satisfy beta neutrality
- must not lower high-vol regime Sharpe below 0.9x V3 high-vol Sharpe.
Priority: P0
Depends on: REQ-F-001

### REQ-F-003: Trend-based regime sizing
Source: RM-003, 5.6, 5.7
Requirement: V4 must compute SPY 60d trailing-return percentile versus trailing 3y distribution and use trend-down state for sizing decisions.
Acceptance criteria:
- Bottom-quartile SPY-60d-return regime Sharpe >=0
- max DD in that regime improves vs V3
- high-vol top-quartile Sharpe >=0.9x V3 high-vol Sharpe.
Anti-criteria:
- Must not implement a blunt vol-off filter
- must not cut risk simply because SPY 20d volatility is high.
Priority: P0
Depends on: none

### REQ-F-004: Residual beta 20d monitoring
Source: RM-002, 5.6, 5.7
Requirement: V4 must monitor rolling 20d realized beta daily to catch fast dislocations missed by 60d beta.
Acceptance criteria:
- Warn at |beta_20d| >0.30
- hard review at |beta_20d| >0.50 for 3 consecutive days
- COVID-like fast windows are visible in monitoring output.
Anti-criteria:
- Must not rely on 60d beta alone
- must not label COVID-style windows effective solely because 60d beta stays below threshold.
Priority: P0
Depends on: REQ-F-005

### REQ-F-005: Residual beta 60d monitoring
Source: RM-001, 5.5, 5.6, 5.7
Requirement: V4 must monitor rolling 60d realized beta daily for persistent drift.
Acceptance criteria:
- Warn at |beta_60d| >0.25
- hard review at |beta_60d| >0.40 for 5 consecutive days
- 2022 rate-shock drift is flagged historically.
Anti-criteria:
- Must not force zero realized beta at the cost of collapsing 2022 rate-shock Sharpe below 1.0.
Priority: P0
Depends on: REQ-F-004

### REQ-F-006: Short top-10 concentration limit
Source: BF-001, 5.4, 5.7
Requirement: V4 must limit concentration in the short book.
Acceptance criteria:
- Top-10 short concentration <=25% at launch
- stretch goal <=20%
- no single short >5% of short book without approval.
Anti-criteria:
- Must not improve concentration by replacing easy-borrow names with HTB names
- must not reduce short diversification during stress windows.
Priority: P0
Depends on: REQ-F-007

### REQ-F-007: HTB cap with PB feed
Source: BF-002, 5.4, 5.7
Requirement: V4 must replace market-cap/ADV borrow proxy with PB locate/utilization data and enforce HTB cap.
Acceptance criteria:
- HTB notional <25% of short book using PB feed
- unavailable borrow data blocks order generation for affected names.
Anti-criteria:
- Must not treat ADV or market cap as sufficient proof of borrow availability after PB feed exists.
Priority: P0
Depends on: none

### REQ-F-008: Multi-tier drawdown halt
Source: OP-001;OP-002;OP-003, 5.2, 5.6, 5.7
Requirement: V4 live-readiness policy must implement multi-tier drawdown controls.
Acceptance criteria:
- -10% rolling 60d DD soft halt
- -15% rolling 60d DD hard halt
- -8% single-day loss halt
- -20% terminal kill switch retained.
Anti-criteria:
- Must not rely on -20% as the first review trigger
- must not continue ordinary rebalancing after a soft/hard halt without documented review.
Priority: P0
Depends on: none

### REQ-F-009: Participation cap
Source: PT-004, 5.4, 5.7
Requirement: V4 pre-trade checks must cap projected participation by name/day.
Acceptance criteria:
- No order plan exceeds 5% ADV without explicit approval
- report p50/p95/max participation as in 5.4.
Anti-criteria:
- Must not report capacity using mean participation only
- must not scale AUM without multiplying by gross exposure.
Priority: P0
Depends on: REQ-F-012, REQ-F-013

### REQ-F-010: VaR / expected shortfall budget
Source: RM-006, 5.7
Requirement: V4 must add rolling historical VaR and expected shortfall limits.
Acceptance criteria:
- Daily 95/99% VaR and ES produced
- breach escalation is documented
- VaR/ES report reconciles to realized P&L.
Anti-criteria:
- Must not use VaR/ES as a substitute for drawdown halts or residual beta monitoring.
Priority: P0
Depends on: REQ-F-008

### REQ-F-011: Slippage and impact monitoring
Source: OP-005, 5.4, 5.7
Requirement: V4 must compare realized execution cost to modeled square-root impact daily.
Acceptance criteria:
- Daily slippage report by name, order, sector, and rotation-day tag
- tail rotation-day impact separately reported.
Anti-criteria:
- Must not apply impact to gross exposure instead of turnover
- must not ignore high-turnover non-rebalance days.
Priority: P0
Depends on: REQ-F-001

### REQ-F-012: ADV20 freshness
Source: DI-003, 5.4, 5.7
Requirement: V4 must refresh ADV20 daily and block stale liquidity estimates.
Acceptance criteria:
- No order generated if ADV20 is missing/stale
- event-day liquidity override is documented.
Anti-criteria:
- Must not rely on stationary ADV around earnings or index events.
Priority: P0
Depends on: none

### REQ-F-013: Point-in-time validation
Source: DI-001, 5.7, 5.8
Requirement: V4 must run point-in-time checks before signal generation.
Acceptance criteria:
- Daily data audit passes for prices, returns, and corporate actions before weights are generated.
Anti-criteria:
- Must not allow cache/reconstruction mismatches to pass silently
- must not use future-adjusted fields in signal construction.
Priority: P0
Depends on: REQ-N-001, REQ-N-004

### REQ-F-014: Canonical source-of-truth reconciliation
Source: OP-006, 5.5, 5.7, 5.8
Requirement: V4 must define exactly one canonical production book path before implementation.
Acceptance criteria:
- One documented command regenerates the canonical V4 weights bit-for-bit
- cache and reconstruction agree by construction.
Anti-criteria:
- Must not repeat the Stage 5.5 cache-vs-reconstruction ambiguity
- must not start V4 if Stage 5.8 reconciliation is Verdict C without explicit resolution.
Priority: P0
Depends on: REQ-N-001, REQ-N-004

### REQ-F-015: PIT data integrity launch gate
Source: DI-001, 5.7
Requirement: V4 launch workflow must block if daily PIT data checks fail.
Acceptance criteria:
- Daily data audit passes before signal generation
- failed audit blocks order files and opens an incident ticket.
Anti-criteria:
- Must not treat manual spot checks as sufficient for live launch.
Priority: P0
Depends on: REQ-F-013

## Section 4 - V4 Non-Functional Requirements (REQ-N-xxx)
### REQ-N-001: Reproducibility
Source: OP-006, 5.5, 5.7
Requirement: One documented command regenerates V4 weights bit-for-bit.
Acceptance criteria:
- Command, inputs, and output hashes are documented for every V4 run.
Anti-criteria:
- Must not depend on hidden notebooks or mutable intermediate files.
Priority: P0
Depends on: none

### REQ-N-002: Testability
Source: ALL_BLOCKING, 5.7
Requirement: Each REQ-F must have at least one automated test in tests/.
Acceptance criteria:
- Automated test coverage maps every REQ-F id to at least one test or explicit non-automatable exception.
Anti-criteria:
- Must not accept manual-only verification for launch-blocking controls.
Priority: P0
Depends on: none

### REQ-N-003: Documentation parity
Source: ALL_BLOCKING, 5.4, 5.5, 5.6, 5.7
Requirement: V4 must produce attribution, capacity, and stress reports analogous to Pillar 5 Stages 5.4-5.6.
Acceptance criteria:
- V4 report set includes capacity, risk decomposition, stress/regime, and live-readiness checklist.
Anti-criteria:
- Must not claim V4 readiness from Sharpe-only backtests.
Priority: P0
Depends on: REQ-N-002

### REQ-N-004: Source-of-truth discipline
Source: OP-006, 5.5, 5.8
Requirement: V4 weights cache and reconstruction script must agree by construction.
Acceptance criteria:
- Daily reconciliation has mean weight L1 <0.01, p95 return diff <1bp, max return diff <5bp.
Anti-criteria:
- Must not allow an unresolved Verdict C-style mismatch into V4 implementation.
Priority: P0
Depends on: REQ-N-001

## Section 5 - V4 Acceptance Gate
- All P0 REQ-F meet acceptance criteria.
- No REQ-F violates any anti-criterion.
- V4 full-sample Sharpe >= 0.9 x V3 baseline.
- V4 capacity ceiling >= $25M under the same live-readiness rules used in Stage 5.4.
- Stage 5.7 checklist is re-evaluated end-to-end: all launch-blocking items pass or are partial with explicit mitigation.
- 2022 rate-shock window Sharpe >= 1.0.
- High-vol regime (SPY 20d vol top quartile) Sharpe >= 0.9 x V3 baseline of 1.62.

## Section 6 - Out of Scope for V4
- New alpha signals; V4 inherits Pillar 4 alpha unchanged.
- Intraday execution; V4 keeps daily rebalance cadence.
- Live trading infrastructure; this remains a separate ops workstream.
- Multi-asset or non-equity extension.
- Replacing the existing factor-tape limitation; Section 2 documents the limitation.

## Section 7 - Open Risks & Known Limitations
- 5.5 OQ#1: no canonical size/value/momentum factor tape; residual alpha cannot be proven free of hidden factor exposure.
- 5.5 OQ#2 / 5.8 Part A: C - BLOCKING DIFF. No path may be deprecated until reconstruction/cache mismatch is resolved.
- 5.6 measurement limitation: 60d-only beta monitoring is blind to fast events; mitigated by REQ-F-004.
- 5.6 paradox: removing residual beta drift may remove P&L-positive exposure in rate-shock regimes; mitigated by REQ-F-001, REQ-F-005, and the Section 5 acceptance gate.
- 5.4 capacity: V4 must re-run the full Stage 5.4 capacity study; V3's <$5M capacity number is a V3-specific artifact, not a forward-looking V4 estimate.
