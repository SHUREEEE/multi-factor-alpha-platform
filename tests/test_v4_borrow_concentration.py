"""Tests for V4 borrow and short concentration gates.

Covers: REQ-F-006, REQ-F-007.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.borrow import (
    BorrowFeedSchemaError,
    apply_pb_borrow_caps,
    enforce_short_concentration_limits,
)
from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights


def test_short_concentration_clean_book_passes() -> None:
    weights = _diversified_short_book(20, total_short=1.0)
    weights["LONG"] = 1.0

    result = enforce_short_concentration_limits(weights, top10_cap=0.60, single_name_cap=0.10)

    assert result.top10_pass
    assert result.single_name_pass
    assert result.violating_symbols == []


def test_short_concentration_flags_single_short_breach() -> None:
    weights = _diversified_short_book(20, total_short=0.95)
    weights["S00"] = -0.10
    weights["LONG"] = 1.0

    result = enforce_short_concentration_limits(weights, top10_cap=0.70, single_name_cap=0.05)

    assert not result.single_name_pass
    assert "S00" in result.violating_symbols


def test_short_concentration_flags_top10_breach_with_single_names_clean() -> None:
    weights = pd.Series({f"S{i:02d}": -0.05 for i in range(10)} | {f"T{i:02d}": -0.025 for i in range(20)})
    weights["LONG"] = 1.0

    result = enforce_short_concentration_limits(weights, top10_cap=0.45, single_name_cap=0.06)

    assert result.single_name_pass
    assert not result.top10_pass


def test_short_concentration_enforce_single_short_preserves_short_total() -> None:
    weights = _diversified_short_book(30, total_short=0.95)
    weights["S00"] = -0.10
    weights["LONG"] = 1.0
    pre_short = float((-weights[weights < 0.0]).sum())

    result = enforce_short_concentration_limits(weights, top10_cap=0.80, single_name_cap=0.05, mode="enforce")

    assert result.enforced_weights is not None
    assert abs(result.enforced_weights["S00"]) <= 0.05 * pre_short + 1e-12
    assert float((-result.enforced_weights[result.enforced_weights < 0.0]).sum()) == pytest.approx(pre_short, abs=1e-9)


def test_short_concentration_enforce_top10_redistributes_only_to_short_book() -> None:
    weights = pd.Series({f"S{i:02d}": -0.05 for i in range(10)} | {f"T{i:02d}": -0.025 for i in range(20)})
    weights["LONG"] = 1.0

    result = enforce_short_concentration_limits(weights, top10_cap=0.45, single_name_cap=0.06, mode="enforce")

    assert result.enforced_weights is not None
    assert result.top10_share <= 0.45 + 1e-12
    assert result.enforced_weights["LONG"] == pytest.approx(1.0)
    assert all(result.enforced_weights.loc[[f"T{i:02d}" for i in range(20)]] < weights.loc[[f"T{i:02d}" for i in range(20)]])


def test_short_concentration_enforce_impossible_when_no_redistribution_pool() -> None:
    weights = pd.Series({f"S{i:02d}": -0.125 for i in range(8)} | {"LONG": 1.0})

    result = enforce_short_concentration_limits(weights, top10_cap=0.25, single_name_cap=0.20, mode="enforce")

    assert result.enforced_weights is None
    assert not result.top10_pass


def test_pb_borrow_caps_clean_feed_passes() -> None:
    weights = pd.Series({"AAA": -0.10, "BBB": -0.10, "CCC": 0.20})

    result = apply_pb_borrow_caps(
        weights,
        _borrow_feed(["AAA", "BBB"], htb_flags=[False, False]),
        asof_date=pd.Timestamp("2024-01-03"),
        aum_usd=1_000_000,
        gross=2.0,
    )

    assert result.blocked_symbols == []
    assert result.feed_freshness_pass
    assert result.htb_cap_pass


def test_pb_borrow_caps_missing_short_data_blocks_without_substitute() -> None:
    weights = pd.Series({"AAA": -0.10, "MISSING": -0.10, "CCC": 0.20})

    result = apply_pb_borrow_caps(
        weights,
        _borrow_feed(["AAA"], htb_flags=[False]),
        asof_date=pd.Timestamp("2024-01-03"),
        aum_usd=1_000_000,
        gross=2.0,
    )

    assert "MISSING" in result.blocked_symbols
    assert result.enforced_weights["MISSING"] == 0.0


def test_pb_borrow_caps_stale_feed_blocks_symbol() -> None:
    weights = pd.Series({"AAA": -0.10, "BBB": 0.10})
    feed = _borrow_feed(["AAA"], htb_flags=[False])
    feed["feed_timestamp_utc"] = ["2024-01-01T20:00:00Z"]

    result = apply_pb_borrow_caps(
        weights,
        feed,
        asof_date=pd.Timestamp("2024-01-04"),
        aum_usd=1_000_000,
        gross=2.0,
    )

    assert not result.feed_freshness_pass
    assert "AAA" in result.blocked_symbols


def test_pb_borrow_caps_reduces_htb_share_and_redistributes_to_non_htb() -> None:
    weights = pd.Series({"HTB": -0.30, "EASY": -0.70, "LONG": 1.0})

    result = apply_pb_borrow_caps(
        weights,
        _borrow_feed(["HTB", "EASY"], htb_flags=[True, False]),
        asof_date=pd.Timestamp("2024-01-03"),
        htb_notional_cap=0.25,
        aum_usd=1_000_000,
        gross=2.0,
    )

    assert result.htb_cap_pass
    assert abs(result.enforced_weights["HTB"]) / (-result.enforced_weights[result.enforced_weights < 0.0]).sum() <= 0.25 + 1e-12
    assert result.enforced_weights["EASY"] < weights["EASY"]
    assert result.enforced_weights["LONG"] == pytest.approx(1.0)


def test_pb_borrow_caps_htb_fail_when_no_non_htb_pool() -> None:
    weights = pd.Series({"HTB1": -0.30, "HTB2": -0.70, "LONG": 1.0})

    result = apply_pb_borrow_caps(
        weights,
        _borrow_feed(["HTB1", "HTB2"], htb_flags=[True, True]),
        asof_date=pd.Timestamp("2024-01-03"),
        htb_notional_cap=0.25,
        aum_usd=1_000_000,
        gross=2.0,
    )

    assert not result.htb_cap_pass
    assert result.enforced_weights["LONG"] == pytest.approx(1.0)


def test_pb_borrow_caps_binary_locate_mode_blocks_zero_locates() -> None:
    weights = pd.Series({"AAA": -0.10, "BBB": -0.10, "LONG": 0.20})
    feed = _borrow_feed(["AAA", "BBB"], htb_flags=[False, False])
    feed.loc[feed["symbol"] == "BBB", "locate_available_shares"] = 0

    result = apply_pb_borrow_caps(
        weights,
        feed,
        asof_date=pd.Timestamp("2024-01-03"),
        aum_usd=1_000_000,
        gross=2.0,
    )

    assert result.locate_check_mode == "binary"
    assert "BBB" in result.locate_violations
    assert result.enforced_weights["BBB"] == 0.0


def test_pb_borrow_caps_share_locate_mode_caps_to_available_shares() -> None:
    weights = pd.Series({"AAA": -0.20, "LONG": 0.20})
    feed = _borrow_feed(["AAA"], htb_flags=[False])
    feed.loc[0, "locate_available_shares"] = 100.0

    result = apply_pb_borrow_caps(
        weights,
        feed,
        asof_date=pd.Timestamp("2024-01-03"),
        aum_usd=1_000_000,
        gross=2.0,
        prices=pd.Series({"AAA": 50.0}),
    )

    assert result.locate_check_mode == "shares"
    assert "AAA" in result.locate_violations
    assert abs(result.enforced_weights["AAA"]) == pytest.approx(100.0 * 50.0 / (1_000_000 * 2.0))


def test_pb_borrow_caps_schema_missing_htb_flag_raises() -> None:
    feed = _borrow_feed(["AAA"], htb_flags=[False]).drop(columns=["htb_flag"])

    with pytest.raises(BorrowFeedSchemaError):
        apply_pb_borrow_caps(
            pd.Series({"AAA": -0.10, "LONG": 0.10}),
            feed,
            asof_date=pd.Timestamp("2024-01-03"),
            aum_usd=1_000_000,
            gross=2.0,
        )


def test_builder_integrates_borrow_concentration_and_manifest_fields() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    borrow = _borrow_feed(["CCC", "DDD"], htb_flags=[False, False])
    borrow["date"] = dates[0]
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        borrow_feed=borrow,
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

    assert result.manifest["builder_version"] == "v4.0.0-D7"
    assert result.manifest["borrow_feed_present"]
    assert result.manifest["borrow_blocked_symbols_count"] == 0
    assert "REQ-F-006" in set(result.validation_status["requirement"])
    assert "REQ-F-007" in set(result.validation_status["requirement"])


def _diversified_short_book(count: int, *, total_short: float) -> pd.Series:
    return pd.Series({f"S{i:02d}": -total_short / count for i in range(count)})


def _borrow_feed(symbols: list[str], *, htb_flags: list[bool]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-03")] * len(symbols),
            "symbol": symbols,
            "locate_available_shares": [10_000.0] * len(symbols),
            "borrow_rate_bps": [100.0] * len(symbols),
            "utilization_pct": [0.20] * len(symbols),
            "htb_flag": htb_flags,
            "feed_timestamp_utc": ["2024-01-03T20:00:00Z"] * len(symbols),
        }
    )
