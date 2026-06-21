# Interview Q&A

## Q1: What is the project in one minute?

This is an end-to-end US equity multi-factor research and risk-engineering
platform covering 2014 to 2024. It starts with universe and data engineering,
builds reusable factor definitions, runs factor research, combines selected
signals, constructs a long-short portfolio, backtests it with T+1 alignment,
and attempts Barra-style risk attribution.

I describe it as two connected tracks. The v1 track is the research diagnosis:
net Sharpe is 0.39, annual return is 4.54%, and turnover is 85.6x/year, so I do
not pitch it as investable. The value is that the pipeline identifies
implementation drag, blocks unsupported attribution claims when market-cap
coverage is insufficient, and now restores no-fallback Barra attribution for a
416-name market-cap-ready subset. The v4 track is an engineering candidate: it adds
turnover-aware construction, acceptance gates, replay evidence, kill-switch
runbooks, PB borrow-feed boundaries, and a machine-readable launch go/no-go
guard. V4 passes local acceptance gates, but live launch is still blocked until
a real PB borrow feed is wired and validated.

## Q2: Why use a seven-pillar architecture?

The seven-pillar structure separates research responsibilities that often get
blurred in quant projects. Universe construction and data cleaning define what
can be traded and observed. Factor modules define raw signals. Research tools
test whether those signals have cross-sectional value. Alpha combination turns
research findings into a model score. Portfolio construction handles
neutralization, costs, capacity, and risk controls. Backtesting measures net
realized performance with T+1 alignment. Attribution asks whether the return
came from intended alpha, public factor exposure, or implementation effects.
This separation made the v1 failure diagnosable: the weak net result was not
just "bad alpha"; it was also high turnover and neutralization drag.

## Q3: How do you avoid look-ahead bias?

The backtest uses a strict T+1 convention. Signals and target weights decided
at date T earn returns from T+1 onward, so weights are shifted before being
multiplied by returns. Price-based factors use only historical adjusted close
and rolling windows. Fundamental inputs are designed to use point-in-time lagged
available dates. The current price-only research path is fully reproducible,
while full-universe market-cap and fundamentals attribution remains
coverage-gated. Tests cover the shift behavior directly: a weight introduced on
day two cannot earn the same day's return. The project also avoids silently
filling missing factor or market-cap data in ways that would create false
precision. The risk attribution refuses to run without usable market caps
rather than creating a misleading Barra claim, and the restored 416-name subset
attribution uses real market-cap inputs rather than equal-cap fallback.

## Q4: Why use adjusted close instead of close?

Adjusted close is necessary because dividends and splits change raw prices
without representing tradable alpha. If a stock splits two-for-one, raw close
would show a roughly 50% drop, and any momentum, reversal, or volatility factor
would interpret that as a real return shock. Using adjusted close keeps the
return series economically meaningful. In this project, price-based factors
such as momentum, short-term reversal, 52-week high, beta, and realized
volatility are computed from adjusted close or returns derived from it. That is
a basic data hygiene decision, but it matters: a sophisticated attribution
model cannot rescue a return stream polluted by corporate-action artifacts.

## Q5: How did you choose the factor set?

The initial library includes common equity styles: momentum, reversal,
52-week-high, idiosyncratic volatility, beta inverse, realized volatility, and
fundamental value/quality/size factors where data exists. Because the
full-universe fundamentals panel is incomplete, the active v1 portfolio is
price-factor driven, while the market-cap-ready subset is used for no-fallback
risk attribution. Earlier research found short-term reversal to be the cleanest
standalone signal, while several low-volatility signals behaved opposite to
their textbook direction in this 2014-2024 large-cap US sample. Pillar 4
records direction transforms separately from raw factor definitions so the
research decision is auditable:
raw signals remain economically interpretable, while the combination layer can
use empirically validated signs.

## Q6: What did the factor research show?

The strongest single-factor research finding is that short-term reversal was
the cleanest price-only signal, especially after sector neutralization. Momentum
was weaker: after removing sector effects, its long-short economics largely
collapsed, suggesting the raw signal was picking up sector rotation more than
stock-specific continuation. The low-volatility family was the most
counterintuitive. Idiosyncratic volatility and realized volatility showed weak
or reversed premia, consistent with a regime where high-volatility growth names
outperformed. That matters because the final portfolio cannot be defended by
saying "these are standard factors." The sample-specific behavior has to be
measured, and v2 should ablate the low-volatility inputs carefully.

## Q7: What is the difference between IC and Fama-MacBeth here?

