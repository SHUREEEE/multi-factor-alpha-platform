from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_attribution import _load_market_caps


def test_load_market_caps_fails_closed_without_valid_panel(tmp_path) -> None:
    path = tmp_path / "fundamentals.parquet"
    pd.DataFrame(columns=["date", "ticker", "field", "value", "available_date"]).to_parquet(path)
    dates = pd.bdate_range("2024-01-02", periods=3, name="date")
    tickers = pd.Index(["A", "B"], name="ticker")

    with pytest.raises(ValueError, match="No usable market_cap panel"):
        _load_market_caps(path, dates, tickers)


def test_load_market_caps_requires_positive_coverage(tmp_path) -> None:
    path = tmp_path / "fundamentals.parquet"
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02")],
            "ticker": ["A", "B"],
            "market_cap": [100.0, float("nan")],
        }
    )
    frame.to_parquet(path)
    dates = pd.bdate_range("2024-01-02", periods=1, name="date")
    tickers = pd.Index(["A", "B"], name="ticker")

    with pytest.raises(ValueError, match="insufficient positive coverage"):
        _load_market_caps(path, dates, tickers)


def test_load_market_caps_allows_explicit_equal_fallback(tmp_path) -> None:
    path = tmp_path / "missing.parquet"
    dates = pd.bdate_range("2024-01-02", periods=3, name="date")
    tickers = pd.Index(["A", "B"], name="ticker")

    market_caps, source = _load_market_caps(path, dates, tickers, allow_equal_fallback=True)

    assert source == "equal-positive fallback (explicit smoke-test override)"
    assert market_caps.shape == (3, 2)
    assert market_caps.eq(1.0).all().all()


def test_load_market_caps_accepts_valid_positive_panel(tmp_path) -> None:
    path = tmp_path / "caps.parquet"
    dates = pd.bdate_range("2024-01-02", periods=2, name="date")
    tickers = pd.Index(["A", "B"], name="ticker")
    panel = pd.DataFrame([[100.0, 200.0], [101.0, 201.0]], index=dates, columns=tickers)
    panel.to_parquet(path)

    market_caps, source = _load_market_caps(path, dates, tickers)

    assert source == "numeric panel"
    pd.testing.assert_frame_equal(market_caps, panel)
