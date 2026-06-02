"""Unit tests for Stage 4.4 implementation-aware portfolio logic."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio.costs import apply_linear_transaction_costs
from src.portfolio.implementation import backtest_rebalanced_deciles, build_liquidity_mask, decompose_turnover


def test_weekly_rebalance_holds_weights_between_refresh_dates() -> None:
    composite, prices = _synthetic_composite_and_prices(n_dates=8, n_tickers=20)
    mask = build_liquidity_mask(prices, "none")
    result = backtest_rebalanced_deciles(composite, prices, "weekly_5d", mask)
    first_weights = result.weights.iloc[1]
    second_weights = result.weights.iloc[2]
    assert first_weights.equals(second_weights)
    assert not result.weights.iloc[5].equals(result.weights.iloc[4])


def test_weekly_rebalance_preserves_one_day_lag() -> None:
    composite, prices = _synthetic_composite_and_prices(n_dates=6, n_tickers=20)
    mask = build_liquidity_mask(prices, "none")
    result = backtest_rebalanced_deciles(composite, prices, "weekly_5d", mask)
    assert pd.isna(result.daily_returns["long_short_return"].iloc[0])
    assert result.daily_returns["long_short_return"].iloc[1:].notna().any()


def test_liquidity_filter_removes_bottom_adv_by_date() -> None:
    _, prices = _synthetic_composite_and_prices(n_dates=25, n_tickers=20)
    mask = build_liquidity_mask(prices, "adv20_filtered")
    usable_counts = mask.sum(axis=1).dropna()
    assert usable_counts.iloc[-1] < 20
    assert usable_counts.iloc[-1] >= 17


def test_turnover_decomposition_consistency() -> None:
    weights = pd.DataFrame(
        {
            "AAA": [0.5, 0.0, 0.5],
            "BBB": [-0.5, -0.5, 0.0],
            "CCC": [0.0, 0.5, -0.5],
        },
        index=pd.bdate_range("2024-01-02", periods=3),
    )
    turnover = decompose_turnover(weights)
    assert turnover["turnover"].iloc[1] == pytest.approx(0.5)
    assert turnover["long_turnover"].iloc[1] >= 0.0
    assert turnover["short_turnover"].iloc[1] >= 0.0
    assert turnover["entry_turnover"].iloc[1] > 0.0
    assert turnover["exit_turnover"].iloc[1] > 0.0


def test_zero_bps_reproduces_gross_for_daily_and_weekly() -> None:
    composite, prices = _synthetic_composite_and_prices(n_dates=8, n_tickers=20)
    mask = build_liquidity_mask(prices, "none")
    for frequency in ["daily", "weekly_5d"]:
        result = backtest_rebalanced_deciles(composite, prices, frequency, mask)
        costed = apply_linear_transaction_costs(result.daily_returns, cost_bps=0)
        assert costed["net_return"].equals(result.daily_returns["long_short_return"])


def _synthetic_composite_and_prices(n_dates: int, n_tickers: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    tickers = [f"T{number:02d}" for number in range(n_tickers)]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    base = np.tile(np.arange(n_tickers, dtype=float), n_dates)
    date_offsets = np.repeat(np.arange(n_dates, dtype=float), n_tickers)
    composite = pd.DataFrame({"composite": base + date_offsets}, index=index)
    prices = pd.DataFrame(
        {
            "adj_close": 10.0 + base,
            "volume": 1_000_000.0 + base * 100_000.0,
            "return_1d": (base / n_tickers) * 0.01,
        },
        index=index,
    )
    return composite, prices