IC measures rank correlation between today's factor scores and future returns,
usually day by day and then averaged. It is useful for directional signal
quality, but a weak average IC can hide a small but stable coefficient.
Fama-MacBeth runs cross-sectional regressions of returns on factors for each
date, then evaluates the time series of coefficients. In this project, that
distinction matters because some low-volatility factors had noisy IC but more
consistent negative regression evidence. The interpretation is not simply
"factor has no signal"; it can be "the signal exists, but the sign is wrong for
this regime." That distinction influenced the direction transforms used in the
combination layer.

## Q8: Why separate raw factor definitions from direction transforms?

Raw factor definitions should encode the economic concept. For example,
`idiosyncratic_vol` is defined as lower residual volatility scoring higher,
which matches the low-volatility anomaly. If research finds that this premium
is reversed in the sample, rewriting the raw factor would erase the audit trail.
Instead, the project keeps raw definitions stable and records direction
transforms in the combination layer. That makes the research decision explicit:
the model is not pretending the economic theory changed; it is saying the
sample evidence required a sign adjustment. This is also safer for interviews,
because every signal has both a theoretical definition and an empirical usage
record.

## Q9: How does the portfolio construction layer work?

Pillar 5 takes combined alpha scores and turns them into long-short weights
with gross exposure, net exposure, beta, sector, cost, and capacity controls.
The intent was to produce a more tradable and risk-controlled book than a raw
factor sort. In v1, however, this layer is also where a lot of value is lost.
Gross PnL sums to 1.055 while net PnL sums to 0.595, and annual turnover is
85.6x/year. That points to neutralization and daily re-solving as too
aggressive. The correct interpretation is not "remove risk controls"; it is
"make risk controls turnover-aware." v2 should introduce no-trade bands,
turnover penalties, and softer neutralization targets.

## Q10: How do transaction costs enter the backtest?

The backtest computes trades from target weight changes and subtracts daily
transaction costs from gross PnL. The current cost model includes linear bps
costs and optional square-root impact support, though the active backtest uses
the configured default cost path. The important accounting change is that
attribution now separates gross return from transaction cost. Previously, the
old attribution summary reported gross total return of 1.055 while the official
backtest metrics were based on net PnL of 0.595. That mismatch is now surfaced
as implementation drag rather than hidden. In an interview, I would emphasize
that net performance is the only investable performance, and gross performance
is a diagnostic tool.

## Q11: What is Barra-style attribution in this project?

The risk model estimates daily factor returns through cross-sectional
regressions of stock returns on factor exposures and industry controls. The
intended Barra-style feature is sqrt(market_cap) weighted least squares, which
gives larger, more liquid names more influence in the cross-section. Portfolio
factor exposure times factor return gives factor contribution, and the
residual is pure alpha before costs. The full 516-name workspace cannot publish
full-universe Barra attribution because market-cap coverage remains below the
contract. The script fails closed unless positive market caps cover the fitted
universe. A 416-name market-cap-ready subset now passes the contract and runs
without fallback. An explicit equal-cap fallback exists only for smoke tests
and is labeled as such.

## Q12: Why is sqrt(market_cap) weighting important?

Sqrt(market_cap) weighting is a compromise between equal weighting and full
market-cap weighting. It makes the regression more representative of the
investable market without letting the largest names completely dominate the
fit. In a Barra-style model, this matters because factor returns should reflect
the behavior of economically meaningful cross-sectional exposures, not just the
average behavior of many tiny or illiquid names. That is why insufficient
market-cap coverage is a blocking issue. If the model silently uses
equal-positive fallback, the regression becomes much closer to ordinary least
squares, and the "Barra-style" claim becomes misleading. v1 now prevents that
by default, and the market-cap-ready subset uses real market caps.

## Q13: Why quarantine the attribution instead of deleting it?

Quarantine preserves the research trail without letting bad numbers become
headline claims. The old attribution output is informative as a diagnostic: it
showed factor contribution greater than total return and negative pure alpha.
But it was not publishable because it used equal-positive market-cap fallback
and mixed gross attribution with net backtest metrics. Deleting it would hide
the mistake; publishing it would overclaim. Quarantine is the middle path: the
project documents what went wrong, changes the script to fail closed, and
defines the gate required to unquarantine Pillar 7. That is closer to how
production research systems should behave.

## Q14: Your Sharpe is only 0.39. Why?

The net Sharpe is low because the edge is marginal and the implementation layer
is too expensive. Gross Sharpe is 0.69, which suggests there is some pre-cost
signal, but net Sharpe falls to 0.39 after transaction costs and trading
frictions. The implementation drag is about 0.46 cumulative return points, and
annual turnover is 85.6x/year, so v1 trades too aggressively for the strength
of the signal. The hit rate is 48.99%, which also says the strategy is close to
noise and relies on a small win/loss payoff edge. I would not pitch this as a
finished alpha product. I would pitch it as a complete research pipeline whose
main finding is that portfolio construction, turnover, and neutralization must
be redesigned before the signal can be investable.

