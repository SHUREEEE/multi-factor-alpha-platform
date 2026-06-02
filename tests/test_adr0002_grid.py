"""Tests for ADR-0002 frozen grid discipline."""

from __future__ import annotations

import json

from scripts.run_adr0002_grid import (
    classify_point,
    decide,
    generate_adr0002_decision_report,
    parse_pre_registered_grid,
    run_adr0002_grid,
    run_sanity_probe,
)


def test_adr0002_pre_registration_parser_returns_16_points() -> None:
    grid = parse_pre_registered_grid(_pre_registration_path())

    assert len(grid) == 16
    assert grid[0] == {
        "turnover_penalty": 4.0,
        "no_trade_band_bps": 100.0,
        "lambda_beta": 10.0,
        "sector_net_cap": 0.10,
    }
    assert grid[-1]["turnover_penalty"] == 40.0


def test_adr0002_point_with_all_gates_pass_is_go_candidate() -> None:
    payload = [_gate("G-REQ-F-001-tail-turnover", "PASS"), _gate("G-Preserve-HighVol-Sharpe", "PASS"), _gate("G-Preserve-2022-Sharpe", "PASS"), _gate("G-REQ-F-002-sector-p95", "PASS")]

    assert classify_point(payload) == "GO-CANDIDATE"
    assert decide([{"classification": "GO-CANDIDATE"}]) == "GO-A"


def test_adr0002_all_rejected_decision_is_escalate_b() -> None:
    points = [{"classification": "REJECTED"} for _ in range(16)]

    assert decide(points) == "ESCALATE-B"


def test_adr0002_runner_deterministic_for_master_decision_with_fake_replay(tmp_path, monkeypatch) -> None:
    def fake_replay(v3_cache_dir, config_path, output_dir):
        output_dir.mkdir(parents=True)
        config_text = config_path.read_text(encoding="utf-8")
        hash_value = "high" if "turnover_penalty: 40.0" in config_text else "low"
        (output_dir / "v4_replay_manifest.json").write_text(f'{{"weights_panel_hash":"{hash_value}","config_hash":"fixed"}}', encoding="utf-8")
        return type("Manifest", (), {"weights_panel_hash": hash_value, "config_hash": "fixed"})()

    def fake_gates(v3_cache_dir, replay_dir):
        return [_Obj("G-REQ-F-001-tail-turnover", "FAIL", 0.5), _Obj("G-Preserve-HighVol-Sharpe", "FAIL", 1.0), _Obj("G-Preserve-2022-Sharpe", "PARTIAL", 1.0), _Obj("G-REQ-F-002-sector-p95", "PASS", 0.1)]

    monkeypatch.setattr("scripts.run_adr0002_grid.replay_v4_full_sample", fake_replay)
    monkeypatch.setattr("scripts.run_adr0002_grid.evaluate_v4_acceptance_gates", fake_gates)

    first = run_adr0002_grid(_pre_registration_path(), tmp_path / "v3", tmp_path / "a", max_minutes_per_point=1.0)
    second = run_adr0002_grid(_pre_registration_path(), tmp_path / "v3", tmp_path / "b", max_minutes_per_point=1.0)

    assert first.decision == second.decision == "ESCALATE-B"
    assert [p["classification"] for p in first.points] == [p["classification"] for p in second.points]


def test_adr0002_runner_exposes_no_threshold_override_argument() -> None:
    import inspect

    signature = inspect.signature(run_adr0002_grid)

    assert "threshold" not in signature.parameters
    assert "gate_thresholds" not in signature.parameters


def test_adr0002_sanity_probe_detects_dead_wiring(tmp_path, monkeypatch) -> None:
    def fake_replay(v3_cache_dir, config_path, output_dir):
        output_dir.mkdir(parents=True)
        (output_dir / "v4_replay_manifest.json").write_text('{"weights_panel_hash":"fixed","config_hash":"fixed"}', encoding="utf-8")
        return type("Manifest", (), {"weights_panel_hash": "fixed", "config_hash": "fixed"})()

    def fake_gates(v3_cache_dir, replay_dir):
        return [_Obj("G-REQ-F-001-tail-turnover", "FAIL", 0.5), _Obj("G-Preserve-HighVol-Sharpe", "FAIL", 1.0), _Obj("G-Preserve-2022-Sharpe", "PARTIAL", 1.0)]

    monkeypatch.setattr("scripts.run_adr0002_grid.replay_v4_full_sample", fake_replay)
    monkeypatch.setattr("scripts.run_adr0002_grid.evaluate_v4_acceptance_gates", fake_gates)

    probe = run_sanity_probe(parse_pre_registered_grid(_pre_registration_path()), tmp_path / "v3", tmp_path / "out", max_minutes_per_point=1.0)

    assert probe["pass_fail"] is False
    assert probe["reason"] == "DEAD_WIRING"


def test_adr0002_decision_report_writes_grid_evidence(tmp_path) -> None:
    manifest = {
        "decision": "ESCALATE-B",
        "points": [
            {
                "point_id": "point_00",
                "params": {"turnover_penalty": 4.0, "no_trade_band_bps": 100.0, "lambda_beta": 10.0, "sector_net_cap": 0.1},
                "classification": "REJECTED",
                "gate_observed": {
                    "G-REQ-F-001-tail-turnover": 0.5,
                    "G-Preserve-HighVol-Sharpe": 1.0,
                    "G-Preserve-2022-Sharpe": 1.0,
                },
            }
        ],
    }
    path = tmp_path / "adr0002_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    report = generate_adr0002_decision_report(path, tmp_path / "report.md")

    text = report.read_text(encoding="utf-8")
    assert "Decision: **ESCALATE-B**" in text
    assert "point_00" in text


def _pre_registration_path():
    from pathlib import Path

    return Path("docs/adr/ADR-0002-turnover-optimizer-reparam.md")


def _gate(gate_id: str, status: str):
    return {"gate_id": gate_id, "status": status, "observed_value": 1.0}


class _Obj:
    def __init__(self, gate_id: str, status: str, observed_value: float):
        self.gate_id = gate_id
        self.req_id = "REQ-F-001"
        self.metric_name = "metric"
        self.observed_value = observed_value
        self.threshold = 1.0
        self.comparator = ">="
        self.status = status
        self.evidence_path = "evidence"
