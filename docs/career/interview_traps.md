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

I would focus on Pillar 5. First, add no-trade bands to avoid unnecessary small
rebalance trades. Second, add a turnover penalty in the optimizer and tune it
against gross-signal preservation, not just net Sharpe. Third, run leave-one-out
factor ablations to remove inputs that increase turnover without improving
gross alpha. After that I would rerun gross/net attribution and compare the
implementation drag before and after.

## What questions would you ask the interviewer?

1. How does your team separate gross alpha attribution from implementation
   costs in practice?
2. What turnover range is typical for a mid-frequency factor strategy here?
3. When attribution shows negative post-cost pure alpha, how do you decide
   whether to kill the strategy or fix implementation?
4. How often is your risk model recalibrated: daily, weekly, or event-driven?
5. What does a typical week look like for someone in this seat?
