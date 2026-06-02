"""Tests for V4 participation-cap checks.

Covers: REQ-F-009.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.capacity import check_order_participation


def test_participation_breaches_above_five_percent() -> None:
    result = check_order_participation(
        pd.Series({"AAA": 0.06}),
        pd.Series({"AAA": 0.00}),
        pd.Series({"AAA": 1_000_000.0}),
        aum_usd=1_000_000.0,
        gross=1.0,
    )

    assert result.any_breach
    assert result.breached_symbols == ["AAA"]


def test_participation_all_pass_under_threshold() -> None:
    result = check_order_participation(
        pd.Series({"AAA": 0.04, "BBB": -0.04}),
        pd.Series({"AAA": 0.00, "BBB": 0.00}),
        pd.Series({"AAA": 1_000_000.0, "BBB": 1_000_000.0}),
        aum_usd=1_000_000.0,
        gross=1.0,
    )

    assert not result.any_breach
    assert result.detail["pass_fail"].all()


def test_participation_uses_gross_multiplier_red_line() -> None:
    result = check_order_participation(
        pd.Series({"AAA": 0.05}),
        pd.Series({"AAA": 0.00}),
        pd.Series({"AAA": 100_000.0}),
        aum_usd=1_000_000.0,
        gross=2.0,
    )

    row = result.detail.set_index("symbol").loc["AAA"]
    assert row["order_notional"] == pytest.approx(100_000.0)
    assert row["participation"] == pytest.approx(1.0)
    assert not row["pass_fail"]


def test_participation_missing_adv_fails_symbol() -> None:
    result = check_order_participation(
        pd.Series({"AAA": 0.05}),
        pd.Series({"AAA": 0.00}),
        pd.Series(dtype=float),
        aum_usd=1_000_000.0,
        gross=1.0,
    )

    assert result.missing_adv_symbols == ["AAA"]
    assert not result.detail.set_index("symbol").loc["AAA", "pass_fail"]


def test_participation_new_symbol_entry_is_calculated() -> None:
    result = check_order_participation(
        pd.Series({"NEW": 0.02}),
        pd.Series(dtype=float),
        pd.Series({"NEW": 1_000_000.0}),
        aum_usd=1_000_000.0,
        gross=1.0,
    )

    assert result.detail.set_index("symbol").loc["NEW", "participation"] == pytest.approx(0.02)


def test_participation_summary_excludes_zero_trade_names() -> None:
    result = check_order_participation(
        pd.Series({"AAA": 0.05, "ZERO": 0.10}),
        pd.Series({"AAA": 0.00, "ZERO": 0.10}),
        pd.Series({"AAA": 1_000_000.0, "ZERO": 1_000_000.0}),
        aum_usd=1_000_000.0,
        gross=1.0,
    )

    assert result.p50 == pytest.approx(0.05)
    assert result.p95 == pytest.approx(0.05)
    assert result.max == pytest.approx(0.05)


def test_participation_aligns_union_of_indexes() -> None:
    result = check_order_participation(
        pd.Series({"AAA": 0.01}),
        pd.Series({"BBB": -0.01}),
        pd.Series({"AAA": 1_000_000.0, "BBB": 1_000_000.0, "CCC": 1_000_000.0}),
        aum_usd=1_000_000.0,
        gross=1.0,
    )

    assert set(result.detail["symbol"]) == {"AAA", "BBB", "CCC"}
    assert result.detail.set_index("symbol").loc["CCC", "reason"] == "NO_TRADE"


def test_builder_participation_breach_updates_validation_without_scaling() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        adv20_usd=pd.DataFrame(1_000.0, index=dates, columns=raw.columns),
        current_weights=pd.DataFrame(0.0, index=dates, columns=raw.columns),
        aum_usd=1_000_000.0,
    )
    config = V4Config(
        sector_net_cap=1.0,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=0.0,
        short_top10_cap=1.0,
        single_short_cap=0.60,
        participation_max=0.05,
    )

    result = build_v4_weights(inputs, config)

    assert result.manifest["validation_state"] == "PARTICIPATION_BREACH"
    assert result.manifest["participation_breached_count"] > 0
    assert result.weights.iloc[-1].abs().sum() > 0.0
