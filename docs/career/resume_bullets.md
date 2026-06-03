# Resume Bullets

Use one version depending on the role. Keep the project title consistent:
`Multi-Factor Alpha Research & Risk Engineering Platform`.

## Risk Attribution Version

- Built an end-to-end US equity multi-factor research platform covering
  universe construction, factor engineering, T+1 backtesting, and Barra-style
  risk-attribution diagnostics across a 2014-2024 sample.
- Implemented gross/net attribution discipline that surfaced a 0.46 cumulative
  implementation drag between gross and net PnL instead of overstating headline
  alpha.
- Added fail-closed attribution safeguards: the reporting path refuses to
  publish Barra-style WLS attribution without a valid positive market-cap
  panel, with equal-cap fallback reserved for smoke tests only.
- Documented attribution quarantine and narrative pivot decisions through
  ADR-style research records, separating valid diagnostics from unsupported
  production claims.
- Added a v4 engineering candidate with acceptance gates and a machine-readable
  launch go/no-go guard, explicitly blocking live-readiness claims until real
  PB borrow data is validated.
- Added parameter-selection walk-forward replay diagnostics showing 5/6
  positive selected-test Sharpe windows while preserving documented weak-window
  caveats.

## Quant Developer Version

- Developed a seven-pillar quant research platform in Python spanning data
  cleaning, factor computation, alpha combination, portfolio construction,
  backtesting, reporting, and risk attribution.
- Added 291 automated tests covering T+1 execution alignment, PnL accounting,
  factor research, portfolio constraints, V4 acceptance gates, data integrity,
  and live-readiness boundaries.
- Built reproducible command-line workflows and source-of-truth artifacts for
  backtests, acceptance gates, launch handoff checks, PB borrow-feed validation,
  and kill-switch runbooks.
- Prepared a public-repo version with dependency metadata, Git hygiene,
  artifact/data policy, and explicit research limitations for interview review.
- Organized reviewer-facing documentation around a project brief, version map,
  evidence artifacts, and explicit v1/v4 readiness boundaries.
- Implemented CLI validation workflows for market-cap contract checks and V4
  walk-forward parameter selection, with JSON/CSV/Markdown evidence outputs.

## Strategy Implementation Version

- Implemented a long-short multi-factor US equity strategy pipeline with
  transaction-cost modeling, capacity checks, sector/beta constraints, and T+1
  vectorized backtesting.
- Diagnosed weak v1 performance honestly: net Sharpe 0.39, annual return 4.54%,
  max drawdown 26.19%, and annual turnover 85.6x, indicating implementation
  drag rather than a finished investable alpha.
- Traced the primary performance leak to Pillar 5 portfolio construction,
  where gross PnL of 1.055 fell to net PnL of 0.595 after trading frictions and
  aggressive neutralization.
- Defined a v2 roadmap with real market-cap restoration, leave-one-out factor
  ablations, no-trade bands, turnover penalties, and regime-aware factor
  weighting.
- Built a v4 candidate layer that passed local acceptance gates while preserving
  a hard launch blocker on real PB borrow-feed readiness.
- Evaluated V4 with train-window parameter selection and next-year test windows,
  surfacing mixed OOS-style evidence rather than relying on full-sample metrics.
