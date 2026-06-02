"""Unit tests for factor coverage reporting."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.reporting.factor_coverage import summarize_factor_coverage


def test_summarize_factor_coverage_classifies_active_and_empty() -> None:
    index = pd.MultiIndex.from_product(
        [pd.bdate_range("2024-01-02", periods=3), ["AAA", "BBB", "CCC"]],
        names=["date", "ticker"],
    )
    factors = pd.DataFrame(
        {
            "active_factor": np.arange(len(index), dtype=float),
            "empty_factor": np.nan,
        },
        index=index,
    )
    summary = summarize_factor_coverage(factors, min_non_null_ratio=0.2, min_ticker_coverage=2)
    status = dict(zip(summary["factor_name"], summary["status"], strict=True))
    assert status["active_factor"] == "active"
    assert status["empty_factor"] == "inactive_empty"


def test_summarize_factor_coverage_reports_dates_and_tickers() -> None:
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")], ["AAA", "BBB"]],
        names=["date", "ticker"],
    )
    factors = pd.DataFrame({"factor": [np.nan, 1.0, 2.0, np.nan]}, index=index)
    summary = summarize_factor_coverage(factors, min_non_null_ratio=0.2, min_ticker_coverage=2)
    row = summary.iloc[0]
    assert row["unique_ticker_coverage"] == 2
    assert row["first_valid_date"] == "2024-01-02"
    assert row["last_valid_date"] == "2024-01-03"


def test_summarize_factor_coverage_rejects_duplicate_index() -> None:
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2024-01-02"), "AAA"), (pd.Timestamp("2024-01-02"), "AAA")],
        names=["date", "ticker"],
    )
    factors = pd.DataFrame({"factor": [1.0, 2.0]}, index=index)
    with pytest.raises(ValueError, match="duplicate"):
        summarize_factor_coverage(factors)
