from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.sanity import perfect_foresight_sharpe, random_alpha_sharpe, reverse_strategy_sharpe


def test_random_alpha_sharpe_near_zero() -> None:
    prices, returns = _synthetic_data()

    result = random_alpha_sharpe(prices, returns, n_trials=20, seed=7)

    assert abs(result["mean_sharpe"]) < 0.3
    assert len(result["trials"]) == 20


def test_perfect_foresight_with_shift_modest() -> None:
    prices, returns = _synthetic_data()

    result = perfect_foresight_sharpe(prices, returns)

    assert abs(result["sharpe_with_shift"]) < 3.0


def test_perfect_foresight_without_shift_high() -> None:
    prices, returns = _synthetic_data()

    result = perfect_foresight_sharpe(prices, returns)

    assert result["sharpe_with_lookahead"] > 5.0


def test_reverse_strategy_flips_sign() -> None:
    prices, returns = _synthetic_data()
    base_weights = returns.shift(1).rank(axis=1, pct=True).sub(0.5).fillna(0.0)
    base_weights = base_weights.div(base_weights.abs().sum(axis=1), axis=0).fillna(0.0)

    result = reverse_strategy_sharpe(prices, returns, base_weights)

    assert result["original_sharpe"] * result["reversed_sharpe"] < 0
    assert abs(result["reversed_sharpe"]) == pytest.approx(abs(result["original_sharpe"]), rel=0.10)


def _synthetic_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(123)
    dates = pd.bdate_range("2024-01-02", periods=50)
    symbols = [f"S{i:02d}" for i in range(20)]
    noise = rng.normal(0.0001, 0.03, size=(50, 20))
    noise = noise - noise.mean(axis=1, keepdims=True)
    returns = pd.DataFrame(noise, index=dates, columns=symbols)
    prices = 100.0 * (1.0 + returns).cumprod()
    return prices, returns
