# Architecture

This project is organized as a seven-pillar research pipeline. The architecture
is intentionally modular because the final question in quant research is rarely
"did the backtest go up?" The real question is where the return came from, what
assumptions were required to produce it, and which layer failed when the result
was weak.

## Pipeline Flow

```text
Universe -> Data -> Factors -> Alpha Combination -> Portfolio -> Backtest -> Attribution
```

Each layer writes artifacts consumed by the next layer. That makes the pipeline
reproducible and also makes it possible to quarantine one layer without
throwing away the whole project. Pillar 7 is the current example: the
attribution code exists and is tested, but the local market-cap data is missing,
so the report refuses to publish a Barra-style claim.

## Pillars 1-2: Universe and Data

The first two pillars define the research sample and the data contract. Price
data is available in `data/processed/prices.parquet`, including adjusted close
and daily returns. Fundamental data is designed to be point-in-time lagged, but
the full-universe fundamentals panel remains coverage-gated. That missing
full-universe coverage is not a minor detail: market capitalization is required
for both size/value factors and sqrt(market_cap) weighted risk-model
regressions. A 416-name market-cap-ready attribution subset now restores the
real-market-cap path without using equal-cap fallback.

The data layer therefore has two roles. It provides usable price inputs for the
active v1 strategy, and it explicitly blocks claims that require unavailable
fundamental fields. This is why the attribution command fails closed by
default.

## Pillar 3: Factor Library

The factor library implements reusable signal definitions. Price factors
include momentum, short-term reversal, 52-week-high, beta inverse,
idiosyncratic volatility, and realized volatility. Fundamental factor modules
also exist for value, quality, and size, but they cannot contribute meaningful
live values until the fundamentals pipeline is populated.

Raw factor definitions preserve economic meaning. If research later decides
that a factor should be inverted in this sample, that decision is recorded in
the combination layer rather than silently rewriting the factor itself. This
keeps the audit trail clean.

## Pillar 4: Alpha Combination

Pillar 4 combines individual factor scores into candidate alpha models. It
uses research diagnostics such as IC, long-short quantile spreads, and
Fama-MacBeth regressions to decide which signals and direction transforms are
allowed into the portfolio path.

The important architectural decision is that research-approved transforms are
separate from raw factor computation. For example, low-volatility factors can
retain their textbook definitions while the combination layer records that the
sample evidence required a different sign or weighting. This is especially
important for v1 because several low-volatility signals behaved poorly during
the 2014-2024 large-cap US sample.

## Pillar 5: Portfolio Construction

Pillar 5 turns alpha scores into a long-short book. It handles exposure
normalization, beta and sector controls, capacity analysis, transaction costs,
stress checks, and production-style risk controls. This layer is where v1's
main performance issue appears.

Gross PnL sums to 1.055, while net PnL sums to 0.595. That 0.46 cumulative
return gap is implementation drag. Annual turnover is 85.6x/year, which is too
high for the strength of the signal. Architecturally, this means the
neutralization and daily re-solve layer is not just a risk-control layer; it is
also an alpha leakage point. v2 should make this layer turnover-aware rather
than simply more constrained.

## Pillar 6: Backtest Engine

The backtest engine enforces T+1 alignment. Target weights decided at date T
earn returns from T+1, not from the same close used to compute the signal. It
writes PnL, NAV, trades, metrics, and manifests under `results/backtest/`.

The v1 headline metrics are intentionally modest: net Sharpe is 0.39, annual
return is 4.54%, max drawdown is 26.19%, and hit rate is 48.99%. These numbers
are not dressed up as a strong strategy. They are treated as evidence that the
research system is working well enough to identify a weak implementation.

## Pillar 7: Risk Model and Attribution

Pillar 7 estimates cross-sectional factor returns and decomposes portfolio
returns into factor contribution, pure alpha, and implementation cost. The
intended model is Barra-style weighted least squares with sqrt(market_cap)
weights and industry controls.

The full 516-name workspace cannot publish full-universe attribution because
the market-cap coverage contract is not met. Earlier artifacts used
equal-positive fallback, which would
turn the regression into something much closer to ordinary least squares while
still looking like a Barra report. The script now prevents that by default. A
smoke-test override exists only for testing the reporting path, and its output
is not a publishable attribution. The restored publishable path is the
416-name market-cap-ready subset documented in
`reports/market_cap_attribution_restoration.md`.

## Extended Engineering Layer

The repository also includes an extended production-engineering layer: ADRs,
launch handoff documents, kill switch runbooks, PB borrow feed contracts,
acceptance gates, reconciliation checks, and risk monitoring scaffolds. This
layer is supplementary to the core strategy, but it supports the same central
theme: disciplined systems should expose uncertainty and block unsafe claims.

## Current v1 Narrative

The v1 architecture successfully answers a hard question: what if the strategy
does not work? The answer is not to invent a stronger result. The answer is to
show the pipeline, measure the weak net performance, separate gross signal from
implementation drag, quarantine unsupported attribution, and write down the v2
research plan. That is the core architectural value of the project.
