"""Tests for V4 trend-based regime sizing.

Covers: REQ-F-003.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.regime import compute_trend_sizing_multiplier
from src.portfolio.v4.regime import TrendSizingResult


def test_trend_sizing_triggers_on_bottom_quartile_trailing_return() -> None:
    returns = _trend_series(tail_return=-0.02)

    result = compute_trend_sizing_multiplier(
        returns,
        trailing_return_window=5,
        percentile_window=40,
        min_history_days=20,
        bottom_quartile_multiplier=0.5,
    )

    assert result.multiplier.iloc[-1] == 0.5
    assert result.regime_label.iloc[-1] == "TREND_DOWN"


def test_trend_sizing_stays_neutral_on_top_quartile_trailing_return() -> None:
    returns = _trend_series(tail_return=0.02)

    result = compute_trend_sizing_multiplier(
        returns,
        trailing_return_window=5,
        percentile_window=40,
        min_history_days=20,
        bottom_quartile_multiplier=0.5,
    )

    assert result.multiplier.iloc[-1] == 1.0
    assert result.regime_label.iloc[-1] == "NEUTRAL"


def test_trend_sizing_is_pit_safe_for_prior_dates() -> None:
    dates = pd.bdate_range("2022-01-03", periods=90, name="date")
    base = pd.Series(np.linspace(-0.005, 0.005, len(dates)), index=dates)
    changed_tail = base.copy()
    changed_tail.iloc[-1] = -0.50

    result_a = compute_trend_sizing_multiplier(base, trailing_return_window=5, percentile_window=30, min_history_days=20)
    result_b = compute_trend_sizing_multiplier(changed_tail, trailing_return_window=5, percentile_window=30, min_history_days=20)

    assert result_a.multiplier.iloc[-2] == result_b.multiplier.iloc[-2]
    assert result_a.percentile.iloc[-2] == result_b.percentile.iloc[-2]


def test_trend_sizing_warmup_returns_nan_multiplier() -> None:
    returns = pd.Series(0.001, index=pd.bdate_range("2024-01-02", periods=200, name="date"))

    result = compute_trend_sizing_multiplier(returns, min_history_days=252)

    assert result.percentile.isna().all()
    assert result.multiplier.isna().all()
    assert set(result.regime_label.unique()) == {"INSUFFICIENT_HISTORY"}
    assert len(result.warmup_dates) == len(returns)


def test_trend_sizing_ignores_high_volatility_when_trend_percentile_is_high() -> None:
    dates = pd.bdate_range("2022-01-03", periods=100, name="date")
    returns = pd.Series(0.001, index=dates)
    returns.iloc[-5:] = [0.08, -0.07, 0.08, -0.07, 0.12]

    result = compute_trend_sizing_multiplier(
        returns,
        trailing_return_window=5,
        percentile_window=40,
        min_history_days=20,
        bottom_quartile_multiplier=0.5,
    )

    assert result.multiplier.iloc[-1] == 1.0
    assert result.regime_label.iloc[-1] == "NEUTRAL"


def test_trend_sizing_preserves_market_proxy_label() -> None:
    returns = _trend_series(tail_return=-0.02)

    result = compute_trend_sizing_multiplier(
        returns,
        trailing_return_window=5,
        percentile_window=40,
        min_history_days=20,
        market_proxy_name="RSP",
    )

    assert result.market_proxy_label == "RSP"


def test_trend_sizing_degenerate_zero_returns_does_not_raise() -> None:
    returns = pd.Series(0.0, index=pd.bdate_range("2022-01-03", periods=90, name="date"))

    result = compute_trend_sizing_multiplier(returns, trailing_return_window=5, percentile_window=40, min_history_days=20)

    assert result.trailing_return.dropna().abs().max() == pytest.approx(0.0)
    assert result.percentile.dropna().between(0.0, 1.0).all()


def test_builder_applies_trend_sizing_multiplier_without_changing_ratios(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})

    def fake_trend(*args, **kwargs) -> TrendSizingResult:
        return TrendSizingResult(
            multiplier=pd.Series([0.5], index=dates),
            trailing_return=pd.Series([-0.10], index=dates),
            percentile=pd.Series([0.10], index=dates),
            regime_label=pd.Series(["TREND_DOWN"], index=dates),
            market_proxy_label="SPY",
            warmup_dates=[],
        )

    monkeypatch.setattr("src.portfolio.v4.builder.compute_trend_sizing_multiplier", fake_trend)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        spy_returns=pd.Series([0.0], index=dates),
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

    assert result.weights.abs().sum(axis=1).iloc[0] == pytest.approx(1.0, abs=1e-4)
    assert result.manifest["trend_sizing_multiplier"] == 0.5
    assert result.manifest["trend_regime_label"] == "TREND_DOWN"
    assert result.manifest["short_top10_share"] == pytest.approx(1.0)


def _trend_series(*, tail_return: float) -> pd.Series:
    dates = pd.bdate_range("2022-01-03", periods=100, name="date")
    returns = pd.Series(0.001, index=dates)
    returns.iloc[20:90] = np.linspace(-0.004, 0.004, 70)
    returns.iloc[-5:] = tail_return
    return returns
