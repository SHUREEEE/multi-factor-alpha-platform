# Pillar 5 V4 Unblock Gate

## Formal Verdict
**GO**
ADR-0001 has been executed and post-ADR reconciliation passed. REQ-F-014 and REQ-N-004 are now SATISFIED-POST-ADR, so provisional labeling is no longer required for V4 kickoff.

## Evidence Summary
- H3 derivative share: 100.0%.
- Sharpe diff: 0.007.
- Return correlation: 0.993.
- V3 NO-GO invariant: True.
- Post-ADR mean weight L1: 0.00e+00.
- Post-ADR max return diff: 0.0000 bps.

## Requirement Classification
| req_id | requirement_text | classification | justification | blocks_v4_start_Y_N |
| --- | --- | --- | --- | --- |
| REQ-F-001 | Turnover-aware neutralization: V4 neutralization must include turnover-aware behavior, such as a no-trade band or turnover penalty, while preserving the daily risk-control objective. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-F-002 | Sector-net constraint inside optimizer: V4 optimizer must constrain sector net exposure inside the beta-neutral solve rather than relying only on side caps. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-F-003 | Trend-based regime sizing: V4 must compute SPY 60d trailing-return percentile versus trailing 3y distribution and use trend-down state for sizing decisions. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-004 | Residual beta 20d monitoring: V4 must monitor rolling 20d realized beta daily to catch fast dislocations missed by 60d beta. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-F-005 | Residual beta 60d monitoring: V4 must monitor rolling 60d realized beta daily for persistent drift. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-F-006 | Short top-10 concentration limit: V4 must limit concentration in the short book. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-007 | HTB cap with PB feed: V4 must replace market-cap/ADV borrow proxy with PB locate/utilization data and enforce HTB cap. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-008 | Multi-tier drawdown halt: V4 live-readiness policy must implement multi-tier drawdown controls. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-009 | Participation cap: V4 pre-trade checks must cap projected participation by name/day. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-010 | VaR / expected shortfall budget: V4 must add rolling historical VaR and expected shortfall limits. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-011 | Slippage and impact monitoring: V4 must compare realized execution cost to modeled square-root impact daily. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-F-012 | ADV20 freshness: V4 must refresh ADV20 daily and block stale liquidity estimates. | SATISFIED-AS-IS | Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings. | N |
| REQ-F-013 | Point-in-time validation: V4 must run point-in-time checks before signal generation. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-F-014 | Canonical source-of-truth reconciliation: V4 must define exactly one canonical production book path before implementation. | BLOCKING-UNTIL-REMEDIATED | This requirement directly requires cache/reconstruction agreement by construction; ADR-0001 must be executed before it can pass. | Y |
| REQ-F-015 | PIT data integrity launch gate: V4 launch workflow must block if daily PIT data checks fail. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-N-001 | Reproducibility: One documented command regenerates V4 weights bit-for-bit. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-N-002 | Testability: Each REQ-F must have at least one automated test in tests/. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-N-003 | Documentation parity: V4 must produce attribution, capacity, and stress reports analogous to Pillar 5 Stages 5.4-5.6. | SATISFIED-PENDING-ADR | Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution. | N |
| REQ-N-004 | Source-of-truth discipline: V4 weights cache and reconstruction script must agree by construction. | BLOCKING-UNTIL-REMEDIATED | This requirement directly requires cache/reconstruction agreement by construction; ADR-0001 must be executed before it can pass. | Y |

## Gate Interpretation
REQ-F-014 and REQ-N-004 are the only requirements that directly block V4 start under strict change control because they require source-of-truth convergence. Other requirements can be designed against a provisional cache-order baseline, but final V4 acceptance cannot occur until ADR-0001 is executed and reconciliation passes.

## Post-ADR Resolution
Date: 2026-05-30

ADR-0001 Option 1 (cache order / single-pass) was executed by aligning Stage 4.5 V3 reconstruction with the Pillar 5 cache-generation semantics. Post-ADR reconciliation passed with mean weight L1 = 0.00e+00 and max return diff = 0.0000 bps in `results/pillar5_stage58_v3_reconciliation_post_adr.csv`.

Stage 4 drift check found material movement in 12 published metrics under the strict published-precision rule; Stage 4 documentation should be reviewed in a separate update workstream. This does not reopen Verdict C because source-of-truth reconciliation now passes exactly.
