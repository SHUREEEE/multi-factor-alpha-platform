from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.risk.risk_model import BarraStyleRiskModel


def _synthetic_panels(t: int = 80, n: int = 40) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2024-01-02", periods=t, name="date")
    tickers = [f"S{i:03d}" for i in range(n)]
    x1 = pd.DataFrame(rng.normal(size=(t, n)), index=dates, columns=tickers)
    x2 = pd.DataFrame(rng.normal(size=(t, n)), index=dates, columns=tickers)
    noise = pd.DataFrame(rng.normal(scale=0.02, size=(t, n)), index=dates, columns=tickers)
    returns = 2.0 * x1 + 0.3 * x2 + noise
    market_caps = pd.DataFrame(rng.lognormal(mean=10.0, sigma=0.25, size=(t, n)), index=dates, columns=tickers)
    return returns, {"x1": x1, "x2": x2}, market_caps


def test_fit_shape() -> None:
    returns, exposures, market_caps = _synthetic_panels(t=25, n=35)
    model = BarraStyleRiskModel(["x1", "x2"]).fit(returns, exposures, market_caps)
    assert model.factor_returns_.shape == (25, 2)


def test_factor_return_recovers_known() -> None:
    returns, exposures, market_caps = _synthetic_panels(t=70, n=50)
    model = BarraStyleRiskModel(["x1", "x2"]).fit(returns, exposures, market_caps)
    assert model.factor_returns_["x1"].mean() == pytest.approx(2.0, abs=0.02)


def test_idio_vol_positive() -> None:
    returns, exposures, market_caps = _synthetic_panels(t=70, n=45)
    model = BarraStyleRiskModel(["x1", "x2"]).fit(returns, exposures, market_caps)
    assert (model.idiosyncratic_volatility.dropna() > 0.0).all()


def test_shrinkage_pulls_toward_mean() -> None:
    dates = pd.bdate_range("2024-01-02", periods=80, name="date")
    tickers = [f"S{i:03d}" for i in range(35)]
    model = BarraStyleRiskModel(["x1"])
    residuals = pd.DataFrame(0.05, index=dates, columns=tickers)
    residuals["S000"] = np.r_[np.full(10, 1.0), np.full(70, np.nan)]
    residuals["S001"] = np.resize([1.0, -1.0], 80)
    model.factor_returns_ = pd.DataFrame({"x1": np.zeros(80)}, index=dates)
    model.residuals_ = residuals

    raw_var = residuals.var(ddof=1)
    prior_var = raw_var.mean()
    shrunk_vol = model.idiosyncratic_volatility

    assert abs(shrunk_vol["S000"] ** 2 - prior_var) < abs(raw_var["S000"] - prior_var)
    assert shrunk_vol["S001"] ** 2 == pytest.approx(raw_var["S001"])


def test_industry_dummies_handled() -> None:
    returns, exposures, market_caps = _synthetic_panels(t=15, n=36)
    tickers = returns.columns
    industry = pd.DataFrame(
        {
            "tech": [1.0 if i % 3 == 0 else 0.0 for i in range(len(tickers))],
            "health": [1.0 if i % 3 == 1 else 0.0 for i in range(len(tickers))],
            "finance": [1.0 if i % 3 == 2 else 0.0 for i in range(len(tickers))],
        },
        index=tickers,
    )
    stacked = pd.concat({date: industry for date in returns.index}, names=["date", "ticker"])

    model = BarraStyleRiskModel(["x1", "x2"]).fit(returns, exposures, market_caps, stacked)

    assert model.factor_returns_.shape[0] == 15
    assert {"health", "finance"}.issubset(model.factor_returns_.columns)
