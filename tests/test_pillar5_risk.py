"""Unit tests for Pillar 5 risk sizing helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.risk import drawdown_events, drawdown_series, scale_return_stream, slice_returns_window


def test_vol_scaling_scales_return_and_cost_linearly() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2, name="date")
    daily = pd.DataFrame({"long_short_return": [0.01, -0.02], "turnover": [0.5, 1.0]}, index=dates)
    scaled = scale_return_stream(daily, leverage_scaler=0.5, cost_bps=10)
    assert scaled["gross_return"].iloc[0] == pytest.approx(0.005)
    assert scaled["turnover"].iloc[1] == pytest.approx(0.5)
    assert scaled["transaction_cost"].iloc[1] == pytest.approx(0.0005)
    assert scaled["net_return"].iloc[1] == pytest.approx(-0.0105)


def test_drawdown_series_and_events_are_correct() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5, name="date")
    returns = pd.Series([0.10, -0.10, -0.10, 0.30, -0.05], index=dates)
    drawdowns = drawdown_series(returns)
    assert drawdowns.iloc[0] == pytest.approx(0.0)
    assert drawdowns.iloc[2] == pytest.approx(-0.19)
    events = drawdown_events(returns)
    first = events.sort_values("peak_to_trough").iloc[0]
    assert first["start_date"] == dates[0]
    assert first["trough_date"] == dates[2]
    assert first["recovery_date"] == dates[3]
    assert first["peak_to_trough"] == pytest.approx(-0.19)


def test_stress_window_slicing_is_inclusive() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5, name="date")
    returns = pd.Series(range(5), index=dates, dtype=float)
    window = slice_returns_window(returns, "2024-01-02", "2024-01-04")
    assert list(window.index) == list(dates[1:4])
    assert window.tolist() == [1.0, 2.0, 3.0]
