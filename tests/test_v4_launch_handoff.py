"""Tests for V4 launch handoff documentation."""

from __future__ import annotations

from pathlib import Path


def test_launch_handoff_records_external_pb_blocker() -> None:
    text = Path("docs/v4_launch_handoff.md").read_text(encoding="utf-8")

    assert "LIVE LAUNCH BLOCKED ON PB BORROW FEED" in text
    assert "17 PASS / 0 PARTIAL / 0 FAIL" in text
    assert "Do not launch with synthetic borrow." in text
    assert "Do not bypass `scripts/check_v4_launch_go_no_go.py`." in text
    assert "PB-feed live wiring workflow" in text


def test_launch_handoff_references_core_artifacts() -> None:
    text = Path("docs/v4_launch_handoff.md").read_text(encoding="utf-8")

    assert "results/v4_e1_acceptance_gates.json" in text
    assert "reports/v4_live_readiness_checklist.md" in text
    assert "results/v4_launch_go_no_go.json" in text
    assert "docs/v4_pb_borrow_feed_contract.md" in text
    assert "scripts/build_v4_launch_evidence_bundle.py" in text
    assert "scripts/run_v4_pb_live_dry_run.py" in text
    assert "scripts/check_v4_launch_go_no_go.py" in text
