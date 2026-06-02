# V4 Kill Switch Operator Runbook

## Trigger Conditions
- PIT launch gate failure.
- Terminal drawdown kill switch.
- Hard halt or unresolved single-day halt.
- PB borrow feed unavailable for affected order names.

## Operator Actions
1. Stop V4 order generation for the affected as-of date.
2. Preserve `results/v4_e1_replay/` and the current run manifest.
3. Open a P0 incident record using `write_incident_record`.
4. Notify the owner that manual review is required before restart.
5. Restart only after the incident record is closed outside this scaffold.

## Non-Actions
- Do not regenerate V3 cache.
- Do not relax PIT, borrow, drawdown, or acceptance thresholds.
- Do not claim live launch readiness from Sharpe alone.
