# STAR Story Cards

## Story A: Implementation Drag

**Situation:** The v1 strategy had a weak headline result: net Sharpe 0.39,
annual return 4.54%, max drawdown 26.19%, and annual turnover 85.6x.

**Task:** I needed to understand whether the weakness came from the factor
signal itself, the portfolio construction layer, or trading costs.

**Action:** I separated gross and net PnL, added explicit transaction-cost
accounting, and traced the strategy through the seven-pillar pipeline. The key
diagnostic was that gross PnL summed to about 1.055 while net PnL summed to
0.595.

**Result:** The platform surfaced about 0.46 cumulative implementation drag.
That changed the v2 plan: instead of blindly adding more factors, the next
work should target Pillar 5 with no-trade bands, turnover penalties, softer
neutralization, and factor ablations.

## Story B: Attribution Quarantine

**Situation:** The project had a Barra-style attribution path, but the current
local fundamentals file did not contain a usable positive market-cap panel.
An earlier smoke-test path could use equal-positive market caps.

**Task:** I needed to prevent a misleading attribution claim while preserving
the diagnostic value of the old output.

**Action:** I changed the attribution command to fail closed unless valid
market caps are supplied. Equal-market-cap fallback now requires an explicit
smoke-test flag, and the README/reporting narrative labels the old attribution
as quarantined.

**Result:** The project avoids overstating "Barra-style" attribution. This is
a stronger interview story than pretending the attribution is production-ready:
it shows that the system can block unsupported claims when the required data
contract is not satisfied.

## Story C: Narrative Pivot

**Situation:** The initial temptation was to keep optimizing until the project
could show a more attractive Sharpe. But the honest v1 result was weak and the
diagnostics were more interesting than the returns.

**Task:** I needed to decide whether to keep tuning the strategy or freeze v1
and present the research truth cleanly.

**Action:** I wrote a narrative pivot: v1 is not a finished alpha product; it
is a complete research platform that exposes implementation drag, missing
market-cap attribution inputs, and the need for a v2 redesign.

**Result:** The project became more credible. It now demonstrates research
discipline, engineering hygiene, fail-closed reporting, and a concrete v2
roadmap rather than a fragile optimized backtest.
