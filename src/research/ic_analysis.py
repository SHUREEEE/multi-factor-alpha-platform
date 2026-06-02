"""Information coefficient analysis for single-factor research."""

from __future__ import annotations

from math import sqrt
from typing import Iterable

import numpy as np
import pandas as pd

from src.factors.utils import validate_multiindex_frame


DEFAULT_PERIODS = [1, 5, 21]


def compute_ic(factor_series: pd.Series, return_series: pd.Series, method: str = "spearman") -> float:
    """Compute one cross-sectional information coefficient.

    Parameters
    ----------
    factor_series:
        Factor values for one date, indexed by ticker.
    return_series:
        Forward returns for the same date and tickers.
    method:
        Correlation method, either ``"spearman"`` or ``"pearson"``.

    Returns
    -------
    float
        Cross-sectional correlation after pairwise NaN removal.
    """
    if method not in {"spearman", "pearson"}:
        raise ValueError("method must be either 'spearman' or 'pearson'.")
    if not isinstance(factor_series, pd.Series) or not isinstance(return_series, pd.Series):
        raise TypeError("factor_series and return_series must be pandas Series.")
    paired_data = pd.concat([factor_series, return_series], axis=1, keys=["factor", "return"])
    clean_data = paired_data.replace([np.inf, -np.inf], np.nan).dropna()
    if clean_data.shape[0] < 3:
        return float("nan")
    if method == "spearman":
        clean_data = clean_data.rank(method="average")
    return float(clean_data["factor"].corr(clean_data["return"]))


def compute_ic_timeseries(
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    periods: Iterable[int] = DEFAULT_PERIODS,
    method: str = "spearman",
    already_shifted: bool = True,
) -> pd.DataFrame:
    """Compute daily IC values for multiple forward-return horizons.

    Parameters
    ----------
    factor_df:
        Single-factor panel indexed by ``(date, ticker)``.
    return_df:
        Return panel or price frame containing ``return_1d``.
    periods:
        Forward holding periods in trading days.
    method:
        Correlation method passed to :func:`compute_ic`.
    already_shifted:
        If ``False``, shift factor values by one ticker-specific row before testing.

    Returns
    -------
    pandas.DataFrame
        Date-indexed IC, valid-observation count, and dropped-pair count.
    """
    period_list = _validate_periods(periods)
    factor_series = prepare_factor_series(factor_df, already_shifted=already_shifted)
    result_parts = [_ic_for_period(factor_series, return_df, period, method) for period in period_list]
    return pd.concat(result_parts, axis=1).sort_index()


def summarize_ic(ic_series: pd.Series) -> dict[str, float | dict[str, float]]:
    """Summarize an IC time series.

    Parameters
    ----------
    ic_series:
        Time series of daily IC values.

    Returns
    -------
    dict
        Mean, standard deviation, IR, t-statistic, hit rate, and decay placeholder.
    """
    if not isinstance(ic_series, pd.Series):
        raise TypeError("ic_series must be a pandas Series.")
    clean_ic = ic_series.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    observation_count = int(clean_ic.shape[0])
    mean_ic = float(clean_ic.mean()) if observation_count else float("nan")
    std_ic = float(clean_ic.std(ddof=1)) if observation_count > 1 else float("nan")
    ic_ir = mean_ic / std_ic if std_ic and not np.isnan(std_ic) else float("nan")
    t_stat = mean_ic / (std_ic / sqrt(observation_count)) if observation_count > 1 and std_ic else float("nan")
    hit_rate = float((clean_ic > 0.0).mean()) if observation_count else float("nan")
    return {
        "mean_ic": mean_ic,
        "ic_std": std_ic,
        "ic_ir": float(ic_ir),
        "t_stat": float(t_stat),
        "hit_rate": hit_rate,
        "n_obs": float(observation_count),
        "ic_decay": {str(ic_series.name or "ic"): mean_ic},
    }


def make_forward_returns(return_df: pd.DataFrame | pd.Series, period: int) -> pd.Series:
    """Build cumulative forward returns aligned to signal date ``T``.

    Parameters
    ----------
    return_df:
        Return panel or price frame containing ``return_1d``.
    period:
        Number of future trading days to compound.

    Returns
    -------
    pandas.Series
        MultiIndex series where value at ``T`` uses returns from ``T+1`` onward.
    """
    _validate_period(period)
    daily_returns = extract_daily_return_matrix(return_df)
    gross_forward_returns = pd.DataFrame(1.0, index=daily_returns.index, columns=daily_returns.columns)
    for forward_step in range(1, period + 1):
        gross_forward_returns *= 1.0 + daily_returns.shift(-forward_step)
    forward_returns = gross_forward_returns - 1.0
    return _stack_wide_frame(forward_returns, f"forward_return_{period}d")


