"""Unit tests for Stage 4.5 portfolio neutralization tools."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_pillar4_stage45_neutralization import _ex2020_summary
from src.portfolio.implementation import backtest_from_weights
from src.portfolio.neutralization import (
    apply_sector_cap,
    beta_neutralize_weights,
    build_out_of_portfolio_market_proxy,
    compute_rolling_betas,
    portfolio_ex_ante_beta,
    sector_cap_then_renormalize_beta,
)


def test_out_of_portfolio_market_proxy_aligns_daily_returns() -> None:
    prices, weights = _synthetic_prices_and_weights()
    proxy = build_out_of_portfolio_market_proxy(prices, weights)
    assert proxy.index.equals(weights.index)
    assert proxy.notna().all()


def test_rolling_beta_respects_lookback_and_lag() -> None:
    prices, weights = _synthetic_prices_and_weights(n_dates=8)
    proxy = build_out_of_portfolio_market_proxy(prices, weights)
    betas = compute_rolling_betas(prices, proxy, lookback=3)
    assert betas.iloc[:3].isna().all().all()
    assert betas.iloc[4].notna().any()


def test_beta_neutralization_preserves_notional_and_reduces_beta() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    weights = pd.DataFrame({"AAA": [0.5] * 3, "BBB": [0.5] * 3, "CCC": [-0.5] * 3, "DDD": [-0.5] * 3}, index=dates)
    betas = pd.DataFrame({"AAA": [1.2] * 3, "BBB": [0.8] * 3, "CCC": [0.7] * 3, "DDD": [1.3] * 3}, index=dates)
    neutral = beta_neutralize_weights(weights, betas)
    ex_ante_beta = portfolio_ex_ante_beta(neutral, betas).dropna()
    assert ex_ante_beta.abs().max() < 1e-10
    assert neutral.where(neutral > 0.0, 0.0).sum(axis=1).dropna().iloc[-1] == pytest.approx(1.0)
    assert -neutral.where(neutral < 0.0, 0.0).sum(axis=1).dropna().iloc[-1] == pytest.approx(1.0)
    assert neutral.abs().sum(axis=1).dropna().max() == pytest.approx(2.0)


def test_sector_cap_enforced_per_date_per_side() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    weights = pd.DataFrame({"AAA": [0.7, 0.7], "BBB": [0.3, 0.3], "CCC": [-0.8, -0.8], "DDD": [-0.2, -0.2]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    capped = apply_sector_cap(weights, sectors, cap=0.6)
    long_tech = capped[["AAA"]].sum(axis=1)
    short_tech = -capped[["CCC"]].sum(axis=1)
    assert long_tech.max() <= 0.6 + 1e-12
    assert short_tech.max() <= 0.6 + 1e-12


def test_sector_cap_then_renormalize_keeps_beta_and_cap() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    weights = pd.DataFrame(
        {"AAA": [0.4, 0.4], "BBB": [0.3, 0.3], "CCC": [0.3, 0.3], "DDD": [-0.5, -0.5], "EEE": [-0.5, -0.5]},
        index=dates,
    )
    betas = pd.DataFrame(
        {"AAA": [0.8, 0.8], "BBB": [1.0, 1.0], "CCC": [1.2, 1.2], "DDD": [0.7, 0.7], "EEE": [1.3, 1.3]},
        index=dates,
    )
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Finance", "DDD": "Tech", "EEE": "Finance"})
    adjusted = sector_cap_then_renormalize_beta(weights, sectors, betas, cap=0.6)
    ex_ante_beta = portfolio_ex_ante_beta(adjusted, betas).abs().dropna()
    assert ex_ante_beta.max() < 0.1
    assert adjusted.abs().sum(axis=1).max() == pytest.approx(2.0)


def test_ex2020_summary_expected_row_counts() -> None:
    yearly = pd.DataFrame(
        {
            "year": [2019, 2020, 2021, 2019, 2020, 2021],
            "variant": ["A", "A", "A", "B", "B", "B"],
            "annual_return": [0.1, 0.5, -0.1, 0.2, 0.6, 0.0],
            "annual_sharpe": [1.0, 3.0, -1.0, 1.5, 4.0, 0.1],
        }
    )
    summary = _ex2020_summary(yearly)
    assert summary.shape[0] == 2
    assert summary["n_years_ex2020"].tolist() == [2, 2]


def test_zero_bps_reproduces_gross_for_neutralized_variant() -> None:
    prices, weights = _synthetic_prices_and_weights()
    proxy = build_out_of_portfolio_market_proxy(prices, weights)
    betas = compute_rolling_betas(prices, proxy, lookback=3).reindex(index=weights.index, columns=weights.columns)
    neutral = beta_neutralize_weights(weights, betas)
    result = backtest_from_weights(neutral, prices)
    from src.portfolio.costs import apply_linear_transaction_costs

    costed = apply_linear_transaction_costs(result.daily_returns, cost_bps=0)
    assert costed["net_return"].equals(result.daily_returns["long_short_return"])


def _synthetic_prices_and_weights(n_dates: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    repeated = np.tile(np.arange(len(tickers), dtype=float), n_dates)
    date_effect = np.repeat(np.arange(n_dates, dtype=float), len(tickers))
    prices = pd.DataFrame(
        {
            "return_1d": 0.001 + repeated * 0.001 + date_effect * 0.0005,
            "adj_close": 10.0 + repeated,
            "volume": 1_000_000.0 + repeated * 100_000.0,
        },
        index=index,
    )
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    weights[["AAA", "BBB"]] = 0.5
    weights[["CCC", "DDD"]] = -0.5
    return prices, weights
