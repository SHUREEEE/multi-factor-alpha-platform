# V4 PB Borrow Feed Contract

Status: CONTRACT READY, LIVE FEED PARTIAL

V4 requires a real PB borrow feed before live launch. The replay path uses synthetic borrow assumptions and must not be interpreted as live PB coverage.

Required schema:

| column | type | required |
| --- | --- | --- |
| `date` | date | yes |
| `symbol` | string | yes |
| `locate_available_shares` | numeric | yes |
| `borrow_rate_bps` | numeric | yes |
| `utilization_pct` | numeric | yes |
| `htb_flag` | boolean-like | yes |
| `feed_timestamp_utc` | timestamp UTC | yes |

Validation is implemented by `src.portfolio.v4.borrow.validate_pb_borrow_feed_schema` and raises `BorrowFeedSchemaError` on schema failure. The standalone validator can be run before a pipeline dry-run:

```powershell
python scripts\validate_v4_pb_feed.py --asof 2026-05-30 --borrow-feed <pb_borrow_feed.csv> --v3-cache-dir results\pillar5_artifacts --output results\v4_artifacts\pb_borrow_validation.json
```

The validator checks schema, feed freshness, zero locates for required active shorts, and missing required active shorts. It exits 0 on pass, 1 on validation failure, and 2 on argument error.

Dry-run command:

```powershell
python scripts\run_v4_pipeline.py --asof 2026-05-30 --config config\v4.yaml --output results\v4_artifacts --inputs-prod --borrow-feed <pb_borrow_feed.csv>
```

PB-gated dry-run command:

```powershell
python scripts\run_v4_pb_live_dry_run.py --asof 2026-05-30 --config config\v4.yaml --output results\v4_artifacts --borrow-feed <pb_borrow_feed.csv> --v3-cache-dir results\pillar5_artifacts
```

The gated wrapper writes `pb_borrow_validation.json` first. If validation fails, it exits 1 before invoking `run_v4_pipeline.py` and no weights cache is produced.

Launch evidence bundle command:

```powershell
python scripts\build_v4_launch_evidence_bundle.py --asof 2026-05-30 --config config\v4.yaml --output results\v4_launch_evidence --borrow-feed <pb_borrow_feed.csv> --v3-cache-dir results\pillar5_artifacts
```

The bundle command runs the PB-gated dry-run, evaluates `scripts\check_v4_launch_go_no_go.py`, and writes `v4_launch_evidence_bundle.json`. The bundle must report `READY` before live readiness can be updated.

Live readiness remains PARTIAL until the production PB file delivery, monitoring owner, and daily freshness SLA are wired outside this repository scaffold.
