# Interview Q&A

## Q1: What is the project in one minute?

This is an end-to-end multi-factor US equity research platform covering 2014 to
2024. It starts with universe and data engineering, builds reusable factor
definitions, runs factor research, combines selected signals, constructs a
long-short portfolio, backtests it with T+1 alignment, and attempts Barra-style
risk attribution. The important point is that v1 is not presented as a
high-Sharpe strategy. The realized net Sharpe is 0.39, annual return is 4.54%,
and turnover is 85.6x/year. The contribution is the research discipline: gross
versus net separation, attribution quarantine, and fail-closed reporting when
market-cap data is missing. The pipeline surfaces that portfolio construction
and implementation drag are the binding problems instead of hiding them behind
an attractive headline metric.

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
available dates, although the current local fundamentals file is empty. Tests
cover the shift behavior directly: a weight introduced on day two cannot earn
the same day's return. The project also avoids silently filling missing factor
or market-cap data in ways that would create false precision. The risk
attribution now refuses to run without usable market caps rather than creating
a misleading Barra claim.

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
fundamental value/quality/size factors where data exists. Because local
fundamentals are empty, the active v1 portfolio is price-factor driven. Earlier
research found short-term reversal to be the cleanest standalone signal, while
several low-volatility signals behaved opposite to their textbook direction in
this 2014-2024 large-cap US sample. Pillar 4 records direction transforms
separately from raw factor definitions so the research decision is auditable:
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
residual is pure alpha before costs. The current workspace cannot publish this
as a valid Barra attribution because the market-cap panel is missing. The
script now fails closed unless positive market caps cover the fitted universe.
An explicit equal-cap fallback exists only for smoke tests and is labeled as
such.

## Q12: Why is sqrt(market_cap) weighting important?

Sqrt(market_cap) weighting is a compromise between equal weighting and full
market-cap weighting. It makes the regression more representative of the
investable market without letting the largest names completely dominate the
fit. In a Barra-style model, this matters because factor returns should reflect
the behavior of economically meaningful cross-sectional exposures, not just the
average behavior of many tiny or illiquid names. That is why the missing
market-cap panel is a blocking issue. If the model silently uses equal-positive
fallback, the regression becomes much closer to ordinary least squares, and the
"Barra-style" claim becomes misleading. v1 now prevents that by default.

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
implementation subtract value. I would be careful, though: the formal
Barra-style attribution is quarantined because the market-cap panel is missing,
so I would not publish the exact pure-alpha number as a final risk-model
result. The broader finding is still useful. Attribution frameworks exist to
surface exactly this kind of problem: the value-add was not where I initially
thought it was. v2 should restore proper market caps, rerun attribution, ablate
the factors, and reduce neutralization intensity.

## Q16: Walk me through how you would fix this in v2.

First, I would restore a real daily market-cap panel, ideally from shares
outstanding times adjusted price, and rerun sqrt(market_cap) weighted
attribution without fallback. Second, I would run leave-one-out ablations over
the six active price factors to find which inputs are value-destroying,
especially idiosyncratic volatility, realized volatility, and 52-week-high
exposure. Third, I would reduce Pillar 5 neutralization intensity with
turnover penalties and no-trade bands, because current implementation drag is
about 0.46 cumulative return points. Fourth, I would test regime-aware factor
weighting so low-volatility signals are not forced into the same allocation in
growth-led and defensive regimes. The goal is not curve fitting; it is
identifying which layer actually leaks value.
