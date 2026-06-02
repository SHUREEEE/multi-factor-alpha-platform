"""Unit tests for Pillar 5.5 attribution helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.attribution import (
    factor_residual_decomposition,
    rolling_realized_beta,
    sector_active_pnl,
    variance_contribution_shares,
)


def test_factor_residual_decomposition_reconciles_to_total() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3, name="date")
    total = pd.Series([0.010, -0.020, 0.005], index=dates)
    components = pd.DataFrame({"market_pnl": [0.004, -0.010, 0.002], "sector_pnl": [0.001, -0.004, 0.001]}, index=dates)
    decomposed = factor_residual_decomposition(total, components)
    reconstructed = decomposed[["market_pnl", "sector_pnl", "residual_alpha_pnl"]].sum(axis=1)
    pd.testing.assert_series_equal(reconstructed, decomposed["total_pnl"], check_names=False)


def test_variance_contribution_shares_sum_to_one_when_components_reconcile() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4, name="date")
    components = pd.DataFrame({"market_pnl": [0.01, -0.01, 0.02, -0.02], "residual_alpha_pnl": [0.00, 0.01, -0.01, 0.00]}, index=dates)
    total = components.sum(axis=1)
    shares = variance_contribution_shares(total, components)
    assert shares.sum() == pytest.approx(1.0)


def test_rolling_realized_beta_matches_known_linear_relation() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5, name="date")
    market = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02], index=dates)
    portfolio = market * 2.0
    beta = rolling_realized_beta(portfolio, market, window=3)
    assert beta.dropna().iloc[-1] == pytest.approx(2.0)


def test_sector_active_pnl_uses_sector_spreads_and_net_exposure() -> None:
    dates = pd.bdate_range("2024-01-02", periods=1, name="date")
    weights = pd.DataFrame({"AAA": [0.5], "BBB": [-0.5]}, index=dates)
    returns = pd.DataFrame({"AAA": [0.03], "BBB": [0.01]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Energy"})
    market = pd.Series([0.02], index=dates)
    pnl = sector_active_pnl(weights, returns, sectors, market)
    assert pnl.loc[dates[0], "sector_pnl__Tech"] == pytest.approx(0.5 * (0.03 - 0.02))
    assert pnl.loc[dates[0], "sector_pnl__Energy"] == pytest.approx(-0.5 * (0.01 - 0.02))

