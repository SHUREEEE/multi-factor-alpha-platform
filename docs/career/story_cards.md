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
diagnostics were more interesting than the returns. Later, v4 acceptance gates
looked much stronger, which created a new risk: overcorrecting from "weak v1"
to "live-ready v4" language.

**Task:** I needed to decide whether to keep tuning the strategy or freeze v1
and present the research truth cleanly, while also explaining how v4 relates to
that v1 diagnosis.

**Action:** I wrote a narrative pivot: v1 is not a finished alpha product; it
is a complete research platform that exposes implementation drag, missing
market-cap attribution inputs, and the need for a v2 redesign. Then I separated
the public story into two connected tracks: v1 as the research diagnosis and v4
as an engineering candidate with explicit launch blockers.

**Result:** The project became more credible. It now demonstrates research
discipline, engineering hygiene, fail-closed reporting, and a concrete v2
roadmap rather than a fragile optimized backtest or a premature live-readiness
claim.

## Story D: V4 Launch Gate

**Situation:** V4 passed the local acceptance-gate suite: 17 pass, 0 partial, 0
fail, with a full-sample acceptance Sharpe around 1.05. It would have been easy
to describe that as launch-ready.

**Task:** I needed to distinguish local engineering evidence from actual live
readiness, especially because the strategy has a short book and therefore
depends on real borrow availability.

**Action:** I added launch handoff documentation, PB borrow-feed contract
boundaries, a live-readiness checklist, dry-run expectations, and a
machine-readable go/no-go guard. The guard remains `BLOCKED` until a real PB
borrow feed is delivered, validated, and included in the launch evidence
bundle.

**Result:** The project shows production judgment. V4 can be presented as a
better engineered candidate, but not as a live strategy. The blocker is
specific, testable, and documented: real PB borrow-feed readiness.

## Story E: Reviewer Packaging

**Situation:** The repository had a lot of evidence: tests, reports, ADRs,
acceptance gates, launch handoff docs, and career notes. But a reviewer could
miss the strongest story if they had to discover it by reading everything.

**Task:** I needed to make the project understandable in five minutes without
watering down the technical content.

**Action:** I rewrote the README opening around a version map and added a
project brief that links the core evidence artifacts. The packaging now names
what the project proves, what it does not prove, what is blocked, and what the
next research work should be.

**Result:** The project became easier to evaluate. The first-read path now
shows the same message as the interview pitch: full-stack research discipline,
honest weak-result diagnosis, v4 engineering controls, and explicit boundaries
around attribution and live readiness.

## Story F: Walk-Forward Evidence

**Situation:** V4 acceptance gates and full-sample metrics looked much stronger
than v1, but relying only on full-sample evidence would have weakened the
research story.

**Task:** I needed to test whether the v4 result survived a more realistic
train/test framing without pretending I had completed a full production
research loop.

**Action:** I added two validation layers. First, a fixed return-stream
time-split diagnostic. Second, a parameter-selection walk-forward replay: each
window selects v4 parameters on the train period and evaluates only the chosen
configuration on the next test year.

**Result:** The selected-parameter test windows were positive in 5 out of 6
years, with mean selected-test Sharpe around 0.95. The test also exposed weak
windows: 2021 was negative and 2024 was near flat. That made the project
stronger because the evidence improved without losing the caution around live
alpha claims.
