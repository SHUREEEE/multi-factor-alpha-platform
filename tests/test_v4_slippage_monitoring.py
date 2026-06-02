"""Tests for V4 slippage attribution.

Covers: REQ-F-011.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.slippage import attribute_slippage_vs_model


def test_slippage_modeled_impact_formula_single_name() -> None:
    result = attribute_slippage_vs_model(
        pd.Series({"AAA": 0.10}),
        pd.Series({"AAA": 0.00}),
        pd.Series({"AAA": 10_000_000.0}),
        pd.Series({"AAA": 0.02}),
        pd.Series({"AAA": 12.0}),
        pd.Series({"AAA": "Tech"}),
        aum_usd=10_000_000.0,
        gross=2.0,
        impact_coefficient=0.5,
        rotation_day_tag=True,
    )

    row = result.detail.set_index("symbol").loc["AAA"]
    assert row["order_notional"] == 2_000_000.0
    assert row["participation"] == 0.20
    assert row["modeled_impact_bps"] == pytest.approx(0.5 * 0.02 * (0.20**0.5) * 10000.0)
    assert result.tail_rotation_day_residual_bps == result.total_residual_bps


def test_slippage_residual_signs_follow_realized_minus_modeled() -> None:
    result = attribute_slippage_vs_model(
        pd.Series({"HIGH": 0.10, "LOW": 0.10}),
        pd.Series({"HIGH": 0.00, "LOW": 0.00}),
        pd.Series({"HIGH": 10_000_000.0, "LOW": 10_000_000.0}),
        pd.Series({"HIGH": 0.01, "LOW": 0.01}),
        pd.Series({"HIGH": 50.0, "LOW": 0.5}),
        pd.Series({"HIGH": "Tech", "LOW": "Tech"}),
        aum_usd=1_000_000.0,
        gross=1.0,
        impact_coefficient=0.1,
    )

    by_symbol = result.detail.set_index("symbol")
    assert by_symbol.loc["HIGH", "residual_bps"] > 0.0
    assert by_symbol.loc["LOW", "residual_bps"] < 0.0


def test_slippage_gross_multiplier_scales_modeled_impact_by_sqrt_two() -> None:
    kwargs = {
        "target_weights": pd.Series({"AAA": 0.10}),
        "current_weights": pd.Series({"AAA": 0.00}),
        "adv20_usd": pd.Series({"AAA": 10_000_000.0}),
        "daily_vol": pd.Series({"AAA": 0.02}),
        "realized_slippage_bps": pd.Series({"AAA": 12.0}),
        "sectors": pd.Series({"AAA": "Tech"}),
        "aum_usd": 10_000_000.0,
        "impact_coefficient": 0.5,
    }

    gross1 = attribute_slippage_vs_model(gross=1.0, **kwargs)
    gross2 = attribute_slippage_vs_model(gross=2.0, **kwargs)

    m1 = gross1.detail.set_index("symbol").loc["AAA", "modeled_impact_bps"]
    m2 = gross2.detail.set_index("symbol").loc["AAA", "modeled_impact_bps"]
    assert m2 / m1 == pytest.approx(2**0.5)


def test_slippage_missing_adv_is_excluded_from_totals() -> None:
    result = attribute_slippage_vs_model(
        pd.Series({"AAA": 0.10, "BBB": 0.10}),
        pd.Series({"AAA": 0.00, "BBB": 0.00}),
        pd.Series({"AAA": 10_000_000.0}),
        pd.Series({"AAA": 0.02, "BBB": 0.02}),
        pd.Series({"AAA": 10.0, "BBB": 10.0}),
        pd.Series({"AAA": "Tech", "BBB": "Health"}),
        aum_usd=10_000_000.0,
        gross=1.0,
    )

    assert result.missing_inputs_symbols == ["BBB"]
    assert result.total_modeled_bps == pytest.approx(result.detail.set_index("symbol").loc["AAA", "modeled_impact_bps"])


def test_slippage_sector_aggregation_is_notional_weighted() -> None:
    result = attribute_slippage_vs_model(
        pd.Series({"A1": 0.20, "A2": 0.10, "B1": 0.10, "B2": 0.10}),
        pd.Series({"A1": 0.00, "A2": 0.00, "B1": 0.00, "B2": 0.00}),
        pd.Series({"A1": 10_000_000.0, "A2": 10_000_000.0, "B1": 10_000_000.0, "B2": 10_000_000.0}),
        pd.Series({"A1": 0.01, "A2": 0.01, "B1": 0.01, "B2": 0.01}),
        pd.Series({"A1": 10.0, "A2": 20.0, "B1": 30.0, "B2": 40.0}),
        pd.Series({"A1": "Tech", "A2": "Tech", "B1": "Health", "B2": "Health"}),
        aum_usd=1_000_000.0,
        gross=1.0,
        impact_coefficient=0.0,
    )

    tech = result.by_sector.set_index("sector").loc["Tech"]
    assert tech["realized_slippage_bps"] == pytest.approx((10.0 * 0.20 + 20.0 * 0.10) / 0.30)


def test_slippage_rotation_day_false_has_no_tail_residual() -> None:
    result = attribute_slippage_vs_model(
        pd.Series({"AAA": 0.10}),
        pd.Series({"AAA": 0.00}),
        pd.Series({"AAA": 10_000_000.0}),
        pd.Series({"AAA": 0.02}),
        pd.Series({"AAA": 12.0}),
        pd.Series({"AAA": "Tech"}),
        aum_usd=10_000_000.0,
        gross=1.0,
        rotation_day_tag=False,
    )

    assert result.tail_rotation_day_residual_bps is None


def test_slippage_all_zero_trade_totals_are_zero() -> None:
    result = attribute_slippage_vs_model(
        pd.Series({"AAA": 0.10}),
        pd.Series({"AAA": 0.10}),
        pd.Series({"AAA": 10_000_000.0}),
        pd.Series({"AAA": 0.02}),
        pd.Series({"AAA": 12.0}),
        pd.Series({"AAA": "Tech"}),
        aum_usd=10_000_000.0,
        gross=1.0,
    )

    assert result.total_modeled_bps == 0.0
    assert result.total_realized_bps == 0.0
    assert result.total_residual_bps == 0.0


def test_builder_slippage_monitor_writes_manifest_without_changing_weights() -> None:
    dates = pd.bdate_range("2024-01-02", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    current = pd.DataFrame({"AAA": [0.0], "BBB": [0.5], "CCC": [-0.5], "DDD": [0.0]}, index=dates)
    adv20 = pd.DataFrame({"AAA": [10_000_000.0], "BBB": [10_000_000.0], "CCC": [10_000_000.0], "DDD": [10_000_000.0]}, index=dates)
    daily_vol = pd.DataFrame({"AAA": [0.02], "BBB": [0.02], "CCC": [0.02], "DDD": [0.02]}, index=dates)
    realized = pd.DataFrame({"AAA": [5.0], "DDD": [5.0]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        current_weights=current,
        adv20_usd=adv20,
        daily_vol=daily_vol,
        realized_slippage_bps=realized,
        rotation_day_tag=True,
    )
    config = V4Config(sector_net_cap=1.0, gross_target=2.0, turnover_penalty=0.0, no_trade_band_bps=0.0, aum_usd=10_000_000.0, short_top10_cap=1.0, single_short_cap=0.60)

    result = build_v4_weights(inputs, config)

    assert "REQ-F-011" in result.manifest["implemented_requirements"]
    assert result.manifest["slippage_tail_rotation_residual_bps"] == result.manifest["slippage_total_residual_bps"]
    assert result.weights.abs().sum(axis=1).iloc[0] > 0.0
