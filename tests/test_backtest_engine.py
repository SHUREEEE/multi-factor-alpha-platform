from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import VectorizedBacktester


def test_pnl_sums_to_nav() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5)
    target_weights = pd.DataFrame({"A": [0.0, 1.0, 1.0, 0.0, 0.0]}, index=dates)
    prices = pd.DataFrame({"A": [100.0, 101.0, 103.0, 102.0, 104.0]}, index=dates)

    result = VectorizedBacktester(
        target_weights=target_weights,
        prices=prices,
        cost_config={"linear_bps": 0.0, "impact_coefficient": 0.0},
    ).run()

    assert result.nav.iloc[-1] == pytest.approx((1.0 + result.pnl).prod())


def test_engine_uses_adj_close_long_form() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    target_weights = pd.DataFrame({"A": [0.0, 1.0, 1.0]}, index=dates)
    prices = pd.DataFrame(
        {
            "date": np.repeat(dates, 1),
            "ticker": ["A", "A", "A"],
            "close": [999.0, 1.0, 999.0],
            "adj_close": [100.0, 110.0, 121.0],
        }
    )

    result = VectorizedBacktester(
        target_weights=target_weights,
        prices=prices,
        cost_config={"linear_bps": 0.0, "impact_coefficient": 0.0},
    ).run()

    assert result.pnl.iloc[-1] == pytest.approx(0.10)


def test_engine_trades_include_cost_column() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    target_weights = pd.DataFrame({"A": [0.0, 0.5, 0.0]}, index=dates)
    prices = pd.DataFrame({"A": [100.0, 101.0, 102.0]}, index=dates)

    result = VectorizedBacktester(
        target_weights=target_weights,
        prices=prices,
        cost_config={"linear_bps": 10.0, "impact_coefficient": 0.0},
    ).run()

    assert {"date", "symbol", "dw", "cost"}.issubset(result.trades.columns)
    assert result.daily_cost.sum() == pytest.approx(result.trades["cost"].sum())
