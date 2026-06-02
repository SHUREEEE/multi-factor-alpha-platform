# Pillar 6/7 Narrative Pivot

## Decision

For v1, do not chase a higher Sharpe ratio before publishing the project
narrative. The project will ship as an honest research-and-attribution case
study rather than as a high-Sharpe strategy claim.

This is a deliberate scope decision, not a retreat from the research process.
The current artifacts show that the engineering framework works, but the
strategy result is weak: net Sharpe is below the sanity range, turnover is high,
and the quarantined attribution indicates negative pure alpha after costs. A
v1 README that hides those facts would be less credible than one that explains
them.

## Reframing

This project's main contribution is not a high-Sharpe number. It is a complete
research-to-attribution pipeline with explicit self-criticism via gross/net
separation, fail-closed reporting, and quarantine documentation when the data
does not support a claim.

The central story is:

- build the pipeline end to end,
- measure the actual net result,
- decompose where performance is lost,
- refuse to publish misleading attribution when market-cap data is missing,
- document what v2 should fix.

That is supplementary to the README, not a replacement for it. The README
should present the project as a rigorous research system whose v1 finding is
that portfolio construction and implementation drag are the binding problems.

## Interview Findings

### Finding 1: Implementation drag is the binding constraint

Net Sharpe is 0.39, while gross Sharpe is 0.69. Gross PnL sums to 1.055, while
net PnL sums to 0.595, so implementation drag is about 0.46 cumulative return
points. That identifies the portfolio construction and trading layer as the
main leakage point rather than allowing the project to blame the signal layer
alone.

### Finding 2: Pure alpha is negative after costs

Using the quarantined equal-market-cap smoke attribution, pure alpha is negative
when costs are included: -92% of net return. The interpretation is that the
six-factor combination's return is explained by factor exposure itself, while
the portfolio construction layer subtracts value through high turnover and
aggressive neutralization. Because the market-cap panel is missing, this result
is treated as a diagnostic finding, not as a publishable Barra attribution.

### Finding 3: Fail-closed reporting prevented a bad claim

The initial attribution would have claimed a Barra-style decomposition while
using equal-positive market-cap fallback. The v1 pipeline now refuses to run
that report by default. This is exactly the kind of production discipline the
project is intended to demonstrate: if the data cannot support the claim, the
report does not get published.

## v2 Research Plan

1. Restore the daily market-cap panel so the risk model can run proper
   sqrt(market_cap) weighted cross-sectional regressions.
2. Run factor ablations across the six price factors, including leave-one-out
   and reduced low-volatility variants, to identify value-destroying inputs.
3. Reduce Pillar 5 neutralization intensity and add no-trade bands or turnover
   penalties to reclaim alpha lost through implementation drag.
4. Test regime-aware factor weighting so low-volatility and reversal signals
   are not forced through the same exposure profile in all market regimes.

## Boundary

This document records the v1 narrative decision. It does not replace the README,
the attribution quarantine, or the v2 research plan. It exists so future readers
can see that the weak headline metrics were acknowledged deliberately rather
than discovered accidentally during an interview.
