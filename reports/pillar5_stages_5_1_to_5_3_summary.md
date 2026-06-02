Pillar 5 Stages 5.1-5.3 Summary
================================

Production Sizing (from 5.1):
  Target vol         : 10%
  Leverage scaler    : k = 0.70
  Production gross   : 1.40 x
  Sharpe @ 10 bps    : 0.498
  Max DD             : -17.3%

Risk Limits (from 5.2):
  Soft warning       : -6.0%  (n_triggers = 45, fp_rate = 67%)
  Hard stop          : -12.0%  (n_triggers = 18, fp_rate = 72%)
  Kill switch        : -20.0% (n_triggers = 0, fp_rate = 0%)

Stress Results (from 5.3):
  Worst historical window : 2015 China crash, return = -8.7%, dd = -10.0%
  Beta shock -20%, gross-adjusted loss = -6.6%
  Borrow cost break-even  : 709 bps
  2023-10 root cause      : sector/factor stress led by Consumer Discretionary; window beta 0.39, not a pure market-beta shock.
  2023-10 DD reconciliation: Pillar4 rolling-return DD -45.8% on 2023-10-12 maps to sized capital DD -11.7%, not -32.2%.

Open items going into 5.4 / 5.5:
  - Add explicit factor-sleeve attribution for 2023-10 if per-factor production books are promoted to first-class artifacts.
  - Decide whether the production gross sanity band should be tied to realized vol or capped by policy.
  - Monitor realized beta under the volume-weighted proxy alongside the original equal-weight proxy.
