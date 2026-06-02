"""Tests for V4 multi-tier drawdown halts.

Covers: REQ-F-008.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.drawdown import evaluate_drawdown_halts


def test_drawdown_soft_halt_at_twelve_percent() -> None:
    returns = _returns_with_tail([-0.04, -0.04, -0.04])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-1])

    assert result.tier == "SOFT"
    assert result.sizing_factor == 0.5


def test_drawdown_hard_halt_blocks_risk_adds() -> None:
    returns = _returns_with_tail([-0.06, -0.06, -0.06])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-1])

    assert result.tier == "HARD"
    assert result.sizing_factor == 0.0
    assert result.risk_adds_blocked


def test_drawdown_single_day_halt_blocks_next_day_orders() -> None:
    returns = _returns_with_tail([-0.09])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-1])

    assert result.tier == "SINGLE_DAY"
    assert result.next_day_order_block


def test_drawdown_single_day_takes_priority_over_soft_and_lists_both_reasons() -> None:
    returns = _returns_with_tail([-0.015, -0.015, -0.09])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-1])

    assert result.tier == "SINGLE_DAY"
    assert "single_day" in result.reason
    assert "soft" in result.reason


def test_drawdown_terminal_takes_priority_over_single_day() -> None:
    returns = _returns_with_tail([-0.16, -0.09])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-1])

    assert result.tier == "TERMINAL"
    assert result.terminal_kill_switch


def test_drawdown_terminal_from_long_history_peak_to_current() -> None:
    dates = pd.bdate_range("2024-01-02", periods=80, name="date")
    returns = pd.Series(0.001, index=dates)
    returns.iloc[20:40] = -0.015
    returns.iloc[40:] = 0.001

    result = evaluate_drawdown_halts(returns, asof_date=dates[-1])

    assert result.peak_to_current_drawdown <= -0.20
    assert result.tier == "TERMINAL"


def test_single_day_clearance_unblocks_next_day_order_but_preserves_tier() -> None:
    returns = _returns_with_tail([-0.09])
    asof = returns.index[-1]

    result = evaluate_drawdown_halts(
        returns,
        asof_date=asof,
        incident_clearance={"single_day_cleared_through": asof + pd.offsets.BDay(1)},
    )

    assert result.tier == "SINGLE_DAY"
    assert not result.next_day_order_block


def test_soft_review_approval_restores_sizing_but_preserves_tier() -> None:
    returns = _returns_with_tail([-0.04, -0.04, -0.04])

    result = evaluate_drawdown_halts(
        returns,
        asof_date=returns.index[-1],
        incident_clearance={"soft_review_approved": True},
    )

    assert result.tier == "SOFT"
    assert result.sizing_factor == 1.0


def test_drawdown_warmup_does_not_raise_or_halt() -> None:
    dates = pd.bdate_range("2024-01-02", periods=30, name="date")
    returns = pd.Series(-0.01, index=dates)

    result = evaluate_drawdown_halts(returns, asof_date=dates[-1])

    assert result.tier == "NONE"
    assert result.sizing_factor == 1.0
    assert result.reason == "INSUFFICIENT_HISTORY"


def test_drawdown_thresholds_are_strict() -> None:
    returns = _returns_with_tail([-0.0799, -0.009, -0.009])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-1])

    assert result.tier == "NONE"


def test_drawdown_terminal_priority_lists_all_subconditions() -> None:
    returns = _returns_with_tail([-0.14, -0.09, -0.05])

    result = evaluate_drawdown_halts(returns, asof_date=returns.index[-2])

    assert result.tier == "TERMINAL"
    assert result.sizing_factor == 0.0
    assert {"terminal", "single_day", "hard"}.issubset(set(result.reason.split(";")))


def test_drawdown_asof_missing_raises_key_error() -> None:
    returns = _returns_with_tail([-0.01])

    with pytest.raises(KeyError):
        evaluate_drawdown_halts(returns, asof_date="2030-01-01")


def test_builder_soft_drawdown_multiplies_trend_sizing(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.portfolio.v4.regime import TrendSizingResult

    dates = pd.bdate_range("2024-01-02", periods=70, name="date")
    raw, sectors = _builder_raw(dates)
    returns = pd.Series(0.0, index=dates)
    returns.iloc[-3:] = [-0.04, -0.04, -0.04]

    def fake_trend(*args, **kwargs) -> TrendSizingResult:
        return TrendSizingResult(
            multiplier=pd.Series(0.5, index=dates),
            trailing_return=pd.Series(0.0, index=dates),
            percentile=pd.Series(0.1, index=dates),
            regime_label=pd.Series("TREND_DOWN", index=dates),
            market_proxy_label="SPY",
            warmup_dates=[],
        )

    monkeypatch.setattr("src.portfolio.v4.builder.compute_trend_sizing_multiplier", fake_trend)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        spy_returns=pd.Series(0.0, index=dates),
        portfolio_returns_history=returns,
    )
    result = build_v4_weights(inputs, _builder_config())

    assert result.manifest["drawdown_tier"] == "SOFT"
    assert result.manifest["final_sizing_factor"] == pytest.approx(0.25)
    assert result.weights.abs().sum(axis=1).iloc[-1] == pytest.approx(0.5, abs=1e-4)


def test_builder_hard_drawdown_zeroes_weights() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70, name="date")
    raw, sectors = _builder_raw(dates)
    returns = pd.Series(0.0, index=dates)
    returns.iloc[-3:] = [-0.06, -0.06, -0.06]

    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        portfolio_returns_history=returns,
    )

    result = build_v4_weights(inputs, _builder_config())

    assert result.manifest["validation_state"] == "HARD_HALT"
    assert result.manifest["final_sizing_factor"] == 0.0
    assert result.weights.iloc[-1].abs().sum() == pytest.approx(0.0)


def test_builder_terminal_drawdown_has_highest_priority() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70, name="date")
    raw, sectors = _builder_raw(dates)
    returns = pd.Series(0.0, index=dates)
    returns.iloc[-2:] = [-0.14, -0.09]

    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        portfolio_returns_history=returns,
    )

    result = build_v4_weights(inputs, _builder_config())

    assert result.manifest["validation_state"] == "TERMINAL_KILL_SWITCH"
    assert result.manifest["terminal_kill_switch"] is True
    assert result.weights.iloc[-1].abs().sum() == pytest.approx(0.0)


def _returns_with_tail(tail: list[float]) -> pd.Series:
    dates = pd.bdate_range("2024-01-02", periods=70, name="date")
    returns = pd.Series(0.0, index=dates)
    returns.iloc[-len(tail) :] = tail
    return returns


def _builder_raw(dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.Series]:
    raw = pd.DataFrame({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    return raw, sectors


def _builder_config() -> V4Config:
    return V4Config(
        sector_net_cap=1.0,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=0.0,
        short_top10_cap=1.0,
        single_short_cap=0.60,
    )
