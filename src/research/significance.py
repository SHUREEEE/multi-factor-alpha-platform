"""Statistical significance helpers for institutional factor validation."""

from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd
import statsmodels.api as sm


def newey_west_mean_test(series: pd.Series, lags: int = 5) -> dict[str, float]:
    """Test whether a time-series mean differs from zero using HAC errors."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    if not isinstance(lags, int) or lags < 0:
        raise ValueError("lags must be a non-negative integer.")
    clean = series.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if clean.shape[0] < 3:
        return {"mean": np.nan, "std_error": np.nan, "t_stat": np.nan, "p_value": np.nan, "n_obs": float(clean.shape[0])}
    model = sm.OLS(clean.to_numpy(dtype=float), np.ones((clean.shape[0], 1))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {
        "mean": float(model.params[0]),
        "std_error": float(model.bse[0]),
        "t_stat": float(model.tvalues[0]),
        "p_value": float(model.pvalues[0]),
        "n_obs": float(clean.shape[0]),
    }


def benjamini_hochberg(p_values: pd.Series | list[float] | np.ndarray) -> pd.Series:
    """Return Benjamini-Hochberg FDR-adjusted p-values."""
    values = pd.Series(p_values, dtype=float)
    adjusted = pd.Series(np.nan, index=values.index, dtype=float)
    clean = values.replace([np.inf, -np.inf], np.nan).dropna()
    m = clean.shape[0]
    if m == 0:
        return adjusted
    ordered = clean.sort_values()
    ranks = np.arange(1, m + 1, dtype=float)
    raw = ordered.to_numpy(dtype=float) * m / ranks
    monotone = np.minimum.accumulate(raw[::-1])[::-1]
    adjusted.loc[ordered.index] = np.clip(monotone, 0.0, 1.0)
    return adjusted


def bootstrap_mean_ci(
    series: pd.Series,
    *,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    random_state: int = 0,
) -> dict[str, float]:
    """Estimate a bootstrap confidence interval for the mean."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be positive.")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1.")
    clean = series.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if clean.empty:
        return {"mean": np.nan, "ci_low": np.nan, "ci_high": np.nan, "n_obs": 0.0}
    rng = np.random.default_rng(random_state)
    values = clean.to_numpy(dtype=float)
    samples = rng.choice(values, size=(n_bootstrap, values.shape[0]), replace=True)
    means = samples.mean(axis=1)
    alpha = 1.0 - confidence
    return {
        "mean": float(values.mean()),
        "ci_low": float(np.quantile(means, alpha / 2.0)),
        "ci_high": float(np.quantile(means, 1.0 - alpha / 2.0)),
        "n_obs": float(values.shape[0]),
    }


def annualized_ir(mean: float, std: float, periods_per_year: int = 252) -> float:
    """Convert a mean/std ratio into an annualized information ratio."""
    if std == 0.0 or np.isnan(std):
        return float("nan")
    return float(mean / std * sqrt(periods_per_year))
