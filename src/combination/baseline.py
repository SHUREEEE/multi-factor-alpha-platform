"""Baseline utilities for Pillar 4 factor combination and portfolio testing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.factors.utils import validate_multiindex_frame
from src.research.ic_analysis import extract_daily_return_matrix
from src.research.quantile_test import TRADING_DAYS_PER_YEAR, compute_annualized_sharpe


@dataclass(frozen=True)
class FactorSpec:
    """Configuration for one factor used in the Pillar 4 baseline."""

    name: str
    sign: int


@dataclass(frozen=True)
class BaselineBacktestResult:
    """Container for daily portfolio returns and summary statistics."""

    daily_returns: pd.DataFrame
    summary: dict[str, float | int | str]


def build_sign_adjusted_panel(factors: pd.DataFrame, specs: list[FactorSpec]) -> pd.DataFrame:
    """Flip selected factors and re-zscore each factor by date.

    Parameters
    ----------
    factors:
        Raw or sector-neutral factor panel indexed by ``(date, ticker)``.
    specs:
        Factor names and signs where ``-1`` means the factor is reversed.

    Returns
    -------
    pandas.DataFrame
        Sign-adjusted and cross-sectionally standardized factor panel.
    """
    _validate_factor_panel(factors)
    _validate_specs(specs)
    missing_names = sorted(set(spec.name for spec in specs) - set(factors.columns))
    if missing_names:
        raise ValueError(f"Missing factor columns: {missing_names}")
    selected = factors[[spec.name for spec in specs]].astype(float).copy()
    for spec in specs:
        selected[spec.name] = selected[spec.name] * float(spec.sign)  # 中文：负向因子翻转后，所有列都变成“越高越看多”。
    adjusted_parts = [_zscore_one_factor(selected[[spec.name]]) for spec in specs]
    output = pd.concat(adjusted_parts, axis=1).sort_index()
    assert output.index.equals(selected.index)
    return output


def build_factor_correlation_report(factors: pd.DataFrame, threshold: float = 0.7) -> pd.DataFrame:
    """Average daily pairwise Spearman rank correlations between factors."""
    _validate_factor_panel(factors)
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1.")
    rows: list[dict[str, float | str | bool]] = []
    factor_names = list(factors.columns)
    for left_index, left_name in enumerate(factor_names):
        for right_name in factor_names[left_index + 1 :]:
            average_correlation = _average_daily_rank_correlation(factors[left_name], factors[right_name])
            rows.append(
                {
                    "factor_1": left_name,
                    "factor_2": right_name,
                    "average_rank_correlation": average_correlation,
                    "abs_average_rank_correlation": abs(average_correlation),
                    "deduplication_flag": abs(average_correlation) > threshold,
                }
            )
    return pd.DataFrame(rows).sort_values("abs_average_rank_correlation", ascending=False)


def backtest_top_bottom_decile(
    composite: pd.DataFrame | pd.Series,
    prices: pd.DataFrame | pd.Series,
    n_quantiles: int = 10,
) -> BaselineBacktestResult:
    """Backtest a daily rebalanced top-decile minus bottom-decile portfolio."""
    _validate_n_quantiles(n_quantiles)
    composite_series = _as_series(composite, "composite")
    daily_returns = extract_daily_return_matrix(prices)
    signal_wide = composite_series.unstack("ticker").sort_index()
    trading_signal = signal_wide.shift(1)  # 中文：T 日持仓只能使用 T-1 已知信号，避免组合层前视偏差。
    aligned_signal, aligned_returns = trading_signal.align(daily_returns, join="inner", axis=None)
    weights = aligned_signal.apply(lambda row: _daily_decile_weights(row, n_quantiles), axis=1)
    portfolio_returns = (weights * aligned_returns).sum(axis=1, min_count=1).rename("long_short_return")
    turnover = _compute_turnover(weights)
    output = pd.DataFrame(
        {
            "long_short_return": portfolio_returns,
            "cumulative_return": (1.0 + portfolio_returns.fillna(0.0)).cumprod() - 1.0,
            "turnover": turnover,
        }
    )
    output.index.name = "date"
    return BaselineBacktestResult(daily_returns=output, summary=_summarize_backtest(output, weights))


def _validate_factor_panel(factors: pd.DataFrame) -> None:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame.")
    validate_multiindex_frame(factors, "factors")
    if factors.index.has_duplicates:
        raise ValueError("factors index contains duplicate (date, ticker) rows.")


def _validate_specs(specs: list[FactorSpec]) -> None:
    if not specs:
        raise ValueError("specs must not be empty.")
    names = [spec.name for spec in specs]
    if len(names) != len(set(names)):
        raise ValueError("factor specs contain duplicate factor names.")
    bad_signs = [spec.sign for spec in specs if spec.sign not in {-1, 1}]
    if bad_signs:
        raise ValueError("factor signs must be either 1 or -1.")


def _zscore_one_factor(factor_frame: pd.DataFrame) -> pd.DataFrame:
    column_name = factor_frame.columns[0]
    grouped = factor_frame.groupby(level="date", group_keys=False)
    return grouped.apply(lambda daily: _zscore_daily_frame(daily, column_name)).reindex(factor_frame.index)


def _zscore_daily_frame(daily_frame: pd.DataFrame, column_name: str) -> pd.DataFrame:
    values = daily_frame[column_name].replace([np.inf, -np.inf], np.nan).astype(float)
    mean_value = values.mean(skipna=True)
    std_value = values.std(skipna=True, ddof=0)
    if pd.isna(std_value) or std_value == 0.0:
        return pd.DataFrame({column_name: np.nan}, index=daily_frame.index)
    return pd.DataFrame({column_name: (values - mean_value) / std_value}, index=daily_frame.index)


def _average_daily_rank_correlation(left: pd.Series, right: pd.Series) -> float:
    paired = pd.concat([left, right], axis=1, keys=["left", "right"])
    daily_correlations = paired.groupby(level="date").apply(_daily_rank_correlation)
    clean_correlations = daily_correlations.replace([np.inf, -np.inf], np.nan).dropna()
    if clean_correlations.empty:
        return float("nan")
    return float(clean_correlations.mean())


def _daily_rank_correlation(daily_data: pd.DataFrame) -> float:
    clean_data = daily_data.replace([np.inf, -np.inf], np.nan).dropna()
    if clean_data.shape[0] < 3:
        return float("nan")
    return float(clean_data["left"].rank().corr(clean_data["right"].rank()))


def _as_series(composite: pd.DataFrame | pd.Series, name: str) -> pd.Series:
    validate_multiindex_frame(composite, name)
    if isinstance(composite, pd.DataFrame):
        if composite.shape[1] != 1:
            raise ValueError(f"{name} must contain exactly one column.")
        series = composite.iloc[:, 0]
    else:
        series = composite
    return series.replace([np.inf, -np.inf], np.nan).astype(float).sort_index().rename(name)


def _validate_n_quantiles(n_quantiles: int) -> None:
    if not isinstance(n_quantiles, int) or n_quantiles < 2:
        raise ValueError("n_quantiles must be an integer greater than or equal to 2.")


def _daily_decile_weights(signal_row: pd.Series, n_quantiles: int) -> pd.Series:
    clean_signal = signal_row.replace([np.inf, -np.inf], np.nan).dropna()
    weights = pd.Series(0.0, index=signal_row.index, dtype=float)
    if clean_signal.shape[0] < n_quantiles:
        return weights * np.nan
    ranks = clean_signal.rank(method="first")
    try:
        labels = pd.qcut(ranks, q=n_quantiles, labels=False) + 1
    except ValueError:
        return weights * np.nan
    long_names = labels[labels == n_quantiles].index
    short_names = labels[labels == 1].index
    if len(long_names) == 0 or len(short_names) == 0:
        return weights * np.nan
    weights.loc[long_names] = 1.0 / len(long_names)
    weights.loc[short_names] = -1.0 / len(short_names)
    return weights


def _compute_turnover(weights: pd.DataFrame) -> pd.Series:
    clean_weights = weights.fillna(0.0)
    turnover = clean_weights.diff().abs().sum(axis=1) * 0.5
    if not turnover.empty:
        turnover.iloc[0] = np.nan
    return turnover.rename("turnover")


def _summarize_backtest(daily_returns: pd.DataFrame, weights: pd.DataFrame) -> dict[str, float | int | str]:
    returns = daily_returns["long_short_return"].replace([np.inf, -np.inf], np.nan).dropna()
    cumulative = daily_returns["cumulative_return"].replace([np.inf, -np.inf], np.nan)
    return {
        "start_date": str(returns.index.min().date()) if not returns.empty else "",
        "end_date": str(returns.index.max().date()) if not returns.empty else "",
        "n_days": int(returns.shape[0]),
        "annualized_return": _annualized_return(returns),
        "annualized_sharpe": compute_annualized_sharpe(returns),
        "max_drawdown": _max_drawdown(cumulative),
        "average_daily_turnover": float(daily_returns["turnover"].mean(skipna=True)),
        "hit_rate": float((returns > 0.0).mean()) if not returns.empty else float("nan"),
        "average_long_count": float((weights > 0.0).sum(axis=1).replace(0, np.nan).mean()),
        "average_short_count": float((weights < 0.0).sum(axis=1).replace(0, np.nan).mean()),
    }


def _annualized_return(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    total_return = float((1.0 + returns).prod() - 1.0)
    years = returns.shape[0] / TRADING_DAYS_PER_YEAR
    if years <= 0.0:
        return float("nan")
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def _max_drawdown(cumulative_returns: pd.Series) -> float:
    wealth = 1.0 + cumulative_returns.dropna()
    if wealth.empty:
        return float("nan")
    running_peak = wealth.cummax()
    drawdown = wealth / running_peak - 1.0
    return float(drawdown.min())
