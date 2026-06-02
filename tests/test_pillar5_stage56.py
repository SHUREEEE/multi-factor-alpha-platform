"""Unit tests for Pillar 5.6 stress/regime helpers."""

from __future__ import annotations

import pandas as pd

from scripts.run_pillar5_stage56_stress_regime import build_regime_indicators, build_regime_split, build_stress_windows


def test_stage56_stress_window_populates_requested_stats() -> None:
    dates = pd.bdate_range("2020-02-19", "2020-03-23", name="date")
    portfolio = pd.Series([0.001] * len(dates), index=dates)
    market = pd.Series([0.002] * len(dates), index=dates)
    stage55 = pd.DataFrame(
        {
            "date": dates,
            "residual_alpha_pnl": [0.0005] * len(dates),
            "rolling_60d_residual_beta": [0.1] * len(dates),
        }
    )
    stress = build_stress_windows(portfolio, market, stage55)
    covid = stress[stress["window"] == "COVID crash"].iloc[0]
    assert int(covid["n_days"]) == len(dates)
    assert covid["hit_rate"] == 1.0
    assert not bool(covid["kill_switch_triggered"])


def test_stage56_regime_split_reports_sample_sizes() -> None:
    dates = pd.bdate_range("2024-01-02", periods=120, name="date")
    market = pd.Series(([0.01, -0.01] * 60), index=dates)
    portfolio = market * 0.5
    regimes = build_regime_indicators(market)
    split = build_regime_split(portfolio, market, regimes)
    assert set(["regime", "n_days", "ann_sharpe", "beta_to_market"]).issubset(split.columns)
    assert split["n_days"].max() > 0
