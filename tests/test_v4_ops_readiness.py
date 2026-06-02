"""Tests for V4 local operations readiness scaffolds."""

from __future__ import annotations

import json

from src.portfolio.v4.ops import write_incident_record, write_kill_switch_runbook


def test_write_incident_record_creates_open_p0_json(tmp_path) -> None:
    path = write_incident_record({"incident_type": "V4_TEST", "reason": "unit"}, tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["incident_type"] == "V4_TEST"
    assert payload["severity"] == "P0"
    assert payload["status"] == "OPEN"
    assert payload["payload"]["reason"] == "unit"


def test_write_kill_switch_runbook_contains_operator_actions(tmp_path) -> None:
    path = write_kill_switch_runbook(tmp_path / "runbook.md")

    text = path.read_text(encoding="utf-8")
    assert "Stop V4 order generation" in text
    assert "Open a P0 incident record" in text
    assert "Do not relax PIT, borrow, drawdown, or acceptance thresholds" in text


def test_pb_borrow_feed_contract_documents_live_partial() -> None:
    from pathlib import Path

    text = Path("docs/v4_pb_borrow_feed_contract.md").read_text(encoding="utf-8")
    assert "LIVE FEED PARTIAL" in text
    assert "locate_available_shares" in text
    assert "BorrowFeedSchemaError" in text
    assert "--borrow-feed <pb_borrow_feed.csv>" in text
    assert "scripts\\build_v4_launch_evidence_bundle.py" in text
    assert "scripts\\check_v4_launch_go_no_go.py" in text
    assert "v4_launch_evidence_bundle.json" in text
