"""Run a V4 prod dry-run gated by real PB borrow feed validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_v4_pipeline import main as run_v4_pipeline_main
from scripts.validate_v4_pb_feed import validate_pb_feed_file
from src.portfolio.v4.borrow import BorrowFeedSchemaError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a PB borrow feed, then run a V4 prod dry-run.")
    parser.add_argument("--asof", required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--borrow-feed", required=True, type=Path)
    parser.add_argument("--v3-cache-dir", type=Path, default=PROJECT_ROOT / "results" / "pillar5_artifacts")
    parser.add_argument("--max-age-days", type=int, default=1)
    args = parser.parse_args(argv)
    if not args.config.exists():
        parser.error("--config must point to an existing file")
    if args.max_age_days < 0:
        parser.error("--max-age-days must be non-negative")

    args.output.mkdir(parents=True, exist_ok=True)
    validation_path = args.output / "pb_borrow_validation.json"
    dry_run_manifest_path = args.output / "v4_pb_live_dry_run_manifest.json"

    try:
        validation = validate_pb_feed_file(
            args.borrow_feed,
            asof=args.asof,
            v3_cache_dir=args.v3_cache_dir,
            max_age_days=args.max_age_days,
        )
    except (BorrowFeedSchemaError, RuntimeError, ValueError) as exc:
        validation = {
            "pass_fail": False,
            "reason": str(exc),
            "borrow_feed": str(args.borrow_feed),
            "asof": args.asof,
        }
    _write_json(validation_path, validation)

    if not bool(validation.get("pass_fail")):
        _write_json(
            dry_run_manifest_path,
            _manifest(args, validation_path, pipeline_exit_code=None, status="PB_FEED_VALIDATION_FAIL"),
        )
        return 1

    pipeline_exit = run_v4_pipeline_main(
        [
            "--asof",
            args.asof,
            "--config",
            str(args.config),
            "--output",
            str(args.output),
            "--inputs-prod",
            "--v3-cache-dir",
            str(args.v3_cache_dir),
            "--borrow-feed",
            str(args.borrow_feed),
        ]
    )
    status = "PASS" if pipeline_exit == 0 else "PIPELINE_FAIL"
    _write_json(
        dry_run_manifest_path,
        _manifest(args, validation_path, pipeline_exit_code=pipeline_exit, status=status),
    )
    return 0 if pipeline_exit == 0 else 1


def _manifest(args: argparse.Namespace, validation_path: Path, *, pipeline_exit_code: int | None, status: str) -> dict[str, object]:
    return {
        "workflow": "v4_pb_live_dry_run",
        "status": status,
        "asof": args.asof,
        "config": str(args.config),
        "output": str(args.output),
        "borrow_feed": str(args.borrow_feed),
        "v3_cache_dir": str(args.v3_cache_dir),
        "pb_validation_report": str(validation_path),
        "pipeline_exit_code": pipeline_exit_code,
        "synthetic_borrow_used": False,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
