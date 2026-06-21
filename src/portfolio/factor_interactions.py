"""Factor interaction, PCA, and orthogonalization diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def factor_correlation_matrix(factors: pd.DataFrame, method: str = "spearman") -> pd.DataFrame:
    """Compute a factor correlation matrix from a MultiIndex factor panel."""
    _validate_factor_frame(factors)
    if method not in {"spearman", "pearson"}:
        raise ValueError("method must be spearman or pearson.")
    return factors.replace([np.inf, -np.inf], np.nan).corr(method=method)


def rolling_factor_correlation(factors: pd.DataFrame, left: str, right: str, window: int = 252, method: str = "spearman") -> pd.Series:
    """Compute rolling mean of daily cross-sectional factor correlations."""
    _validate_factor_frame(factors)
    if left not in factors.columns or right not in factors.columns:
        raise ValueError("left and right must be columns in factors.")
    if window < 3:
        raise ValueError("window must be at least 3.")
    if method not in {"spearman", "pearson"}:
        raise ValueError("method must be spearman or pearson.")
    left_wide = factors[left].replace([np.inf, -np.inf], np.nan).unstack("ticker").sort_index()
    right_wide = factors[right].replace([np.inf, -np.inf], np.nan).unstack("ticker").sort_index()
    left_wide, right_wide = left_wide.align(right_wide, join="outer", axis=None)
    if method == "spearman":
        left_wide = left_wide.rank(axis=1, method="average")
        right_wide = right_wide.rank(axis=1, method="average")
    daily_corr = _rowwise_correlation(left_wide, right_wide)
    daily_corr.index = pd.to_datetime(daily_corr.index)
    result = daily_corr.sort_index().rolling(window, min_periods=max(3, window // 2)).mean()
    result.name = f"rolling_corr_{left}__{right}"
    return result


def pca_factor_diagnostics(factors: pd.DataFrame, n_components: int | None = None) -> pd.DataFrame:
    """Return PCA eigenvalue and explained-variance diagnostics for factor columns."""
    _validate_factor_frame(factors)
    clean = factors.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if clean.shape[0] < 3 or clean.shape[1] < 2:
        return pd.DataFrame(columns=["component", "eigenvalue", "explained_variance_ratio", "cumulative_explained_variance"])
    standardized = (clean - clean.mean()) / clean.std(ddof=1).replace(0.0, np.nan)
    standardized = standardized.dropna(axis=1, how="any")
    if standardized.shape[1] < 2:
        return pd.DataFrame(columns=["component", "eigenvalue", "explained_variance_ratio", "cumulative_explained_variance"])
    covariance = np.cov(standardized.to_numpy(dtype=float), rowvar=False)
    eigenvalues = np.linalg.eigvalsh(covariance)[::-1]
    if n_components is not None:
        eigenvalues = eigenvalues[: int(n_components)]
    total = float(eigenvalues.sum())
    ratios = eigenvalues / total if total > 0.0 else np.full_like(eigenvalues, np.nan)
    return pd.DataFrame(
        {
            "component": [f"PC{i}" for i in range(1, len(eigenvalues) + 1)],
            "eigenvalue": eigenvalues,
            "explained_variance_ratio": ratios,
            "cumulative_explained_variance": np.cumsum(ratios),
        }
    )


def orthogonalize_factor(target: pd.Series, controls: pd.DataFrame) -> pd.Series:
    """Residualize one factor against control factor exposures cross-sectionally by date."""
    if not isinstance(target, pd.Series):
        raise TypeError("target must be a pandas Series.")
    if not isinstance(controls, pd.DataFrame):
        raise TypeError("controls must be a pandas DataFrame.")
    if not isinstance(target.index, pd.MultiIndex) or not isinstance(controls.index, pd.MultiIndex):
        raise TypeError("target and controls must use MultiIndex(date, ticker).")
    joined = pd.concat([target.rename("__target__"), controls], axis=1).replace([np.inf, -np.inf], np.nan)
    residuals = joined.groupby(level="date", group_keys=False).apply(_residualize_one_date)
    residuals.name = f"{target.name or 'factor'}_orthogonalized"
    return residuals.sort_index()


def factor_exposure_summary(weights: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Compute portfolio factor exposures as weighted average factor values."""
    _validate_factor_frame(factors)
    if not isinstance(weights, pd.DataFrame):
        raise TypeError("weights must be a pandas DataFrame.")
    factor_panels = {name: factors[name].unstack("ticker").reindex(index=weights.index, columns=weights.columns) for name in factors.columns}
    rows = []
    for date in weights.index:
        record: dict[str, object] = {"date": date}
        weight_row = weights.loc[date].fillna(0.0)
        for name, panel in factor_panels.items():
            record[name] = float((weight_row * panel.loc[date]).sum(skipna=True))
        rows.append(record)
    return pd.DataFrame(rows).set_index("date")


def _residualize_one_date(daily: pd.DataFrame) -> pd.Series:
    clean = daily.dropna()
    output = pd.Series(np.nan, index=daily.index, dtype=float)
    control_columns = [column for column in daily.columns if column != "__target__"]
    if clean.shape[0] <= len(control_columns) + 1:
        return output
    x = clean[control_columns].to_numpy(dtype=float)
    x = np.column_stack([np.ones(clean.shape[0]), x])
    y = clean["__target__"].to_numpy(dtype=float)
    if np.linalg.matrix_rank(x) < x.shape[1]:
        return output
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    output.loc[clean.index] = y - x @ beta
    return output


def _rowwise_correlation(left: pd.DataFrame, right: pd.DataFrame) -> pd.Series:
    valid = left.notna() & right.notna()
    left_clean = left.where(valid)
    right_clean = right.where(valid)
    counts = valid.sum(axis=1)
    left_centered = left_clean.sub(left_clean.mean(axis=1), axis=0)
    right_centered = right_clean.sub(right_clean.mean(axis=1), axis=0)
    numerator = (left_centered * right_centered).sum(axis=1, min_count=1)
    left_ss = (left_centered * left_centered).sum(axis=1, min_count=1)
    right_ss = (right_centered * right_centered).sum(axis=1, min_count=1)
    denominator = (left_ss * right_ss).pow(0.5).replace(0.0, np.nan)
    return (numerator / denominator).where(counts >= 3)


def _validate_factor_frame(factors: pd.DataFrame) -> None:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame.")
    if not isinstance(factors.index, pd.MultiIndex):
        raise TypeError("factors must use MultiIndex(date, ticker).")
    if factors.empty:
        raise ValueError("factors must not be empty.")
