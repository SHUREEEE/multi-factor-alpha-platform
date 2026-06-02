"""Quantile portfolio tests for single-factor research."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.ic_analysis import make_forward_returns, prepare_factor_series


TRADING_DAYS_PER_YEAR = 252


def quantile_portfolio_returns(
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    n_quantiles: int = 10,
    already_shifted: bool = True,
) -> pd.DataFrame:
    """Compute equal-weighted forward returns for factor quantile portfolios.

    Parameters
    ----------
    factor_df:
        Single-factor panel indexed by ``(date, ticker)``.
    return_df:
        Daily return panel or price frame containing ``return_1d``.
    n_quantiles:
        Number of cross-sectional buckets.
    already_shifted:
        If ``False``, shift factor values by one day before portfolio sorting.

    Returns
    -------
    pandas.DataFrame
        Date-by-quantile equal-weighted forward returns.
    """
    _validate_n_quantiles(n_quantiles)
    factor_series = prepare_factor_series(factor_df, already_shifted=already_shifted)
    forward_returns = make_forward_returns(return_df, period=1)
    analysis_data = pd.concat([factor_series, forward_returns], axis=1, keys=["factor", "return"])
    quantile_returns = analysis_data.groupby(level="date", sort=True).apply(
        lambda daily: _daily_quantile_returns(daily, n_quantiles)
    )
    quantile_returns.index.name = "date"
    return quantile_returns.sort_index()


def compute_long_short_return(quantile_returns: pd.DataFrame) -> pd.Series:
    """Compute top-minus-bottom quantile returns."""
    _validate_quantile_returns(quantile_returns)
    bottom_column = quantile_returns.columns[0]
    top_column = quantile_returns.columns[-1]
    return (quantile_returns[top_column] - quantile_returns[bottom_column]).rename("long_short")


def compute_monotonicity(quantile_returns: pd.DataFrame) -> float:
    """Measure whether mean returns increase with quantile rank."""
    _validate_quantile_returns(quantile_returns)
    mean_returns = quantile_returns.mean(axis=0, skipna=True).astype(float)
    quantile_ranks = pd.Series(np.arange(1, len(mean_returns) + 1), index=mean_returns.index)
    if mean_returns.dropna().shape[0] < 3:
        return float("nan")
    return float(quantile_ranks.corr(mean_returns, method="spearman"))


def compute_annualized_sharpe(return_series: pd.Series) -> float:
    """Compute annualized Sharpe ratio from daily returns."""
    if not isinstance(return_series, pd.Series):
        raise TypeError("return_series must be a pandas Series.")
    clean_returns = return_series.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if clean_returns.shape[0] < 2:
        return float("nan")
    std_return = clean_returns.std(ddof=1)
    if std_return == 0 or np.isnan(std_return):
        return float("nan")
    return float(clean_returns.mean() / std_return * np.sqrt(TRADING_DAYS_PER_YEAR))


def detect_monotonic_direction(quantile_returns: pd.DataFrame) -> str:
    """Return increasing, decreasing, or none for mean quantile returns."""
    _validate_quantile_returns(quantile_returns)
    mean_returns = quantile_returns.mean(axis=0, skipna=True).dropna()
    if mean_returns.shape[0] < 2:
        return "none"
    differences = mean_returns.diff().dropna()
    if (differences > 0.0).all():
        return "increasing"
    if (differences < 0.0).all():
        return "decreasing"
    return "none"


def _daily_quantile_returns(daily_data: pd.DataFrame, n_quantiles: int) -> pd.Series:
    clean_data = daily_data.replace([np.inf, -np.inf], np.nan).dropna(subset=["factor", "return"])
    output_index = [f"Q{quantile_number}" for quantile_number in range(1, n_quantiles + 1)]
    if clean_data.shape[0] < n_quantiles:
        return pd.Series(np.nan, index=output_index, dtype=float)
    try:
        quantile_labels = pd.qcut(clean_data["factor"].rank(method="first"), q=n_quantiles, labels=output_index)
    except ValueError:
        return pd.Series(np.nan, index=output_index, dtype=float)
    portfolio_returns = clean_data.groupby(quantile_labels, observed=False)["return"].mean()
    return portfolio_returns.reindex(output_index).astype(float)


def _validate_n_quantiles(n_quantiles: int) -> None:
    if not isinstance(n_quantiles, int) or n_quantiles < 2:
        raise ValueError("n_quantiles must be an integer greater than or equal to 2.")


def _validate_quantile_returns(quantile_returns: pd.DataFrame) -> None:
    if not isinstance(quantile_returns, pd.DataFrame):
        raise TypeError("quantile_returns must be a pandas DataFrame.")
    if quantile_returns.shape[1] < 2:
        raise ValueError("quantile_returns must contain at least two quantile columns.")
