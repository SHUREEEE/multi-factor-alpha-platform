# V4 Launch Handoff

Status: ENGINEERING READY, LIVE LAUNCH BLOCKED ON PB BORROW FEED

## Evidence Summary

- E1 acceptance gates: `17 PASS / 0 PARTIAL / 0 FAIL`
- Acceptance artifact: `results/v4_e1_acceptance_gates.json`
- Replay manifest: `results/v4_e1_replay/v4_replay_manifest.json`
- Source-of-truth builder/cache reconciliation: `src.portfolio.v4.builder.build_v4_weights` and `src.portfolio.v4.reconciliation.reconcile_cache_to_builder`
- Prod-loader scaffold: `scripts/run_v4_pipeline.py --inputs-prod`
- Live readiness checklist: `reports/v4_live_readiness_checklist.md`
- Launch evidence bundle wrapper: `scripts/build_v4_launch_evidence_bundle.py`
- Launch go/no-go guard: `scripts/check_v4_launch_go_no_go.py`
- Current go/no-go artifact: `results/v4_launch_go_no_go.json`

## Local Engineering Closure

All V4 REQ-F and REQ-N rows in `reports/v4_design.md` are `MERGED`.

The local pipeline can:

- Read canonical V3 cache inputs for a single as-of date.
- Build V4 weights through the canonical builder.
- Write cache artifacts.
- Rebuild and reconcile cache output automatically.
- Produce replay, acceptance, readiness, and risk reports.
- Open local incident records.
- Provide a kill-switch operator runbook.
- Emit a machine-readable launch go/no-go decision.
- Bundle PB dry-run and go/no-go evidence into one manifest.

## External Launch Blocker

Live launch remains blocked until the real PB borrow feed is delivered and wired.

Required external evidence:

- Production PB borrow file delivery path.
- Daily freshness SLA and monitoring owner.
- Schema match to `docs/v4_pb_borrow_feed_contract.md`.
- Successful PB-gated dry-run with real PB borrow data via `scripts/run_v4_pb_live_dry_run.py --borrow-feed <path>` and no synthetic borrow assumption.
- A `READY` decision from `scripts/check_v4_launch_go_no_go.py --pb-dry-run-manifest <manifest>`.
- A `READY` bundle from `scripts/build_v4_launch_evidence_bundle.py`.

Synthetic borrow in replay is acceptable for E1 evaluation only. It is not live borrow readiness.

## Do Not Proceed Conditions

- Do not launch with synthetic borrow.
- Do not relax PIT, borrow, drawdown, ADV20, or acceptance thresholds.
- Do not regenerate or mutate V3 canonical cache.
- Do not claim launch readiness from Sharpe-only evidence.
- Do not bypass `scripts/check_v4_launch_go_no_go.py`.

## Next Authorized Action

The next workflow should be a PB-feed live wiring workflow. Its only purpose is to replace the synthetic borrow assumption with real PB feed ingestion, run `scripts/build_v4_launch_evidence_bundle.py --borrow-feed <path>`, and update `reports/v4_live_readiness_checklist.md` only if the feed passes schema and freshness checks and the bundle reports `READY`.
