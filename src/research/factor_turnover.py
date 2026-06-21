"""Factor turnover diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.ic_analysis import prepare_factor_series


def rank_autocorrelation(factor_df: pd.DataFrame | pd.Series, lag: int = 1, already_shifted: bool = True) -> pd.Series:
    """Compute cross-sectional rank autocorrelation between signal dates."""
    if not isinstance(lag, int) or lag <= 0:
        raise ValueError("lag must be a positive integer.")
    factor = prepare_factor_series(factor_df, already_shifted=already_shifted)
    ranks = factor.unstack("ticker").sort_index().rank(axis=1, method="average")
    autocorr = ranks.corrwith(ranks.shift(lag), axis=1).replace([np.inf, -np.inf], np.nan)
    autocorr.name = f"rank_autocorr_lag_{lag}"
    return autocorr


def quantile_membership_turnover(
    factor_df: pd.DataFrame | pd.Series,
    n_quantiles: int = 10,
    already_shifted: bool = True,
) -> pd.DataFrame:
    """Measure daily fraction of names entering and leaving each factor quantile."""
    if not isinstance(n_quantiles, int) or n_quantiles < 2:
        raise ValueError("n_quantiles must be at least 2.")
    factor = prepare_factor_series(factor_df, already_shifted=already_shifted)
    labels = factor.groupby(level="date", sort=True).transform(lambda values: _daily_quantile_labels(values, n_quantiles))
    label_wide = labels.unstack("ticker").sort_index()
    rows = []
    previous_sets: dict[str, set[str]] | None = None
    for date, row in label_wide.iterrows():
        current_sets = {f"Q{i}": set(row[row == f"Q{i}"].index.astype(str)) for i in range(1, n_quantiles + 1)}
        record: dict[str, object] = {"date": date}
        for quantile, current in current_sets.items():
            previous = previous_sets.get(quantile, set()) if previous_sets is not None else set()
            denominator = max(len(current), len(previous), 1)
            record[f"{quantile}_turnover"] = float(len(current.symmetric_difference(previous)) / denominator) if previous_sets is not None else np.nan
        rows.append(record)
        previous_sets = current_sets
    return pd.DataFrame(rows).set_index("date").sort_index()


def signal_half_life(rank_autocorr_series: pd.Series) -> float:
    """Estimate signal half-life from mean lag-1 rank autocorrelation."""
    if not isinstance(rank_autocorr_series, pd.Series):
        raise TypeError("rank_autocorr_series must be a pandas Series.")
    rho = float(rank_autocorr_series.replace([np.inf, -np.inf], np.nan).dropna().mean())
    if rho <= 0.0 or rho >= 1.0:
        return float("nan")
    return float(np.log(0.5) / np.log(rho))


def summarize_factor_turnover(factor_df: pd.DataFrame | pd.Series, n_quantiles: int = 10, already_shifted: bool = True) -> dict[str, float]:
    """Return compact rank and quantile turnover metrics."""
    autocorr = rank_autocorrelation(factor_df, already_shifted=already_shifted)
    quantile_turnover = quantile_membership_turnover(factor_df, n_quantiles=n_quantiles, already_shifted=already_shifted)
    return {
        "rank_autocorr_mean": float(autocorr.mean(skipna=True)),
        "rank_autocorr_median": float(autocorr.median(skipna=True)),
        "signal_half_life_days": signal_half_life(autocorr),
        "quantile_turnover_mean": float(quantile_turnover.mean(axis=1, skipna=True).mean(skipna=True)),
        "top_quantile_turnover_mean": float(quantile_turnover[f"Q{n_quantiles}_turnover"].mean(skipna=True)),
        "bottom_quantile_turnover_mean": float(quantile_turnover["Q1_turnover"].mean(skipna=True)),
    }


def _daily_quantile_labels(values: pd.Series, n_quantiles: int) -> pd.Series:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna()
    output = pd.Series(np.nan, index=values.index, dtype=object)
    if clean.shape[0] < n_quantiles:
        return output
    labels = [f"Q{i}" for i in range(1, n_quantiles + 1)]
    try:
        output.loc[clean.index] = pd.qcut(clean.rank(method="first"), q=n_quantiles, labels=labels).astype(str)
    except ValueError:
        pass
    return output
