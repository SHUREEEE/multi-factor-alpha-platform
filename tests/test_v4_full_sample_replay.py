"""Tests for E1 V4 full-sample replay driver."""

from __future__ import annotations

import json

import pandas as pd

from scripts.run_v4_full_sample_replay import replay_v4_full_sample
from src.portfolio.v4.acceptance_gates import evaluate_v4_acceptance_gates


def test_replay_tiny_universe_produces_all_panels(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path)

    replay_v4_full_sample(cache, tmp_path / "config.json", tmp_path / "out")

    assert (tmp_path / "out" / "v4_weights_panel.parquet").exists()
    assert (tmp_path / "out" / "v4_returns_panel.parquet").exists()
    assert (tmp_path / "out" / "v4_diagnostics_panel.parquet").exists()
    assert (tmp_path / "out" / "v4_replay_manifest.json").exists()
    assert (tmp_path / "out" / "v4_pit_audit_log.parquet").exists()


def test_replay_is_deterministic_for_weights_panel_hash(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path)

    first = replay_v4_full_sample(cache, tmp_path / "config.json", tmp_path / "a")
    second = replay_v4_full_sample(cache, tmp_path / "config.json", tmp_path / "b")

    assert first.weights_panel_hash == second.weights_panel_hash


def test_replay_prior_weights_chain_reduces_second_day_turnover(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path)

    replay_v4_full_sample(cache, tmp_path / "config.json", tmp_path / "out")
    diagnostics = pd.read_parquet(tmp_path / "out" / "v4_diagnostics_panel.parquet")

    assert diagnostics["turnover"].iloc[1] < 4.0


def test_replay_pit_log_records_fail_and_continues(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path)
    (cache / "pit_fail_dates.json").write_text('["2024-01-05"]', encoding="utf-8")

    replay_v4_full_sample(cache, tmp_path / "config.json", tmp_path / "out")
    pit = pd.read_parquet(tmp_path / "out" / "v4_pit_audit_log.parquet")

    assert "FAIL" in set(pit["pit_status"])
    assert (tmp_path / "out" / "v4_weights_panel.parquet").exists()


def test_replay_manifest_marks_synthetic_borrow(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path)

    replay_v4_full_sample(cache, tmp_path / "config.json", tmp_path / "out")
    manifest = json.loads((tmp_path / "out" / "v4_replay_manifest.json").read_text(encoding="utf-8"))

    assert manifest["borrow_source"] == "synthetic"


def test_replay_config_wiring_changes_weights_hash(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path, alternating_weights=True)
    base_config = tmp_path / "base.yaml"
    tuned_config = tmp_path / "tuned.yaml"
    base_config.write_text("turnover_penalty: 4.0\nno_trade_band_bps: 100.0\nlambda_beta: 10.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    tuned_config.write_text("turnover_penalty: 40.0\nno_trade_band_bps: 300.0\nlambda_beta: 5.0\nsector_net_cap: 0.10\n", encoding="utf-8")

    base = replay_v4_full_sample(cache, base_config, tmp_path / "base")
    tuned = replay_v4_full_sample(cache, tuned_config, tmp_path / "tuned")

    assert base.weights_panel_hash != tuned.weights_panel_hash
    assert base.replay_config["turnover_penalty"] == 4.0
    assert tuned.replay_config["turnover_penalty"] == 40.0


def test_protected_regime_alpha_improves_preservation_gates(tmp_path) -> None:
    cache = _tiny_v3_cache(tmp_path, regime_returns=True)
    base_config = tmp_path / "base.yaml"
    protected_config = tmp_path / "protected.yaml"
    base_config.write_text("turnover_penalty: 4.0\nno_trade_band_bps: 100.0\nlambda_beta: 10.0\nsector_net_cap: 0.10\nprotected_regime_alpha_bps: 0.0\n", encoding="utf-8")
    protected_config.write_text("turnover_penalty: 4.0\nno_trade_band_bps: 100.0\nlambda_beta: 10.0\nsector_net_cap: 0.10\nprotected_regime_alpha_bps: 1.0\n", encoding="utf-8")

    replay_v4_full_sample(cache, base_config, tmp_path / "base")
    replay_v4_full_sample(cache, protected_config, tmp_path / "protected")
    base = {gate.gate_id: gate.observed_value for gate in evaluate_v4_acceptance_gates(cache, tmp_path / "base")}
    protected = {gate.gate_id: gate.observed_value for gate in evaluate_v4_acceptance_gates(cache, tmp_path / "protected")}

    assert protected["G-Preserve-HighVol-Sharpe"] > base["G-Preserve-HighVol-Sharpe"]
    assert protected["G-Preserve-2022-Sharpe"] > base["G-Preserve-2022-Sharpe"]


def _tiny_v3_cache(tmp_path, *, alternating_weights: bool = False, regime_returns: bool = False):
    cache = tmp_path / "cache"
    cache.mkdir()
    dates = pd.bdate_range("2024-01-02", periods=20, name="date")
    if alternating_weights:
        weights = pd.DataFrame(
            {
                "AAA": [0.7 if idx % 2 == 0 else 0.3 for idx in range(len(dates))],
                "BBB": [0.3 if idx % 2 == 0 else 0.7 for idx in range(len(dates))],
                "CCC": [-0.7 if idx % 2 == 0 else -0.3 for idx in range(len(dates))],
                "DDD": [-0.3 if idx % 2 == 0 else -0.7 for idx in range(len(dates))],
            },
            index=dates,
        )
    else:
        weights = pd.DataFrame({"AAA": 0.5, "BBB": -0.5}, index=dates)
    if regime_returns:
        dates = pd.bdate_range("2022-01-03", periods=260, name="date")
        weights = pd.DataFrame({"AAA": 0.5, "BBB": -0.5}, index=dates)
        low_vol = [0.001, -0.001, 0.0015, -0.0005] * 50
        high_vol = [0.010, -0.008, 0.012, -0.009] * 15
        returns_values = low_vol + high_vol
        returns = pd.DataFrame({"long_short_return": returns_values}, index=dates)
    else:
        returns = pd.DataFrame({"long_short_return": [0.001, -0.001] * 10}, index=dates)
    weights.to_parquet(cache / "v3_weights.parquet")
    returns.to_parquet(cache / "v3_daily_returns.parquet")
    return cache
