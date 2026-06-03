from __future__ import annotations

import pandas as pd
import pytest

from src.data.fundamentals_contract import validate_daily_fundamentals


def _price_index() -> pd.MultiIndex:
    return pd.MultiIndex.from_product(
        [pd.bdate_range("2024-01-02", periods=2), ["AAA", "BBB"]],
        names=["date", "ticker"],
    )


def test_validate_daily_fundamentals_accepts_valid_market_cap_panel() -> None:
    index = _price_index()
    frame = pd.DataFrame(
        {
            "market_cap": [100.0, 200.0, 101.0, 201.0],
            "book_value": [50.0, 80.0, 50.0, 80.0],
        },
        index=index,
    )

    report = validate_daily_fundamentals(frame, price_index=index)

    assert report.valid
    assert report.ticker_count == 2
    assert report.market_cap_min_positive_coverage == pytest.approx(1.0)
    assert report.violations == []


def test_validate_daily_fundamentals_reports_missing_market_cap() -> None:
    index = _price_index()
    frame = pd.DataFrame({"book_value": [50.0, 80.0, 50.0, 80.0]}, index=index)

    report = validate_daily_fundamentals(frame, price_index=index)

    assert not report.valid
    assert report.missing_columns == ["market_cap"]
    assert any("Missing required daily fundamental columns" in item for item in report.violations)
    with pytest.raises(ValueError, match="Missing required daily fundamental columns"):
        report.raise_for_errors()


def test_validate_daily_fundamentals_requires_positive_market_cap_coverage() -> None:
    index = _price_index()
    frame = pd.DataFrame({"market_cap": [100.0, float("nan"), 101.0, 201.0]}, index=index)

    report = validate_daily_fundamentals(frame, price_index=index, min_market_cap_coverage=0.95)

    assert not report.valid
    assert report.market_cap_min_positive_coverage == pytest.approx(0.5)
    assert any("market_cap positive coverage below contract" in item for item in report.violations)


def test_validate_daily_fundamentals_requires_price_index_alignment() -> None:
    index = _price_index()
    shifted_index = pd.MultiIndex.from_product(
        [pd.bdate_range("2024-01-03", periods=2), ["AAA", "BBB"]],
        names=["date", "ticker"],
    )
    frame = pd.DataFrame({"market_cap": [100.0, 200.0, 101.0, 201.0]}, index=shifted_index)

    report = validate_daily_fundamentals(frame, price_index=index)

    assert not report.valid
    assert any("exactly align" in item for item in report.violations)