## Q15: Your pure alpha is negative. Doesn't that mean your strategy doesn't work?

Yes, for v1 that is the right interpretation. The quarantined smoke attribution
shows negative pure alpha after costs, meaning the six-factor portfolio's
return is explained by public factor exposure while portfolio construction and
implementation subtract value. I would be careful, though: full-universe
Barra-style attribution is still coverage-gated because the complete
market-cap panel is not available. I would use the 416-name restored subset for
publishable no-fallback attribution and avoid presenting it as full-universe
attribution. The broader finding is still useful. Attribution frameworks exist
to surface exactly this kind of problem: the value-add was not where I
initially thought it was. v2 should continue with factor ablation and reduced
neutralization intensity.

## Q16: Walk me through how you would fix this in v2.

First, I restored a real daily market-cap path from SEC shares outstanding
times adjusted price and reran sqrt(market_cap) weighted attribution without
fallback on a market-cap-ready subset. Next, I would add a more complete
historical fundamentals vendor so the full universe clears the same contract.
Second, I would run leave-one-out ablations over
the six active price factors to find which inputs are value-destroying,
especially idiosyncratic volatility, realized volatility, and 52-week-high
exposure. Third, I would reduce Pillar 5 neutralization intensity with
turnover penalties and no-trade bands, because current implementation drag is
about 0.46 cumulative return points. Fourth, I would test regime-aware factor
weighting so low-volatility signals are not forced into the same allocation in
growth-led and defensive regimes. The goal is not curve fitting; it is
identifying which layer actually leaks value.

## Q17: What changed from v1 to v4?

V1 established the research pipeline and diagnosed the first strategy result.
Its main finding was weak investable value after costs: net Sharpe was 0.39,
turnover was 85.6x/year, and implementation drag was about 0.46 cumulative
return points. V4 is the engineering response to that diagnosis. It adds
turnover-aware construction, risk-budget controls, capacity checks,
borrow-concentration constraints, drawdown halt logic, data-integrity checks,
acceptance gates, replay manifests, and launch handoff artifacts.

I would be careful not to overclaim v4. The local acceptance gates pass, and
the reported full-sample acceptance Sharpe is 1.05. I also added time-split and
parameter-selection walk-forward diagnostics: the selected-parameter test
windows are positive in 5 out of 6 years, with mean selected-test Sharpe around
0.95. But there are weak windows, including a negative 2021 test Sharpe and a
near-flat 2024 test Sharpe. The correct claim is that v4 is a better engineered
candidate with encouraging but mixed OOS-style replay evidence, not a live
strategy.

## Q18: If v4 passes acceptance gates, why is launch still blocked?

Because acceptance gates and live-readiness gates answer different questions.
The v4 acceptance gates check whether the local replay satisfies requirements
around turnover, sector exposure, beta monitoring, short concentration,
participation, VaR/ES, slippage tails, and stress-regime preservation. Those
are necessary engineering checks, but they do not prove the strategy can be
launched with real borrow availability.

The current go/no-go artifact is `BLOCKED` because the real PB borrow feed is
not delivered and validated. Synthetic borrow is acceptable for replay
evaluation, but not for live short-book readiness. Before using live-readiness
language, I would require a production PB feed path, schema match, freshness
SLA, PB-gated dry run, and a `READY` launch evidence bundle.

## Q19: What is the biggest remaining weakness of the public project?

The biggest remaining research weakness is full-universe fundamentals
coverage. The project now has real-market-cap attribution for a 416-name
subset, but the full 516-name universe still needs a more complete historical
fundamentals vendor before I would call full-universe Barra attribution
publishable.

The biggest validation weakness is that v4's current walk-forward evidence is
still replay-scaffold parameter selection, not a full retraining research loop.
That is stronger than a full-sample acceptance grid, but it still limits the
strategy claim. My next research step would be to extend the walk-forward into
a full retraining study, add full-universe fundamentals coverage, and run
leave-one-out factor ablations.

## Q20: How would you package this project differently for a quant researcher,
quant developer, and risk role?

For a quant researcher, I would emphasize the research controls: factor
diagnostics, IC and Fama-MacBeth analysis, direction transforms, gross/net
diagnosis, factor ablation roadmap, and the decision not to hide weak v1
metrics.

For a quant developer, I would emphasize the engineering surface: modular
pipeline, command-line workflows, tests, reproducible artifacts, source-of-truth
cache reconciliation, acceptance gates, launch bundle, and machine-readable
go/no-go output.

For a risk or portfolio implementation role, I would emphasize attribution
discipline, implementation drag, turnover-aware construction, sector/beta
constraints, capacity and borrow controls, drawdown halts, kill-switch runbooks,
and the refusal to claim launch readiness from Sharpe alone.
