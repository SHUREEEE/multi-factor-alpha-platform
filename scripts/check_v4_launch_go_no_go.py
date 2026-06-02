"""Evaluate V4 launch go/no-go from local readiness artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether V4 has local launch go evidence.")
    parser.add_argument("--gates", type=Path, default=Path("results/v4_e1_acceptance_gates.json"))
    parser.add_argument("--readiness", type=Path, default=Path("reports/v4_live_readiness_checklist.md"))
    parser.add_argument("--pb-dry-run-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = check_launch_go_no_go(
        gates_path=args.gates,
        readiness_path=args.readiness,
        pb_dry_run_manifest_path=args.pb_dry_run_manifest,
    )
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if report["decision"] == "READY" else 1


def check_launch_go_no_go(
    *,
    gates_path: Path,
    readiness_path: Path,
    pb_dry_run_manifest_path: Path | None = None,
) -> dict[str, object]:
    failures: list[str] = []
    gate_counts = _gate_counts(gates_path)
    if gate_counts["PARTIAL"] or gate_counts["FAIL"]:
        failures.append("ACCEPTANCE_GATES_NOT_ALL_PASS")

    readiness = _readiness_rows(readiness_path)
    p0_not_ready = sorted(item for item, row in readiness.items() if row["priority"] == "P0" and row["status"] != "READY")
    if p0_not_ready:
        failures.append("P0_READINESS_NOT_READY")

    pb_manifest: dict[str, object] | None = None
    if pb_dry_run_manifest_path is None:
        failures.append("PB_DRY_RUN_MANIFEST_MISSING")
    else:
        pb_manifest = _read_json(pb_dry_run_manifest_path)
        if pb_manifest.get("status") != "PASS":
            failures.append("PB_DRY_RUN_NOT_PASS")
        if pb_manifest.get("synthetic_borrow_used") is not False:
            failures.append("PB_DRY_RUN_SYNTHETIC_BORROW")
        if pb_manifest.get("pipeline_exit_code") != 0:
            failures.append("PB_DRY_RUN_PIPELINE_NOT_ZERO")

    return {
        "decision": "READY" if not failures else "BLOCKED",
        "failures": failures,
        "gate_counts": gate_counts,
        "p0_not_ready": p0_not_ready,
        "pb_dry_run_manifest": str(pb_dry_run_manifest_path) if pb_dry_run_manifest_path is not None else None,
        "pb_dry_run_status": pb_manifest.get("status") if pb_manifest is not None else None,
        "reason": "READY" if not failures else ",".join(failures),
    }


def _gate_counts(path: Path) -> dict[str, int]:
    data = _read_json(path)
    rows = data if isinstance(data, list) else data.get("gates", [])
    return {status: sum(1 for row in rows if row.get("status") == status) for status in ("PASS", "PARTIAL", "FAIL")}


def _readiness_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|") or "---" in line or " item " in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 3:
            continue
        item, priority, status = cells
        rows[item] = {"priority": priority, "status": status}
    return rows


def _read_json(path: Path) -> object:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
