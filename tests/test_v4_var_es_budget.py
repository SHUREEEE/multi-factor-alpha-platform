"""Tests for V4 VaR and expected-shortfall budget.

Covers: REQ-F-010.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.risk_budget import compute_var_es_budget


def test_var_es_budget_normal_sample_close_to_expected_quantiles() -> None:
    returns = _normal_returns()

    result = compute_var_es_budget(returns, asof_date=returns.index[-1])

    assert result.var[0.95] == pytest.approx(-1.645 * 0.01, rel=0.20)
    assert result.var[0.99] == pytest.approx(-2.326 * 0.01, rel=0.35)


def test_var_es_expected_shortfall_is_more_negative_than_var() -> None:
    returns = _normal_returns()

    result = compute_var_es_budget(returns, asof_date=returns.index[-1])

    assert result.es[0.95] <= result.var[0.95]
    assert result.es[0.99] <= result.var[0.99]


def test_var_budget_breach_when_var_more_negative_than_budget() -> None:
    returns = _normal_returns()

    result = compute_var_es_budget(returns, asof_date=returns.index[-1], var_budget_95=-0.01)

    assert result.breach_flags["var_95"]


def test_var_budget_none_does_not_evaluate_breach() -> None:
    returns = _normal_returns()

    result = compute_var_es_budget(returns, asof_date=returns.index[-1], var_budget_95=None)

    assert not result.breach_flags["var_95"]


def test_var_es_warmup_sets_breach_flags_false() -> None:
    dates = pd.bdate_range("2024-01-02", periods=100, name="date")
    returns = pd.Series(-0.02, index=dates)

    result = compute_var_es_budget(returns, asof_date=dates[-1], min_obs=252, var_budget_95=-0.01, es_budget_95=-0.01)

    assert result.warmup
    assert not any(result.breach_flags.values())


def test_var_es_realized_return_matches_asof_return() -> None:
    returns = _normal_returns()

    result = compute_var_es_budget(returns, asof_date=returns.index[-1])

    assert result.realized_return == pytest.approx(float(returns.iloc[-1]))


def test_var_es_extreme_small_sample_uses_var_as_es_when_tail_singleton() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5, name="date")
    returns = pd.Series([0.01, 0.02, -0.03, 0.01, 0.00], index=dates)

    result = compute_var_es_budget(returns, asof_date=dates[-1], window=5, min_obs=5)

    assert result.es[0.95] == result.var[0.95]


def test_var_es_supports_extra_confidence_levels() -> None:
    returns = _normal_returns()

    result = compute_var_es_budget(returns, asof_date=returns.index[-1], confidence_levels=(0.95, 0.99, 0.995))

    assert set(result.var) == {0.95, 0.99, 0.995}
    assert set(result.es) == {0.95, 0.99, 0.995}


def test_builder_var_breach_updates_validation_without_halting() -> None:
    dates = pd.bdate_range("2024-01-02", periods=252, name="date")
    raw = pd.DataFrame({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0.0005, 0.003, len(dates)), index=dates)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        portfolio_returns_history=returns,
        var_budgets={"var_95": -0.001},
    )
    config = V4Config(
        sector_net_cap=1.0,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=0.0,
        short_top10_cap=1.0,
        single_short_cap=0.60,
    )

    result = build_v4_weights(inputs, config)

    assert result.manifest["validation_state"] == "VAR_BREACH"
    assert result.manifest["var_95_breach"] is True
    assert result.weights.iloc[-1].abs().sum() > 0.0


def _normal_returns() -> pd.Series:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2024-01-02", periods=252, name="date")
    return pd.Series(rng.normal(0.0, 0.01, len(dates)), index=dates)
