"""Tests for the V4 launch go/no-go checker."""

from __future__ import annotations

import json
import subprocess
import sys

from scripts.check_v4_launch_go_no_go import check_launch_go_no_go


def test_launch_go_no_go_blocks_without_pb_dry_run_manifest(tmp_path) -> None:
    gates = _gates(tmp_path, ["PASS", "PASS"])
    readiness = _readiness(tmp_path, pb_status="PARTIAL")

    report = check_launch_go_no_go(gates_path=gates, readiness_path=readiness)

    assert report["decision"] == "BLOCKED"
    assert "P0_READINESS_NOT_READY" in report["failures"]
    assert "PB_DRY_RUN_MANIFEST_MISSING" in report["failures"]
    assert report["p0_not_ready"] == ["PB borrow real feed"]


def test_launch_go_no_go_blocks_on_partial_gate_even_with_pb_pass(tmp_path) -> None:
    gates = _gates(tmp_path, ["PASS", "PARTIAL"])
    readiness = _readiness(tmp_path, pb_status="READY")
    pb_manifest = _pb_manifest(tmp_path, status="PASS")

    report = check_launch_go_no_go(gates_path=gates, readiness_path=readiness, pb_dry_run_manifest_path=pb_manifest)

    assert report["decision"] == "BLOCKED"
    assert "ACCEPTANCE_GATES_NOT_ALL_PASS" in report["failures"]


def test_launch_go_no_go_ready_when_all_evidence_passes(tmp_path) -> None:
    gates = _gates(tmp_path, ["PASS", "PASS"])
    readiness = _readiness(tmp_path, pb_status="READY")
    pb_manifest = _pb_manifest(tmp_path, status="PASS")

    report = check_launch_go_no_go(gates_path=gates, readiness_path=readiness, pb_dry_run_manifest_path=pb_manifest)

    assert report["decision"] == "READY"
    assert report["failures"] == []


def test_launch_go_no_go_blocks_synthetic_borrow_manifest(tmp_path) -> None:
    gates = _gates(tmp_path, ["PASS"])
    readiness = _readiness(tmp_path, pb_status="READY")
    pb_manifest = _pb_manifest(tmp_path, status="PASS", synthetic_borrow_used=True)

    report = check_launch_go_no_go(gates_path=gates, readiness_path=readiness, pb_dry_run_manifest_path=pb_manifest)

    assert report["decision"] == "BLOCKED"
    assert "PB_DRY_RUN_SYNTHETIC_BORROW" in report["failures"]


def test_launch_go_no_go_cli_exit_codes_and_writes_report(tmp_path) -> None:
    gates = _gates(tmp_path, ["PASS"])
    readiness = _readiness(tmp_path, pb_status="PARTIAL")
    output = tmp_path / "go_no_go.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_v4_launch_go_no_go.py",
            "--gates",
            str(gates),
            "--readiness",
            str(readiness),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "BLOCKED"


def _gates(tmp_path, statuses: list[str]):
    path = tmp_path / "gates.json"
    payload = [{"gate_id": f"G-{idx}", "status": status} for idx, status in enumerate(statuses)]
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _readiness(tmp_path, *, pb_status: str):
    path = tmp_path / "readiness.md"
    path.write_text(
        "\n".join(
            [
                "| item | priority | status |",
                "| --- | --- | --- |",
                "| PIT audit live wiring | P0 | READY |",
                f"| PB borrow real feed | P0 | {pb_status} |",
                "| ADV20 daily refresh | P0 | READY |",
                "| incident sink | P0 | READY |",
                "| kill switch operator runbook | P0 | READY |",
                "| prod input loader | P0 | READY |",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _pb_manifest(tmp_path, *, status: str, synthetic_borrow_used: bool = False):
    path = tmp_path / "pb_manifest.json"
    payload = {
        "status": status,
        "synthetic_borrow_used": synthetic_borrow_used,
        "pipeline_exit_code": 0 if status == "PASS" else 1,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
