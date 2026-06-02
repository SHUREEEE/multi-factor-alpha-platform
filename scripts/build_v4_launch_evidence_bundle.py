"""Build a V4 launch evidence bundle from PB dry-run and go/no-go checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.check_v4_launch_go_no_go import main as go_no_go_main
from scripts.run_v4_pb_live_dry_run import main as pb_dry_run_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a V4 launch evidence bundle.")
    parser.add_argument("--asof", required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--borrow-feed", required=True, type=Path)
    parser.add_argument("--v3-cache-dir", type=Path, default=PROJECT_ROOT / "results" / "pillar5_artifacts")
    parser.add_argument("--gates", type=Path, default=PROJECT_ROOT / "results" / "v4_e1_acceptance_gates.json")
    parser.add_argument("--readiness", type=Path, default=PROJECT_ROOT / "reports" / "v4_live_readiness_checklist.md")
    parser.add_argument("--max-age-days", type=int, default=1)
    args = parser.parse_args(argv)
    if not args.config.exists():
        parser.error("--config must point to an existing file")
    if args.max_age_days < 0:
        parser.error("--max-age-days must be non-negative")

    args.output.mkdir(parents=True, exist_ok=True)
    pb_manifest = args.output / "v4_pb_live_dry_run_manifest.json"
    go_no_go_report = args.output / "v4_launch_go_no_go.json"
    bundle_path = args.output / "v4_launch_evidence_bundle.json"

    pb_exit = pb_dry_run_main(
        [
            "--asof",
            args.asof,
            "--config",
            str(args.config),
            "--output",
            str(args.output),
            "--borrow-feed",
            str(args.borrow_feed),
            "--v3-cache-dir",
            str(args.v3_cache_dir),
            "--max-age-days",
            str(args.max_age_days),
        ]
    )
    go_exit = go_no_go_main(
        [
            "--gates",
            str(args.gates),
            "--readiness",
            str(args.readiness),
            "--pb-dry-run-manifest",
            str(pb_manifest),
            "--output",
            str(go_no_go_report),
        ]
    )
    status = "READY" if pb_exit == 0 and go_exit == 0 else "BLOCKED"
    _write_json(
        bundle_path,
        {
            "workflow": "v4_launch_evidence_bundle",
            "status": status,
            "asof": args.asof,
            "pb_dry_run_exit_code": pb_exit,
            "go_no_go_exit_code": go_exit,
            "pb_dry_run_manifest": str(pb_manifest),
            "go_no_go_report": str(go_no_go_report),
            "borrow_feed": str(args.borrow_feed),
            "synthetic_borrow_used": False,
        },
    )
    return 0 if status == "READY" else 1


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
