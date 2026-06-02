# Pillar 5 Stage 5.7 - Live-Readiness Operational Checklist

## Plan

1. Synthesize locked Pillar 5 findings from Stages 5.1 through 5.6 without running new backtests.
2. Convert each finding into an institutional pre-launch checklist item with status, owner, and launch-blocking flag.
3. Carry forward Stage 5.4 capacity/turnover/borrow findings as pre-trade and financing controls.
4. Carry forward Stage 5.5 sector-net widening and residual-beta findings as risk-monitoring controls.
5. Carry forward Stage 5.6 regime results: trend-down weakness, 2022 rate-shock residual-beta paradox, and 20d/60d beta monitoring requirements.
6. Add multi-tier drawdown halt controls: -10% soft halt, -15%/-20% hard halt, and -8% single-day loss.
7. Add a separate warning section for findings that complicate the V4 fix path, outside the pass/fail checklist grid.

## Executive Summary
- Launch readiness: **NO-GO for live capital** until blocking fails are resolved. There are 16 launch-blocking items: 12 fail and 4 partial.
- The biggest V4 blockers are turnover-aware neutralization, sector-net constraints, short concentration, participation caps, residual beta monitoring, and canonical source-of-truth reconciliation.
- Stage 5.6 changes the regime-control design: V3 is weak in negative 60d market trend, not high vol. V4 should use trend-conditioned sizing, not a blunt vol filter.

## Status Legend
- pass = current V3 / current process is acceptable for this control.
- partial = concept exists or evidence is favorable, but live-ready implementation is incomplete.
- fail = missing or materially insufficient for launch.
- N/A = not applicable.

## Go / No-Go
| status | blocking_for_launch | size |
| --- | --- | --- |
| fail | Y | 12 |
| partial | N | 4 |
| partial | Y | 4 |
| pass | N | 3 |

## Findings That Complicate The V4 Fix Path
| warning | why_it_matters | V4_watch_out |
| --- | --- | --- |
| Sector net widening (5.5) | Beta neutralization reduced ex-ante beta but widened sector net exposure from 7.5% raw to 14.1% post-V3. | Do not optimize beta in isolation; add sector net constraints inside the neutralization objective. |
| 2022 rate-shock paradox (5.6) | Residual beta drifted on 56.6% of days, yet V3 returned +11.9% with Sharpe 1.14. | A cleaner neutralization layer may remove P&L-positive exposure; require counterfactual replay before approving the fix. |
| Capacity-driven AUM ceiling (5.4) | Capacity is <$5M under current live-readiness rules due to tail turnover and borrow concentration. | Do not evaluate V4 at institutional AUM until turnover, participation, and short-book constraints are solved. |
| Fast-event beta measurement blind spot (5.6) | COVID crash shows 0 high residual-beta days under 60d beta, likely because the window is too slow. | Use 20d and 60d beta monitors together; do not treat 60d-only calm as proof of risk control. |

## Checklist By Category
### Pre-trade controls
| item_id | control | status | owner | blocking_for_launch | pillar5_evidence | current_v3_status | v4_requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PT-001 | Production gross leverage fixed at 1.405x for 10% target vol | pass | Risk / PM | N | 5.1 selected 10% vol target, k=0.7025, production gross=1.405x. | Keep static gross cap at 1.405x until V4 dynamic sizing is approved. | Hard gross cap in order generation and daily risk report. |
| PT-002 | Dynamic volatility overlay evaluation | partial | V4 strategy work | N | 5.1 showed static 10% target can realize ~26% 60d vol in high-vol regimes. | Evaluate dynamic vol targeting, but do not use a blunt high-vol off switch because 5.6 found high-vol Sharpe is strong. | Backtest dynamic vol overlay without reducing SPY 20d vol top-quartile Sharpe below current baseline. |
| PT-003 | Turnover cap / no-trade band in neutralization optimizer | fail | V4 strategy work | Y | 5.4 capacity ceiling <$5M is driven by tail rotation days; non-rebalance turnover 27.4% vs rebalance 7.0%. | Add turnover penalty or no-trade band to daily beta-neutralization / sector-cap solve. | Non-rebalance-day mean turnover < 2x rebalance-day mean turnover; >100% turnover days reduced by at least 75%. |
| PT-004 | Participation cap by name and day | fail | Ops infra work | Y | 5.4 p95 participation breaches quickly; mid-cap names such as APH/MOS/PTC/OKE bind capacity. | Enforce projected participation limit before orders are released. | No order plan exceeds 5% ADV participation without explicit PM/risk approval. |
| PT-005 | Sector net constraint after beta-neutral solve | fail | V4 strategy work | Y | 5.5 found post-V3 max abs sector net 14.1% vs raw 7.5%; beta-neutralization widened sector net exposure. | Constrain sector net exposure inside the beta-neutral optimizer, not only as a side cap. | Post-solve average max abs sector net <= raw baseline and p95 max abs sector net <= 15%. |

