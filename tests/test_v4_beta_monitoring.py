"""Tests for V4 residual beta monitoring.

Covers: REQ-F-004, REQ-F-005.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio.v4.beta_monitoring import BetaMonitorResult
from src.portfolio.v4.beta_monitoring import compute_realized_beta_monitor_20d, compute_realized_beta_monitor_60d
from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights


def test_20d_beta_monitor_warns_and_hard_reviews_after_three_days() -> None:
    dates = pd.bdate_range("2024-01-02", periods=25, name="date")
    market = _alternating_market(dates)
    portfolio = market * 0.6

    result = compute_realized_beta_monitor_20d(portfolio, market)

    assert result.beta.dropna().iloc[-1] == pytest.approx(0.6)
    assert result.warning_flag.iloc[19]
    assert not result.hard_review_flag.iloc[20]
    assert result.hard_review_flag.iloc[21]


def test_20d_beta_monitor_stays_clear_for_low_beta() -> None:
    dates = pd.bdate_range("2024-01-02", periods=25, name="date")
    market = _alternating_market(dates)
    portfolio = market * 0.1

    result = compute_realized_beta_monitor_20d(portfolio, market)

    assert not result.warning_flag.any()
    assert not result.hard_review_flag.any()


def test_60d_beta_monitor_hard_review_requires_five_days() -> None:
    dates = pd.bdate_range("2024-01-02", periods=66, name="date")
    market = _alternating_market(dates)
    portfolio = market * 0.45

    result = compute_realized_beta_monitor_60d(portfolio, market)

    assert result.warning_flag.iloc[59]
    assert not result.hard_review_flag.iloc[62]
    assert result.hard_review_flag.iloc[63]


def test_60d_consecutive_counter_resets_before_hard_review() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70, name="date")
    market = _alternating_market(dates)
    beta_path = pd.Series(0.0, index=dates)
    beta_path.iloc[40:46] = 0.6
    beta_path.iloc[46:55] = 0.0
    beta_path.iloc[55:61] = 0.6
    portfolio = market * beta_path

    result = compute_realized_beta_monitor_60d(
        portfolio,
        market,
        window=5,
        min_obs=5,
        hard_review_threshold=0.40,
        hard_review_consecutive_days=5,
    )

    assert not result.hard_review_flag.iloc[40:63].any()
    assert result.consecutive_breach_count.iloc[52] == 0


def test_20d_monitor_catches_fast_event_that_60d_monitor_does_not() -> None:
    dates = pd.bdate_range("2024-01-02", periods=75, name="date")
    market = _alternating_market(dates)
    portfolio = market * 0.0
    portfolio.iloc[45:] = market.iloc[45:] * 0.7

    beta20 = compute_realized_beta_monitor_20d(portfolio, market)
    beta60 = compute_realized_beta_monitor_60d(portfolio, market)

    assert beta20.hard_review_flag.iloc[-1]
    assert not beta60.hard_review_flag.iloc[-1]


def test_beta_monitor_index_mismatch_raises() -> None:
    portfolio = pd.Series([0.1, 0.2], index=pd.bdate_range("2024-01-02", periods=2))
    market = pd.Series([0.1, 0.2], index=pd.bdate_range("2024-01-03", periods=2))

    with pytest.raises(ValueError):
        compute_realized_beta_monitor_20d(portfolio, market)


def test_beta_monitor_warmup_dates_and_flags() -> None:
    dates = pd.bdate_range("2024-01-02", periods=10, name="date")
    market = _alternating_market(dates)
    portfolio = market * 0.6

    result = compute_realized_beta_monitor_20d(portfolio, market)

    assert result.beta.isna().all()
    assert not result.warning_flag.any()
    assert not result.hard_review_flag.any()
    assert len(result.warmup_dates) == len(dates)


def test_beta_monitor_is_pit_safe_for_prior_dates() -> None:
    dates = pd.bdate_range("2024-01-02", periods=30, name="date")
    market = _alternating_market(dates)
    portfolio = market * 0.4
    changed_market = market.copy()
    changed_market.iloc[-1] = 0.50

    result_a = compute_realized_beta_monitor_20d(portfolio, market)
    result_b = compute_realized_beta_monitor_20d(portfolio, changed_market)

    assert result_a.beta.iloc[-2] == result_b.beta.iloc[-2]


def test_beta_monitor_labels_are_preserved() -> None:
    dates = pd.bdate_range("2024-01-02", periods=65, name="date")
    market = _alternating_market(dates)

    beta20 = compute_realized_beta_monitor_20d(market * 0.1, market, market_proxy_name="RSP")
    beta60 = compute_realized_beta_monitor_60d(market * 0.1, market, market_proxy_name="RSP")

    assert beta20.window_label == "20d"
    assert beta60.window_label == "60d"
    assert beta20.market_proxy_label == "RSP"
    assert beta60.market_proxy_label == "RSP"


def test_beta_monitor_uses_sample_covariance_ddof_one() -> None:
    dates = pd.bdate_range("2024-01-02", periods=25, name="date")
    market = pd.Series(np.linspace(-0.03, 0.04, len(dates)), index=dates)
    portfolio = market * 0.55 + 0.001

    result = compute_realized_beta_monitor_20d(portfolio, market)
    expected = np.cov(portfolio.iloc[-20:], market.iloc[-20:], ddof=1)[0, 1] / np.var(market.iloc[-20:], ddof=1)

    assert result.beta.iloc[-1] == pytest.approx(expected, abs=1e-12)


def test_builder_marks_beta_hard_review_without_blocking_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})

    def fake_beta20(*args, **kwargs) -> BetaMonitorResult:
        return _beta_result(dates, beta=0.6, warning=True, hard=True)

    def fake_beta60(*args, **kwargs) -> BetaMonitorResult:
        return _beta_result(dates, beta=0.1, warning=False, hard=False)

    monkeypatch.setattr("src.portfolio.v4.builder.compute_realized_beta_monitor_20d", fake_beta20)
    monkeypatch.setattr("src.portfolio.v4.builder.compute_realized_beta_monitor_60d", fake_beta60)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        portfolio_returns_history=pd.Series([0.0], index=dates),
        market_returns_for_beta=pd.Series([0.0], index=dates),
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

    assert result.weights.shape == raw.shape
    assert result.manifest["validation_state"] == "BETA_HARD_REVIEW"
    assert result.manifest["beta_20d_hard_review"] is True
    assert result.manifest["beta_60d_hard_review"] is False


def test_builder_without_regime_or_beta_inputs_leaves_manifest_empty() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
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

    assert result.manifest["trend_sizing_multiplier"] is None
    assert result.manifest["beta_20d"] is None
    assert result.manifest["validation_state"] == "PASS"


def _alternating_market(dates: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(([0.01, -0.01] * ((len(dates) // 2) + 1))[: len(dates)], index=dates)


def _beta_result(dates: pd.DatetimeIndex, *, beta: float, warning: bool, hard: bool) -> BetaMonitorResult:
    return BetaMonitorResult(
        beta=pd.Series([beta], index=dates),
        abs_beta=pd.Series([abs(beta)], index=dates),
        warning_flag=pd.Series([warning], index=dates),
        hard_review_flag=pd.Series([hard], index=dates),
        consecutive_breach_count=pd.Series([1 if hard else 0], index=dates),
        window_label="20d",
        market_proxy_label="SPY",
        warmup_dates=[],
    )
