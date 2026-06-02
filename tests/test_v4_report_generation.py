"""Tests for E1 V4 report generation.

Covers: REQ-N-003.
"""

from __future__ import annotations

import json

import pandas as pd

from scripts.run_v4_reports import REPORT_NAMES, generate_v4_reports


def test_v4_report_generation_writes_all_five_e1_reports(tmp_path) -> None:
    replay, gates = _e1_artifacts(tmp_path)

    paths = generate_v4_reports(replay, gates, tmp_path / "reports")

    assert set(paths) == set(REPORT_NAMES)
    assert {path.name for path in paths.values()} == set(REPORT_NAMES)


def test_v4_acceptance_gate_report_contains_17_gate_rows(tmp_path) -> None:
    replay, gates = _e1_artifacts(tmp_path)

    paths = generate_v4_reports(replay, gates, tmp_path / "reports")
    text = paths["v4_acceptance_gate.md"].read_text(encoding="utf-8")

    assert text.count("| G-") == 17


def test_v4_live_readiness_checklist_marks_live_dependencies_partial_and_loader_ready(tmp_path) -> None:
    replay, gates = _e1_artifacts(tmp_path)

    paths = generate_v4_reports(replay, gates, tmp_path / "reports")
    text = paths["v4_live_readiness_checklist.md"].read_text(encoding="utf-8")

    for item in ["PB borrow real feed"]:
        assert f"| {item} | P0 | PARTIAL |" in text
    for item in ["PIT audit live wiring", "ADV20 daily refresh", "incident sink", "kill switch operator runbook", "prod input loader"]:
        assert f"| {item} | P0 | READY |" in text


def test_v4_stress_report_contains_required_regime_sections(tmp_path) -> None:
    replay, gates = _e1_artifacts(tmp_path)

    paths = generate_v4_reports(replay, gates, tmp_path / "reports")
    text = paths["v4_stress_regime.md"].read_text(encoding="utf-8")

    assert "2022_rate_shock" in text
    assert "high_vol_regime" in text


def test_v4_reports_do_not_make_sharpe_only_launch_readiness_claim(tmp_path) -> None:
    replay, gates = _e1_artifacts(tmp_path)

    paths = generate_v4_reports(replay, gates, tmp_path / "reports")

    for path in paths.values():
        text = path.read_text(encoding="utf-8").lower()
        assert "ready for launch based on sharpe" not in text
        assert "launch ready based on sharpe" not in text


def _e1_artifacts(tmp_path):
    replay = tmp_path / "v4_e1_replay"
    replay.mkdir()
    dates = pd.bdate_range("2022-01-03", periods=260, name="date")
    diagnostics = pd.DataFrame(
        {
            "participation_p95": 0.03,
            "short_top10_share": 0.20,
            "htb_notional_share": 0.0,
            "sector_net_max": 0.10,
            "beta_20d": 0.0,
            "beta_60d": 0.0,
        },
        index=dates,
    )
    returns = pd.DataFrame({"daily_return_bps": [10.0, -5.0] * 130}, index=dates)
    pit = pd.DataFrame({"pit_status": "PASS"}, index=dates)
    diagnostics.to_parquet(replay / "v4_diagnostics_panel.parquet")
    returns.to_parquet(replay / "v4_returns_panel.parquet")
    pit.to_parquet(replay / "v4_pit_audit_log.parquet")
    gates = tmp_path / "v4_e1_acceptance_gates.json"
    payload = [
        {
            "gate_id": f"G-{idx:02d}",
            "req_id": "REQ-F-001",
            "metric_name": "metric",
            "observed_value": 1.0,
            "threshold": 1.0,
            "comparator": ">=",
            "status": "PASS",
            "evidence_path": str(replay / "v4_diagnostics_panel.parquet"),
        }
        for idx in range(17)
    ]
    gates.write_text(json.dumps(payload), encoding="utf-8")
    return replay, gates