def prepare_factor_series(factor_df: pd.DataFrame | pd.Series, already_shifted: bool = True) -> pd.Series:
    """Return one clean factor series, optionally shifted to avoid look-ahead bias."""
    validate_multiindex_frame(factor_df, "factor_df")
    if isinstance(factor_df, pd.DataFrame):
        if factor_df.shape[1] != 1:
            raise ValueError("factor_df must contain exactly one factor column.")
        factor_series = factor_df.iloc[:, 0].astype(float)
    else:
        factor_series = factor_df.astype(float)
    if already_shifted:
        return factor_series.sort_index()
    shifted = factor_series.sort_index().groupby(level="ticker").shift(1)
    return shifted.rename(factor_series.name)


def extract_daily_return_matrix(return_df: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Convert supported return inputs to a date-by-ticker daily-return matrix."""
    if isinstance(return_df, pd.Series):
        validate_multiindex_frame(return_df, "return_df")
        return return_df.astype(float).unstack("ticker").sort_index()
    if not isinstance(return_df, pd.DataFrame):
        raise TypeError("return_df must be a pandas DataFrame or Series.")
    if isinstance(return_df.index, pd.MultiIndex):
        validate_multiindex_frame(return_df, "return_df")
        if "return_1d" not in return_df.columns:
            raise ValueError("return_df must contain return_1d when using MultiIndex input.")
        return return_df["return_1d"].astype(float).unstack("ticker").sort_index()
    return return_df.astype(float).sort_index()


def _ic_for_period(factor_series: pd.Series, return_df: pd.DataFrame | pd.Series, period: int, method: str) -> pd.DataFrame:
    forward_returns = make_forward_returns(return_df, period)
    factor_wide = factor_series.unstack("ticker").sort_index()
    return_wide = forward_returns.unstack("ticker").sort_index()
    factor_wide, return_wide = factor_wide.align(return_wide, join="outer", axis=None)
    if method == "spearman":
        factor_wide = factor_wide.rank(axis=1, method="average")
        return_wide = return_wide.rank(axis=1, method="average")
    ic_values = _rowwise_correlation(factor_wide, return_wide)
    valid_counts = (factor_wide.notna() & return_wide.notna()).sum(axis=1)
    union_counts = (factor_wide.notna() | return_wide.notna()).sum(axis=1)
    output = pd.DataFrame(
        {
            f"ic_{period}d": ic_values.where(valid_counts >= 3),
            f"n_obs_{period}d": valid_counts.astype(int),
            f"n_dropped_{period}d": (union_counts - valid_counts).astype(int),
        }
    )
    output.index.name = "date"
    return output


def _daily_ic_metrics(daily_data: pd.DataFrame, method: str) -> pd.Series:
    factor_values = daily_data["factor"].droplevel("date")
    return_values = daily_data["return"].droplevel("date")
    valid_mask = factor_values.notna() & return_values.notna()
    ic_value = compute_ic(factor_values, return_values, method=method)
    return pd.Series({"ic": ic_value, "n_obs": int(valid_mask.sum()), "n_dropped": int((~valid_mask).sum())})


def _rowwise_correlation(left: pd.DataFrame, right: pd.DataFrame) -> pd.Series:
    valid_mask = left.notna() & right.notna()
    left_clean = left.where(valid_mask)
    right_clean = right.where(valid_mask)
    left_centered = left_clean.sub(left_clean.mean(axis=1), axis=0)
    right_centered = right_clean.sub(right_clean.mean(axis=1), axis=0)
    numerator = (left_centered * right_centered).sum(axis=1, min_count=1)
    left_ss = (left_centered * left_centered).sum(axis=1, min_count=1)
    right_ss = (right_centered * right_centered).sum(axis=1, min_count=1)
    denominator = (left_ss * right_ss).pow(0.5).replace(0.0, np.nan)
    return numerator / denominator


def _stack_wide_frame(wide_frame: pd.DataFrame, name: str) -> pd.Series:
    long_frame = wide_frame.rename_axis(index="date", columns="ticker").reset_index()
    melted = long_frame.melt(id_vars="date", var_name="ticker", value_name=name)
    stacked = melted.set_index(["date", "ticker"])[name].astype(float).sort_index()
    return stacked


def _validate_periods(periods: Iterable[int]) -> list[int]:
    period_list = [int(period) for period in periods]
    if not period_list:
        raise ValueError("periods must contain at least one holding period.")
    for period in period_list:
        _validate_period(period)
    return period_list


def _validate_period(period: int) -> None:
    if not isinstance(period, int) or period <= 0:
        raise ValueError("period must be a positive integer.")
