# Project Brief

## One-Minute Positioning

This project is an end-to-end US equity multi-factor research and risk
engineering platform covering 2014 to 2024. It is built as a seven-pillar
pipeline:

```text
Universe -> Data -> Factors -> Alpha Combination -> Portfolio -> Backtest -> Attribution
```

The project is not marketed as a live-ready alpha product. Its stronger claim
is that it demonstrates research discipline: reproducible backtesting, T+1
alignment, gross/net separation, implementation-drag diagnosis, fail-closed
risk attribution, and production-style launch controls.

## What Makes It Competitive

1. It is end to end rather than a single notebook. The repository includes
   reusable modules, command-line workflows, tests, generated artifacts, ADRs,
   runbooks, and release documentation.
2. It treats weak results honestly. The v1 strategy has a 0.39 net Sharpe and
   85.6x annual turnover, so the project freezes that result and explains why
   the portfolio construction layer is leaking value.
3. It blocks unsupported claims. Barra-style attribution requires a positive
   market-cap panel; when full-universe coverage is insufficient, the reporting
   path fails closed instead of publishing an equal-cap fallback. A separate
   416-name market-cap-ready subset now passes the real-market-cap contract and
   runs attribution without fallback.
4. It includes a production-engineering candidate layer. V4 adds acceptance
   gates, replay evidence, data-integrity checks, drawdown halts, borrow
   constraints, kill-switch runbooks, and a machine-readable launch
   go/no-go guard.

## Evidence Snapshot

| Area | Evidence |
| --- | --- |
| Core backtest | `results/backtest/metrics.json` |
| Research narrative decision | `reports/pillar6_7_narrative_pivot.md` |
| Attribution quarantine and restoration | `reports/pillar6_7_attribution_quarantine.md`, `reports/market_cap_attribution_restoration.md` |
| V4 acceptance gates | `reports/v4_acceptance_gate.md` |
| V4 fixed time-split validation | `results/v4_walk_forward/walk_forward_report.md` |
| V4 parameter-selected walk-forward | `results/v4_walk_forward_selection_full/v4_walk_forward_selection_report.md` |
| Factor leave-one-out ablation | `results/factor_ablation/factor_ablation_report.md` |
| V4 launch handoff | `docs/v4_launch_handoff.md` |
| Launch go/no-go artifact | `results/v4_launch_go_no_go.json` |
| Data and artifact policy | `docs/data_policy.md` |
| Fundamentals ingestion guide | `docs/fundamentals_ingestion_guide.md` |
| Interview prep | `docs/career/` |

## v1 Research Findings

| Metric | Value |
| --- | ---: |
| Net Sharpe | 0.39 |
| Annual return | 4.54% |
| Max drawdown | -26.19% |
| Annual turnover | 85.6x |
| Gross PnL sum | 1.055 |
| Net PnL sum | 0.595 |
| Implementation drag | 0.46 cumulative return points |

The main v1 conclusion is that the signal and portfolio construction stack is
not yet investable. The system identifies the binding issue as implementation
drag: gross signal survives better than net performance, while aggressive
neutralization and high turnover erode returns.

## V4 Engineering Candidate

V4 is a production-engineering improvement track. It is designed to address
turnover-aware construction and launch discipline, not to create a Sharpe-only
marketing claim.

| Gate | Result |
| --- | ---: |
| Acceptance gates | 17 PASS / 0 PARTIAL / 0 FAIL |
| Full-sample acceptance Sharpe | 1.05 |
| 2022 shock Sharpe | 1.14 |
| Time-split test windows | 6 / 6 positive Sharpe |
| Weakest test window | 2024, Sharpe 0.05 |
| Parameter-selected test windows | 5 / 6 positive Sharpe |
| Weakest selected test window | 2021, Sharpe -0.04 |
| Factor ablation finding | Dropping `week_52_high` improves no-cost combo Sharpe by 0.07 |
| Launch decision | BLOCKED |
| Current P0 blocker | Real PB borrow feed |

The launch blocker is intentional. Synthetic borrow assumptions are acceptable
for replay and engineering evaluation, but live-readiness language requires a
real PB borrow feed, freshness checks, schema validation, a PB-gated dry run,
and a `READY` launch evidence bundle.

## What Not To Claim

- Do not claim the strategy is live-ready.
- Do not claim full-universe publishable Barra attribution until the full
  market-cap panel reaches the coverage contract.
- Do claim only the documented 416-name market-cap-ready subset attribution
  when discussing restored no-fallback Barra attribution.
- Do not treat equal-market-cap fallback attribution as a production result.
- Do not treat v4 acceptance gates as out-of-sample proof by themselves.
- Do not hide v1's weak net Sharpe or high turnover.

## Next Work

The next highest-value work is:

1. Add a more complete historical fundamentals vendor to lift the full
   516-name universe above the 95% daily market-cap coverage contract.
2. Extend `scripts/run_v4_walk_forward_selection.py` from replay-scaffold
   parameter selection into a full retraining walk-forward study.
3. Promote the leave-one-out factor ablation into the V4 optimizer loop,
   especially reviewing `week_52_high`.
4. Compare turnover penalties and no-trade bands against implementation drag.
5. Wire a real PB borrow feed and rerun the launch evidence bundle.

## Interview Framing

The strongest way to describe the project is:

> I built a full-stack quant research platform, then used it to diagnose why
> the first strategy result was not investable. The project shows how I handle
> data contracts, backtest alignment, risk attribution, production guardrails,
> and honest research decisions, rather than just optimizing for a headline
> Sharpe.