### Risk monitoring
| item_id | control | status | owner | blocking_for_launch | pillar5_evidence | current_v3_status | v4_requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RM-001 | Residual beta 60d monitoring | partial | Ops infra work | Y | 5.5 residual alpha beta=0.269; 5.6 found 2022 rate shock had |beta|>0.4 on 56.6% of days. | Compute rolling 60d realized beta daily and alert on drift. | Warn at |beta_60d| > 0.25; hard review at |beta_60d| > 0.40 for 5 consecutive days. |
| RM-002 | Residual beta 20d fast-event monitoring | fail | Ops infra work | Y | 5.6 COVID crash shows zero high-beta days under 60d threshold, likely because 60d beta smooths fast events. | Add 20d realized beta monitor alongside 60d to catch fast dislocations. | Warn at |beta_20d| > 0.30; hard review at |beta_20d| > 0.50 for 3 consecutive days. |
| RM-003 | Trend-based regime sizing monitor | fail | V4 strategy work | Y | 5.6 refuted high-vol weakness; weak regime is SPY 60d return bottom quartile, Sharpe=-0.074 over 677 days. | Compute daily SPY 60d trailing return percentile vs trailing 3y distribution and reduce sizing in bottom quartile. | When SPY 60d trend percentile is bottom quartile, V4 regime-conditioned Sharpe >= 0 and drawdown improves vs V3. |
| RM-004 | Do not use blunt high-vol kill filter | pass | Risk / PM | N | 5.6 found SPY 20d vol top-quartile Sharpe=1.624 vs bottom-quartile Sharpe=0.500. | High vol alone is not a de-risk trigger; use trend and realized risk jointly. | Risk policy states vol-only filter is informational, not automatic sizing reduction. |
| RM-005 | Factor tape for size/value/momentum attribution | partial | Ops infra work | N | 5.5 could not prove residual alpha is not hidden size/value/momentum exposure because canonical factor returns are unavailable. | Source or build approved factor-return tape for institutional attribution. | Daily size/value/momentum factor returns available and reconciled to attribution engine. |
| RM-006 | VaR / expected shortfall budget | fail | Ops infra work | Y | Pillar 5 covered DD and stress windows but did not implement formal VaR/ES limits. | Add rolling historical VaR/ES risk budget before live launch. | Daily 95/99% VaR and ES produced, with breach escalation and PM signoff. |

### Borrow / financing
| item_id | control | status | owner | blocking_for_launch | pillar5_evidence | current_v3_status | v4_requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BF-001 | Short top-10 concentration limit | fail | V4 strategy work | Y | 5.4 found top-10 short concentration=48.7%, structurally independent of AUM. | Add explicit short-side concentration constraint. | Top-10 short concentration <= 25%; no single short > 5% of short book absent approval. |
| BF-002 | HTB exposure cap | partial | Ops infra work | Y | 5.4 HTB-proxy share=25.5%, near the 30% borrow-feasible threshold. | Replace market-cap/ADV proxy with PB borrow feed and enforce HTB cap. | HTB notional < 25% of short book using PB locate/utilization data. |
| BF-003 | Borrow cost stress monitor | partial | Ops infra work | N | 5.3 break-even borrow cost is ~700 bps, robust but analytic and not PB-confirmed. | Track realized borrow fees and rerun borrow stress weekly. | Daily borrow fee file available; projected fee drag included in pre-trade P&L. |

### Operational
| item_id | control | status | owner | blocking_for_launch | pillar5_evidence | current_v3_status | v4_requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OP-001 | Soft halt at -10% rolling 60d drawdown | fail | Ops infra work | Y | 5.6 worst requested window return=-9.1%; institutional review should occur before -20% kill switch. | Add soft halt requiring PM/risk review at -10% rolling 60d drawdown. | Automated alert and documented review before next rebalance after breach. |
| OP-002 | Hard halt at -15% rolling 60d drawdown | partial | Risk / PM | Y | 5.2 hard stop was -12% de-risk and kill switch -20%; 5.7 adds institutional hard halt tier. | Define hard halt action: freeze new risk or cut gross by at least 50%. | Policy implemented and historically simulated before paper trading. |
| OP-003 | Single-day loss halt at -8% | fail | Ops infra work | Y | Single-day operational loss limit was not defined in 5.1-5.6. | Add -8% single-day loss halt with immediate order freeze and risk review. | Intraday/close-to-close loss monitor triggers order block and incident ticket. |
| OP-004 | Existing -20% kill switch retained as capital-preservation backstop | pass | Risk / PM | N | 5.2 and 5.6 found no tested window breaches -20%; still useful as terminal kill switch. | Keep -20% kill switch but do not rely on it as first review point. | Policy includes -10%, -15%, and -20% tiers with explicit actions. |
| OP-005 | Slippage and impact monitoring | fail | Ops infra work | Y | 5.4 shows impact is capacity-binding because of tail rotation days. | Compare realized execution cost to modeled square-root impact daily. | Daily slippage report by name, order, sector, and rotation-day tag. |
| OP-006 | Canonical V3 source-of-truth reconciliation | fail | V4 strategy work | Y | 5.5 found reconstructed Stage 4.5 V3 does not exactly match locked Pillar 5 cache. | Decide and document canonical production book path; deprecate the other path. | One reproducible command regenerates locked V3 weights bit-for-bit or documents intentional versioning. |

### Data integrity
| item_id | control | status | owner | blocking_for_launch | pillar5_evidence | current_v3_status | v4_requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DI-001 | Point-in-time prices and returns checks | partial | Ops infra work | Y | Pillar 5 uses existing processed prices; live launch needs automated PIT validation. | Add PIT validation checks for prices, returns, and corporate-action adjustments. | Daily data audit passes before signal generation. |
| DI-002 | Survivorship and universe audit | partial | Ops infra work | N | Pillar 4/5 universe construction uses available processed data; launch needs explicit survivorship audit. | Document universe membership and delisting treatment. | Universe audit report generated for backtest and paper-trading periods. |
| DI-003 | ADV20 real-time refresh | fail | Ops infra work | Y | 5.4 capacity relies on ADV20; live capacity should re-evaluate ADV around earnings/events. | Refresh ADV20 daily and block stale liquidity estimates. | No order generated if ADV20 missing/stale; event-day liquidity override documented. |


## Output
- Machine-readable checklist: `results/pillar5_stage57_checklist_status.csv`.

## 5.8 Handoff Note
Do not start Stage 5.8 until this checklist, especially the warning section above, has been reviewed. The V4 spec must trace every launch-blocking item and every warning to an explicit requirement.
