from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.pnl import compute_costs, compute_metrics, compute_pnl


def test_weights_shift_applied() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    weights = pd.DataFrame({"A": [0.0, 1.0, 0.0]}, index=dates)
    returns = pd.DataFrame({"A": [0.10, 0.20, -0.30]}, index=dates)

    pnl = compute_pnl(weights, returns)

    assert pnl.iloc[0] == pytest.approx(0.0)
    assert pnl.iloc[1] == pytest.approx(0.0)
    assert pnl.iloc[2] == pytest.approx(-0.30)


def test_no_lookahead() -> None:
    dates = pd.bdate_range("2024-01-02", periods=200)
    forward_returns = np.tile([0.01, -0.01], 100)
    weights = pd.DataFrame({"A": np.sign(forward_returns)}, index=dates)
    returns = pd.DataFrame({"A": forward_returns}, index=dates)

    pnl = compute_pnl(weights, returns)
    metrics = compute_metrics(pnl)

    assert metrics["sharpe"] < 1.0


def test_metric_signs() -> None:
    positive = pd.Series([0.01, 0.02, -0.005, 0.01])
    negative = -positive

    assert compute_metrics(positive)["sharpe"] > 0
    assert compute_metrics(negative)["sharpe"] < 0


def test_metric_max_drawdown_nonnegative() -> None:
    metrics = compute_metrics(pd.Series([0.02, -0.10, 0.03]))

    assert metrics["max_drawdown"] >= 0.0


def test_linear_cost_only() -> None:
    trades = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
            "symbol": ["A", "B"],
            "dw": [0.25, -0.75],
        }
    )
    prices = pd.DataFrame({"A": [10.0], "B": [20.0]}, index=pd.to_datetime(["2024-01-02"]))

    costs = compute_costs(trades, {"linear_bps": 10.0, "impact_coefficient": 0.0}, adv=None, prices=prices)

    assert costs.loc[pd.Timestamp("2024-01-02")] == pytest.approx(0.001)


def test_zero_turnover_zero_cost() -> None:
    trades = pd.DataFrame(columns=["date", "symbol", "dw"])
    prices = pd.DataFrame({"A": [10.0, 11.0]}, index=pd.bdate_range("2024-01-02", periods=2))

    costs = compute_costs(trades, {}, adv=None, prices=prices)

    assert costs.sum() == pytest.approx(0.0)


def test_all_metrics_output() -> None:
    metrics = compute_metrics(pd.Series([0.01, -0.005, 0.002, 0.003]))

    assert set(metrics) == {
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "annual_return",
        "annual_vol",
        "hit_rate",
        "avg_win",
        "avg_loss",
        "avg_win_loss_ratio",
        "turnover_annual_x",
    }
