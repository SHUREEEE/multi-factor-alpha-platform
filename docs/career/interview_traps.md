# Interview Traps And Safe Answers

## Your Sharpe is low. How do you prove you understand alpha?

I agree the v1 strategy is weak. I do not pitch it as a finished alpha product.
The value of the project is the research platform: it separates gross signal,
net implementation cost, risk attribution, and unsupported data claims. The
system found that net Sharpe is 0.39 while gross Sharpe is higher, and that the
main leak is implementation drag. That is exactly the kind of diagnosis a
research platform should produce.

## Why not fix Pillar 5 before applying?

Because the scope decision matters. v1 already answers the main diagnostic
question: the portfolio construction and trading layer is leaking value. A v2
would target no-trade bands, turnover penalties, softer neutralization, and
factor ablations. For a portfolio project, I think it is more honest to freeze
the weak result and document the next research step than to keep tuning until
the backtest looks cleaner.

## V4 has stronger acceptance metrics. Are you now claiming the strategy works?

No. V4 is an engineering candidate, not a finished live alpha claim. The local
acceptance gates passing is useful evidence that the redesigned construction
and risk-control layer satisfies the requirements I defined for replay. But it
is not the same as publishable attribution or live readiness. I added
parameter-selection walk-forward diagnostics, and those are encouraging but
mixed: 5 of 6 selected test windows have positive Sharpe, while 2021 is
negative and 2024 is near flat. I would describe v4 as a better engineered
candidate with partial OOS-style replay evidence that still needs real
market-cap attribution, full retraining validation, and PB borrow-feed readiness
before stronger claims are appropriate.

## If V4 passes 17 gates, why not call it production-ready?

Because one P0 dependency is still external and unresolved: the real PB borrow
feed. A long-short strategy cannot treat synthetic borrow as live short-book
readiness. The go/no-go artifact is intentionally `BLOCKED` until a real feed
is delivered, schema-validated, freshness-monitored, and run through the PB
dry-run and launch evidence bundle. That is not a cosmetic blocker; it is a
real production boundary.

## Your fundamentals file is empty. Why not fake or approximate it?

Because market-cap data is a contract for the attribution claim. If I do not
have a positive daily market-cap panel, I should not publish sqrt-market-cap
weighted Barra-style attribution. The script now fails closed by default and
allows equal-cap fallback only for smoke tests. I would rather show a blocked
claim than a misleading one.

## 85x annual turnover is high. Is that acceptable?

No. That is one of the main findings. The annual turnover tells me the current
neutralization and rebalancing logic is too aggressive for the strength of the
signal. My first v2 change would be a turnover-aware portfolio construction
layer with no-trade bands, explicit turnover penalties, and a comparison of
gross/net PnL preservation.

## If you had one week to improve v1, what would you do?

I would make the work evidence-first rather than just tune the backtest. First,
restore the market-cap panel so attribution can run without fallback. Second,
run leave-one-out factor ablations to remove inputs that increase turnover
without improving gross alpha. Third, compare no-trade bands and turnover
penalties against gross-signal preservation and net implementation drag. If the
focus is v4 specifically, I would extend the current parameter-selection
walk-forward into a full retraining study and wire the real PB borrow feed
through the launch evidence bundle.

## What questions would you ask the interviewer?

1. How does your team separate gross alpha attribution from implementation
   costs in practice?
2. What turnover range is typical for a mid-frequency factor strategy here?
3. When attribution shows negative post-cost pure alpha, how do you decide
   whether to kill the strategy or fix implementation?
4. How often is your risk model recalibrated: daily, weekly, or event-driven?
5. What does a typical week look like for someone in this seat?
