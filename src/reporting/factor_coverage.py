"""Coverage diagnostics for factor panels."""

from __future__ import annotations

import pandas as pd


def summarize_factor_coverage(
    factors: pd.DataFrame,
    min_non_null_ratio: float = 0.20,
    min_ticker_coverage: int = 50,
) -> pd.DataFrame:
    """Summarize missingness and cross-sectional coverage for each factor.

    Parameters
    ----------
    factors:
        Factor panel indexed by ``(date, ticker)`` with one column per factor.
    min_non_null_ratio:
        Minimum panel-wide non-null ratio used to mark a factor as active.
    min_ticker_coverage:
        Minimum number of tickers with at least one valid value.

    Returns
    -------
    pandas.DataFrame
        One row per factor with coverage metrics and activation status.
    """
    _validate_factor_panel(factors)
    rows = [_summarize_one_factor(factors[column], min_non_null_ratio, min_ticker_coverage) for column in factors.columns]
    return pd.DataFrame(rows).sort_values(["status", "factor_name"]).reset_index(drop=True)


def _summarize_one_factor(
    factor: pd.Series,
    min_non_null_ratio: float,
    min_ticker_coverage: int,
) -> dict[str, object]:
    valid_mask = factor.notna()
    valid_factor = factor[valid_mask]
    non_null_ratio = float(valid_mask.mean())
    unique_ticker_coverage = int(valid_factor.index.get_level_values("ticker").nunique()) if not valid_factor.empty else 0
    unique_date_coverage = int(valid_factor.index.get_level_values("date").nunique()) if not valid_factor.empty else 0
    status = _classify_status(non_null_ratio, unique_ticker_coverage, min_non_null_ratio, min_ticker_coverage)
    return {
        "factor_name": str(factor.name),
        "non_null_ratio": non_null_ratio,
        "unique_ticker_coverage": unique_ticker_coverage,
        "unique_date_coverage": unique_date_coverage,
        "first_valid_date": _date_or_empty(valid_factor, "min"),
        "last_valid_date": _date_or_empty(valid_factor, "max"),
        "status": status,
    }


def _classify_status(
    non_null_ratio: float,
    unique_ticker_coverage: int,
    min_non_null_ratio: float,
    min_ticker_coverage: int,
) -> str:
    if non_null_ratio == 0.0:
        return "inactive_empty"
    if non_null_ratio >= min_non_null_ratio and unique_ticker_coverage >= min_ticker_coverage:
        return "active"
    return "thin_coverage"


def _date_or_empty(valid_factor: pd.Series, operation: str) -> str:
    if valid_factor.empty:
        return ""
    dates = valid_factor.index.get_level_values("date")
    value = dates.min() if operation == "min" else dates.max()
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _validate_factor_panel(factors: pd.DataFrame) -> None:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame.")
    if not isinstance(factors.index, pd.MultiIndex):
        raise TypeError("factors must use MultiIndex(date, ticker).")
    if list(factors.index.names) != ["date", "ticker"]:
        raise ValueError("factor index names must be ['date', 'ticker'].")
    if factors.index.has_duplicates:
        raise ValueError("factor panel contains duplicate (date, ticker) rows.")
