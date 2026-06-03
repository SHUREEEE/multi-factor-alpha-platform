# Reviewer Guide

## 30 Seconds

Read the README TL;DR and Version Map.

The core claim is not that this is a live-ready high-Sharpe strategy. The claim
is that this is a reproducible quant research and risk-engineering platform
that can diagnose weak results, block unsupported attribution, and document
production readiness boundaries.

## 5 Minutes

Read:

1. `docs/PROJECT_BRIEF.md`
2. `results/v4_walk_forward_selection_full/v4_walk_forward_selection_report.md`
3. `results/factor_ablation/factor_ablation_report.md`
4. `docs/fundamentals_contract.md`
5. `results/v4_launch_go_no_go.json`

The most important evidence:

| evidence | why it matters |
| --- | --- |
| v1 net Sharpe 0.39 and annual turnover 85.6x | Shows the project does not hide weak investable performance. |
| Implementation drag 0.46 cumulative return points | Identifies portfolio construction and trading as the binding issue. |
| Market-cap contract and fail-closed attribution | Prevents unsupported Barra-style attribution claims. |
| V4 17/17 acceptance gates | Shows local engineering controls satisfy defined replay requirements. |
| V4 selected-parameter walk-forward 5/6 positive test windows | Adds OOS-style replay evidence while preserving weak-window caveats. |
| Factor ablation: dropping `week_52_high` improves no-cost combo Sharpe | Identifies a concrete v2 research target instead of vague tuning. |
| Launch go/no-go BLOCKED | Keeps live-readiness language tied to real PB borrow data. |

## 15 Minutes

Read:

1. `docs/architecture.md`
2. `reports/pillar6_7_narrative_pivot.md`
3. `reports/pillar6_7_attribution_quarantine.md`
4. `docs/v4_launch_handoff.md`
5. `docs/career/interview_traps.md`

Then inspect the implementation entry points:

```powershell
python scripts\run_backtest.py --weights results\pillar5_artifacts\v3_weights.parquet --prices data\processed\prices.parquet --output results\backtest
python scripts\build_market_cap_panel.py --fundamentals data\processed\fundamentals.parquet --prices data\processed\prices.parquet --output data\processed\daily_fundamentals.parquet --report data\processed\daily_fundamentals_contract.json --input-format long --lag-days 45
python scripts\run_v4_walk_forward_selection.py --v3-cache-dir results\pillar5_artifacts --output results\v4_walk_forward_selection_full --train-years 5 --test-years 1
```

## Do Not Over-Interpret

- Do not call the strategy live-ready.
- Do not call the quarantined equal-cap smoke attribution publishable Barra attribution.
- Do not treat V4 acceptance gates as final alpha proof.
- Do not ignore the weak 2021 and near-flat 2024 selected-test windows.
- Do not treat synthetic borrow as real short-book readiness.

## Good Interview Summary

> I built a full-stack quant research platform, then used it to diagnose why
> the first strategy result was not investable. V4 improves the construction
> and risk-control layer and has encouraging replay walk-forward evidence, but
> the project still blocks live-readiness and publishable attribution claims
> until the data contracts and PB borrow feed are satisfied.
