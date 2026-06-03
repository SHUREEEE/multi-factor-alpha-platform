"""Validation contract for point-in-time fundamental panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd


DAILY_FUNDAMENTAL_INDEX_NAMES: tuple[str, str] = ("date", "ticker")
LONG_FUNDAMENTAL_COLUMNS: tuple[str, ...] = ("date", "ticker", "field", "value")
ATTRIBUTION_REQUIRED_COLUMNS: tuple[str, ...] = ("market_cap",)


@dataclass(frozen=True)
class FundamentalsContractReport:
    """Machine-readable validation summary for a fundamentals panel."""

    valid: bool
    row_count: int
    ticker_count: int
    start_date: str | None
    end_date: str | None
    columns: list[str]
    required_columns: list[str]
    missing_columns: list[str]
    market_cap_min_positive_coverage: float | None = None
    market_cap_mean_positive_coverage: float | None = None
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable report."""
        return {
            "valid": self.valid,
            "row_count": self.row_count,
            "ticker_count": self.ticker_count,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "columns": self.columns,
            "required_columns": self.required_columns,
            "missing_columns": self.missing_columns,
            "market_cap_min_positive_coverage": self.market_cap_min_positive_coverage,
            "market_cap_mean_positive_coverage": self.market_cap_mean_positive_coverage,
            "violations": self.violations,
        }

    def raise_for_errors(self) -> None:
        """Raise a ValueError with all validation violations."""
        if self.violations:
            raise ValueError("; ".join(self.violations))


def validate_daily_fundamentals(
    frame: pd.DataFrame,
    *,
    price_index: pd.MultiIndex | None = None,
    required_columns: Iterable[str] = ATTRIBUTION_REQUIRED_COLUMNS,
    min_market_cap_coverage: float = 0.95,
) -> FundamentalsContractReport:
    """Validate the daily PIT fundamentals contract.

    The publishable attribution path requires a daily ``market_cap`` panel with
    high positive coverage over the fitted universe. This function keeps that
    data contract explicit and reusable by ingestion, audit, and attribution
    workflows.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    if not 0.0 <= min_market_cap_coverage <= 1.0:
        raise ValueError("min_market_cap_coverage must be between 0 and 1.")

    required = list(required_columns)
    violations: list[str] = []
    missing_columns = sorted(set(required) - set(frame.columns))
    if missing_columns:
        violations.append(f"Missing required daily fundamental columns: {missing_columns}")

    if not isinstance(frame.index, pd.MultiIndex):
        violations.append("Daily fundamentals must use MultiIndex(date, ticker).")
        index_names: list[str | None] = list(frame.index.names)
    else:
        index_names = list(frame.index.names)
        if index_names != list(DAILY_FUNDAMENTAL_INDEX_NAMES):
            violations.append("Daily fundamentals index names must be ['date', 'ticker'].")
        if not frame.index.is_unique:
            violations.append("Daily fundamentals index must be unique.")
        if price_index is not None and not frame.index.equals(price_index):
            violations.append("Daily fundamentals index must exactly align to processed prices index.")

    if price_index is not None:
        _validate_price_index(price_index)

    start_date, end_date, ticker_count = _index_coverage(frame.index)
    min_coverage: float | None = None
    mean_coverage: float | None = None
    if "market_cap" in frame.columns and isinstance(frame.index, pd.MultiIndex):
        market_cap = pd.to_numeric(frame["market_cap"], errors="coerce").unstack("ticker")
        positive_coverage = market_cap.where(market_cap > 0.0).notna().mean(axis=1)
        clean_coverage = positive_coverage.dropna()
        if not clean_coverage.empty:
            min_coverage = float(clean_coverage.min())
            mean_coverage = float(clean_coverage.mean())
        if clean_coverage.empty or float(clean_coverage.min()) < min_market_cap_coverage:
            observed = "nan" if min_coverage is None or np.isnan(min_coverage) else f"{min_coverage:.2%}"
            violations.append(
                "market_cap positive coverage below contract: "
                f"min_daily_coverage={observed}, required={min_market_cap_coverage:.2%}."
            )

    return FundamentalsContractReport(
        valid=not violations,
        row_count=int(len(frame)),
        ticker_count=ticker_count,
        start_date=start_date,
        end_date=end_date,
        columns=[str(column) for column in frame.columns],
        required_columns=required,
        missing_columns=missing_columns,
        market_cap_min_positive_coverage=min_coverage,
        market_cap_mean_positive_coverage=mean_coverage,
        violations=violations,
    )


def _validate_price_index(price_index: pd.MultiIndex) -> None:
    if not isinstance(price_index, pd.MultiIndex):
        raise TypeError("price_index must be a pandas MultiIndex.")
    if list(price_index.names) != list(DAILY_FUNDAMENTAL_INDEX_NAMES):
        raise ValueError("price_index names must be ['date', 'ticker'].")


def _index_coverage(index: pd.Index) -> tuple[str | None, str | None, int]:
    if not isinstance(index, pd.MultiIndex) or "date" not in index.names or "ticker" not in index.names:
        return None, None, 0
    dates = pd.to_datetime(index.get_level_values("date"), errors="coerce")
    tickers = index.get_level_values("ticker").dropna().astype(str)
    valid_dates = pd.Series(dates).dropna()
    if valid_dates.empty:
        return None, None, int(pd.Index(tickers).nunique())
    return (
        str(valid_dates.min().date()),
        str(valid_dates.max().date()),
        int(pd.Index(tickers).nunique()),
    )
