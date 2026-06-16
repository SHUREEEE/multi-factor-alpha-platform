# Release Notes: v1.0-research-complete

This release packages the first complete public research snapshot of the
multi-factor alpha research and risk-engineering platform.

## Headline Results

- v1 net Sharpe: 0.39, with 4.54% annual return and -26.19% max drawdown.
- Gross Sharpe diagnostic: 0.69.
- Annual turnover: 85.6x/year.
- Implementation drag: about 0.46 cumulative return points.
- Barra-style pure-alpha attribution: quarantined until a real positive
  market-cap panel is restored.

## Key Findings

The v1 strategy is intentionally framed as a weak net strategy with a strong
diagnostic trail. Gross signal exists, but implementation drag is the binding
constraint. Attribution is fail-closed rather than allowed to publish an
unsupported equal-market-cap fallback result.

The v4 engineering layer adds turnover-aware construction, replay manifests,
risk controls, acceptance gates, live-readiness checklists, and PB borrow-feed
boundaries. It is engineering-ready locally, but live launch remains blocked
until a real PB borrow feed is delivered and validated.

