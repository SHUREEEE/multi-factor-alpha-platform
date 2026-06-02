"""Tests for E1 V4 acceptance gates."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.portfolio.v4.acceptance_gates import GATE_SPECS, evaluate_v4_acceptance_gates


def test_acceptance_gates_all_pass_for_synthetic_panels(tmp_path) -> None:
    replay, v3 = _panels(tmp_path)

    results = evaluate_v4_acceptance_gates(v3, replay)

    assert len(results) == 17
    non_sharpe_results = [
        result
        for result in results
        if result.gate_id
        not in {
            "G-REQ-F-001-2022-shock",
            "G-Preserve-HighVol-Sharpe",
            "G-Preserve-2022-Sharpe",
        }
    ]
    assert all(result.status == "PASS" for result in non_sharpe_results)


def test_acceptance_gate_tail_turnover_fail() -> None:
    from src.portfolio.v4.acceptance_gates import _status

    assert _status(0.50, 0.75, ">=") == "FAIL"


def test_acceptance_gate_sharpe_partial_band() -> None:
    from src.portfolio.v4.acceptance_gates import _status

    assert _status(0.87, 0.90, ">=") == "PARTIAL"


def test_acceptance_gate_sector_fail_band() -> None:
    from src.portfolio.v4.acceptance_gates import _status

    assert _status(0.18, 0.15, "<=") == "FAIL"


def test_acceptance_gate_evidence_paths_point_to_replay(tmp_path) -> None:
    replay, v3 = _panels(tmp_path)

    results = evaluate_v4_acceptance_gates(v3, replay)

    assert all(str(replay) in result.evidence_path for result in results)


def test_acceptance_gate_thresholds_are_design_constants() -> None:
    thresholds = {gate_id: threshold for gate_id, _, _, threshold, _ in GATE_SPECS}

    assert thresholds["G-REQ-F-001-tail-turnover"] == 0.75
    assert thresholds["G-REQ-F-002-sector-p95"] == 0.15
    assert thresholds["G-REQ-F-009-participation"] == 0.05


def test_acceptance_gate_count_is_fixed_to_design() -> None:
    assert len(GATE_SPECS) == 17


def test_acceptance_gate_json_round_trip(tmp_path) -> None:
    replay, v3 = _panels(tmp_path)

    evaluate_v4_acceptance_gates(v3, replay)
    payload = json.loads((tmp_path / "v4_e1_acceptance_gates.json").read_text(encoding="utf-8"))

    assert payload[0]["status"] in {"PASS", "PARTIAL", "FAIL"}
    assert isinstance(payload[0]["observed_value"], float)


def _panels(tmp_path):
    tmp_path = Path(tmp_path)
    replay = tmp_path / "v4_e1_replay"
    v3 = tmp_path / "v3"
    replay.mkdir(parents=True)
    v3.mkdir()
    dates = pd.bdate_range("2022-01-03", periods=260, name="date")
    returns = pd.DataFrame({"daily_return_bps": ([10.0, -5.0] * 130), "gross": 2.0, "long_sum": 1.0, "short_sum": 1.0}, index=dates)
    diagnostics = pd.DataFrame(
        {
            "turnover": 0.1,
            "sector_net_max": 0.10,
            "beta_20d": 0.0,
            "beta_60d": 0.0,
            "drawdown_60d": 0.0,
            "var_95": -0.01,
            "es_95": -0.02,
            "trend_sizing_multiplier": [0.5] + [1.0] * 259,
            "short_top10_share": 0.20,
            "htb_notional_share": 0.0,
            "participation_p95": 0.03,
            "slippage_tail_rotation_residual_bps": 0.0,
        },
        index=dates,
    )
    v3_returns = pd.DataFrame({"long_short_return": returns["daily_return_bps"] / 10000.0}, index=dates)
    returns.to_parquet(replay / "v4_returns_panel.parquet")
    diagnostics.to_parquet(replay / "v4_diagnostics_panel.parquet")
    v3_returns.to_parquet(v3 / "v3_daily_returns.parquet")
    return replay, v3
