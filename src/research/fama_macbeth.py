"""Fama-MacBeth cross-sectional regression tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.research.ic_analysis import make_forward_returns, prepare_factor_series


def run_fama_macbeth(
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    control_factors: dict[str, pd.DataFrame | pd.Series] | None = None,
    already_shifted: bool = True,
    nw_lags: int = 5,
) -> pd.DataFrame:
    """Run a two-step Fama-MacBeth regression.

    Parameters
    ----------
    factor_df:
        Main factor panel indexed by ``(date, ticker)``.
    return_df:
        Daily return panel or price frame containing ``return_1d``.
    control_factors:
        Optional control factor panels with the same index structure.
    already_shifted:
        If ``False``, shift all factor inputs before regression.
    nw_lags:
        Newey-West lag count for coefficient time-series inference.

    Returns
    -------
    pandas.DataFrame
        Coefficient, Newey-West t-statistic, p-value, and number of dates.
    """
    if not isinstance(nw_lags, int) or nw_lags < 0:
        raise ValueError("nw_lags must be a non-negative integer.")
    regression_data = _build_regression_data(factor_df, return_df, control_factors, already_shifted)
    daily_coefficients = regression_data.groupby(level="date", sort=True).apply(_fit_one_cross_section)
    clean_coefficients = daily_coefficients.dropna(how="all")
    if clean_coefficients.empty:
        return _empty_result(["factor"] + list((control_factors or {}).keys()))
    return _summarize_coefficients(clean_coefficients, nw_lags)


def _build_regression_data(
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    control_factors: dict[str, pd.DataFrame | pd.Series] | None,
    already_shifted: bool,
) -> pd.DataFrame:
    main_factor = prepare_factor_series(factor_df, already_shifted=already_shifted).rename("factor")
    forward_returns = make_forward_returns(return_df, period=1).rename("forward_return")
    regression_parts = [main_factor, forward_returns]
    for control_name, control_frame in (control_factors or {}).items():
        control_series = prepare_factor_series(control_frame, already_shifted=already_shifted).rename(control_name)
        regression_parts.append(control_series)
    return pd.concat(regression_parts, axis=1).replace([np.inf, -np.inf], np.nan)


def _fit_one_cross_section(daily_data: pd.DataFrame) -> pd.Series:
    clean_data = daily_data.dropna()
    coefficient_names = [column for column in daily_data.columns if column != "forward_return"]
    if clean_data.shape[0] <= len(coefficient_names) + 1:
        return pd.Series(np.nan, index=coefficient_names, dtype=float)
    design_matrix = sm.add_constant(clean_data[coefficient_names], has_constant="add")
    if np.linalg.matrix_rank(design_matrix.to_numpy(dtype=float)) < design_matrix.shape[1]:
        return pd.Series(np.nan, index=coefficient_names, dtype=float)
    model = sm.OLS(clean_data["forward_return"].astype(float), design_matrix.astype(float)).fit()
    return model.params.reindex(coefficient_names).astype(float)


def _summarize_coefficients(daily_coefficients: pd.DataFrame, nw_lags: int) -> pd.DataFrame:
    rows = []
    for coefficient_name in daily_coefficients.columns:
        clean_series = daily_coefficients[coefficient_name].dropna().astype(float)
        rows.append(_summarize_one_coefficient(clean_series, coefficient_name, nw_lags))
    return pd.DataFrame(rows).set_index("variable")


def _summarize_one_coefficient(beta_series: pd.Series, coefficient_name: str, nw_lags: int) -> dict[str, float | str]:
    if beta_series.shape[0] < 3:
        return {"variable": coefficient_name, "coefficient": np.nan, "t_stat": np.nan, "p_value": np.nan, "n_dates": float(beta_series.shape[0])}
    intercept_only = np.ones((beta_series.shape[0], 1))
    model = sm.OLS(beta_series.to_numpy(dtype=float), intercept_only).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lags})
    return {
        "variable": coefficient_name,
        "coefficient": float(model.params[0]),
        "t_stat": float(model.tvalues[0]),
        "p_value": float(model.pvalues[0]),
        "n_dates": float(beta_series.shape[0]),
    }


def _empty_result(variable_names: list[str]) -> pd.DataFrame:
    rows = [{"variable": name, "coefficient": np.nan, "t_stat": np.nan, "p_value": np.nan, "n_dates": 0.0} for name in variable_names]
    return pd.DataFrame(rows).set_index("variable")
