from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.pnl import compute_pnl
from src.risk.attribution import (
    compute_factor_exposure,
    decompose_portfolio_return,
    risk_decomposition,
    summarize_attribution,
)


def _panels() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=5, name="date")
    tickers = ["A", "B", "C"]
    weights = pd.DataFrame(
        [
            [0.50, -0.25, -0.25],
            [0.40, -0.20, -0.20],
            [0.30, -0.10, -0.20],
            [0.20, -0.10, -0.10],
            [0.10, -0.05, -0.05],
        ],
        index=dates,
        columns=tickers,
    )
    exposures = {
        "value": pd.DataFrame(
            [
                [1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
            ],
            index=dates,
            columns=tickers,
        ),
        "momentum": pd.DataFrame(0.0, index=dates, columns=tickers),
    }
    factor_returns = pd.DataFrame({"value": [0.0, 0.01, -0.02, 0.03, 0.01], "momentum": 0.05}, index=dates)
    stock_returns = pd.DataFrame(
        [
            [0.00, 0.00, 0.00],
            [0.02, -0.01, 0.03],
            [-0.01, 0.02, -0.02],
            [0.04, -0.03, 0.01],
            [0.01, 0.01, -0.02],
        ],
        index=dates,
        columns=tickers,
    )
    return weights, exposures, factor_returns, stock_returns


def test_decomposition_sums_to_total() -> None:
    weights, exposures, factor_returns, stock_returns = _panels()
    decomp = decompose_portfolio_return(weights, exposures, factor_returns, stock_returns)
    contribs = decomp.filter(like="_contrib").sum(axis=1) + decomp["pure_alpha"]

    pd.testing.assert_series_equal(contribs, decomp["total"], check_names=False, atol=1e-12)


def test_zero_exposure_zero_factor_contrib() -> None:
    weights, exposures, factor_returns, _ = _panels()
    portfolio_exposure = compute_factor_exposure(weights.shift(1), exposures)
    assert portfolio_exposure["momentum"].fillna(0.0).eq(0.0).all()

    decomp = decompose_portfolio_return(weights, exposures, factor_returns, _panels()[3])
    assert decomp["momentum_contrib"].fillna(0.0).eq(0.0).all()


def test_pure_alpha_when_no_factor_contrib() -> None:
    weights, exposures, factor_returns, stock_returns = _panels()
    zero_factor_returns = factor_returns * 0.0
    decomp = decompose_portfolio_return(weights, exposures, zero_factor_returns, stock_returns)

    pd.testing.assert_series_equal(decomp["pure_alpha"], decomp["total"], check_names=False)


def test_risk_decomposition_pct_sums_to_one() -> None:
    weights = pd.Series({"A": 0.5, "B": -0.25, "C": -0.25})
    exposures = {
        "value": pd.Series({"A": 1.0, "B": -1.0, "C": 0.0}),
        "momentum": pd.Series({"A": 0.5, "B": 0.5, "C": -1.0}),
    }
    factor_cov = pd.DataFrame({"value": [0.04, 0.01], "momentum": [0.01, 0.09]}, index=["value", "momentum"])
    idio_var = pd.Series({"A": 0.01, "B": 0.02, "C": 0.03})

    result = risk_decomposition(weights, exposures, factor_cov, idio_var)

    assert result["factor_pct"] + result["idio_pct"] == pytest.approx(1.0)
    assert result["total_variance"] == pytest.approx(result["factor_variance"] + result["idiosyncratic_variance"])


def test_attribution_consistency_with_pillar6_pnl() -> None:
    weights, exposures, factor_returns, stock_returns = _panels()
    decomp = decompose_portfolio_return(weights, exposures, factor_returns, stock_returns)
    pillar6_pnl = compute_pnl(weights, stock_returns)

    assert summarize_attribution(decomp)["total_return"] == pytest.approx(float(pillar6_pnl.sum()))
    pd.testing.assert_series_equal(decomp["total"], pillar6_pnl.reindex(decomp.index), check_names=False)


def test_summarize_attribution_handles_net_transaction_costs() -> None:
    weights, exposures, factor_returns, stock_returns = _panels()
    decomp = decompose_portfolio_return(weights, exposures, factor_returns, stock_returns)
    gross_total = decomp["total"].copy()
    gross_pure_alpha = decomp["pure_alpha"].copy()
    cost = pd.Series(-0.001, index=decomp.index, name="transaction_cost")
    decomp["gross_total"] = gross_total
    decomp["gross_pure_alpha"] = gross_pure_alpha
    decomp["transaction_cost"] = cost
    decomp["pure_alpha"] = gross_pure_alpha + cost
    decomp["total"] = gross_total + cost

    summary = summarize_attribution(decomp)

    assert summary["gross_total_return"] == pytest.approx(float(gross_total.sum()))
    assert summary["transaction_cost_total"] == pytest.approx(float(cost.sum()))
    assert summary["pure_alpha_gross_total"] == pytest.approx(float(gross_pure_alpha.sum()))
    assert summary["pure_alpha_total"] == pytest.approx(float((gross_pure_alpha + cost).sum()))
