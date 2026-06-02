"""Unit tests for Pillar 1 data infrastructure."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.cleaner import apply_pit_lag, clean_prices, compute_returns, make_daily_fundamentals
from src.data.universe import Universe


def test_clean_prices_and_returns_normal_case() -> None:
    raw_prices = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2024-01-02", "2024-01-03"],
            "ticker": ["AAA", "AAA", "BBB", "BBB"],
            "open": [10.0, 11.0, 20.0, 22.0],
            "high": [11.0, 12.0, 21.0, 23.0],
            "low": [9.0, 10.0, 19.0, 21.0],
            "close": [10.0, 12.0, 20.0, 22.0],
            "adj_close": [10.0, 12.0, 20.0, 22.0],
            "volume": [1000, 1100, 2000, 2100],
        }
    )
    cleaned_prices = clean_prices(raw_prices)
    prices_with_returns = compute_returns(cleaned_prices)
    assert prices_with_returns.index.names == ["date", "ticker"]
    assert prices_with_returns.loc[(pd.Timestamp("2024-01-03"), "AAA"), "return_1d"] == pytest.approx(0.2)


def test_clean_prices_removes_bad_rows_edge_case() -> None:
    raw_prices = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "ticker": ["AAA", "AAA"],
            "open": [10.0, 11.0],
            "high": [11.0, 12.0],
            "low": [9.0, 10.0],
            "close": [10.0, 0.0],
            "adj_close": [10.0, -1.0],
            "volume": [1000, 1100],
        }
    )
    cleaned_prices = clean_prices(raw_prices)
    assert cleaned_prices.shape[0] == 1
    assert (cleaned_prices["adj_close"] > 0).all()


def test_clean_prices_missing_column_failure_case() -> None:
    incomplete_prices = pd.DataFrame({"date": ["2024-01-02"], "ticker": ["AAA"]})
    with pytest.raises(ValueError, match="Missing required columns"):
        clean_prices(incomplete_prices)


def test_apply_pit_lag_adds_business_day_delay() -> None:
    fundamentals = pd.DataFrame(
        {
            "date": ["2024-03-29"],
            "ticker": ["AAA"],
            "field": ["net_income"],
            "value": [100.0],
        }
    )
    lagged_fundamentals = apply_pit_lag(fundamentals, lag_days=45)
    assert "available_date" in lagged_fundamentals.columns
    assert lagged_fundamentals.loc[0, "available_date"] > lagged_fundamentals.loc[0, "date"]


def test_make_daily_fundamentals_adds_market_cap_normal_case() -> None:
    raw_prices = pd.DataFrame(
        {
            "date": ["2024-06-03", "2024-06-04"],
            "ticker": ["AAA", "AAA"],
            "open": [10.0, 12.0],
            "high": [11.0, 13.0],
            "low": [9.0, 11.0],
            "close": [10.0, 12.0],
            "adj_close": [10.0, 12.0],
            "volume": [1000, 1200],
        }
    )
    fundamentals = pd.DataFrame(
        {
            "date": ["2024-03-29", "2024-03-29"],
            "ticker": ["AAA", "AAA"],
            "field": ["shares_outstanding", "book_value"],
            "value": [100.0, 500.0],
        }
    )
    prices = compute_returns(clean_prices(raw_prices))
    daily_fundamentals = make_daily_fundamentals(fundamentals, prices, lag_days=45)
    assert daily_fundamentals.loc[(pd.Timestamp("2024-06-03"), "AAA"), "market_cap"] == pytest.approx(1000.0)
    assert daily_fundamentals.loc[(pd.Timestamp("2024-06-04"), "AAA"), "book_value"] == pytest.approx(500.0)


def test_make_daily_fundamentals_without_shares_edge_case() -> None:
    raw_prices = pd.DataFrame(
        {
            "date": ["2024-06-03"],
            "ticker": ["AAA"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.0],
            "adj_close": [10.0],
            "volume": [1000],
        }
    )
    fundamentals = pd.DataFrame({"date": ["2024-03-29"], "ticker": ["AAA"], "field": ["book_value"], "value": [500.0]})
    daily_fundamentals = make_daily_fundamentals(fundamentals, clean_prices(raw_prices), lag_days=45)
    assert "market_cap" in daily_fundamentals.columns
    assert daily_fundamentals["market_cap"].isna().all()


def test_make_daily_fundamentals_missing_adj_close_failure_case() -> None:
    prices = pd.DataFrame(index=pd.MultiIndex.from_tuples([(pd.Timestamp("2024-06-03"), "AAA")], names=["date", "ticker"]))
    fundamentals = pd.DataFrame({"date": ["2024-03-29"], "ticker": ["AAA"], "field": ["book_value"], "value": [500.0]})
    with pytest.raises(ValueError, match="adj_close"):
        make_daily_fundamentals(fundamentals, prices, lag_days=45)


def test_universe_rejects_empty_tickers_failure_case() -> None:
    with pytest.raises(ValueError, match="at least one ticker"):
        Universe.from_tickers([])
