"""V4 trend-based regime sizing.

Trend sizing is keyed to trailing market returns, not realized volatility.
Percentiles are point-in-time safe: date t is ranked against history available
through t-1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrendSizingResult:
    """Daily market-trend sizing state."""

    multiplier: pd.Series
    trailing_return: pd.Series
    percentile: pd.Series
    regime_label: pd.Series
    market_proxy_label: str
    warmup_dates: list[pd.Timestamp]


def compute_trend_sizing_multiplier(
    spy_returns: pd.Series,
    *,
    trailing_return_window: int = 60,
    percentile_window: int = 756,
    bottom_quartile_multiplier: float = 0.5,
    min_history_days: int = 252,
    market_proxy_name: str = "SPY",
) -> TrendSizingResult:
    """Compute daily V4 sizing multiplier from market trailing-return percentile."""
    if trailing_return_window <= 0:
        raise ValueError("trailing_return_window must be positive.")
    if percentile_window <= 1:
        raise ValueError("percentile_window must be greater than 1.")
    if min_history_days <= 0:
        raise ValueError("min_history_days must be positive.")
    if not 0.0 <= bottom_quartile_multiplier <= 1.0:
        raise ValueError("bottom_quartile_multiplier must be in [0, 1].")

    returns = spy_returns.astype(float).sort_index()
    trailing_return = returns.rolling(
        trailing_return_window,
        min_periods=trailing_return_window,
    ).apply(_compound_return, raw=True)
    trailing_return.name = "trailing_return"

    percentile = pd.Series(np.nan, index=returns.index, name="percentile", dtype=float)
    for date in returns.index:
        historical = trailing_return.loc[:date].iloc[:-1].dropna().tail(percentile_window)
        if len(historical) < min_history_days or pd.isna(trailing_return.loc[date]):
            continue
        percentile.loc[date] = float((historical <= trailing_return.loc[date]).mean())

    regime_label = pd.Series("INSUFFICIENT_HISTORY", index=returns.index, name="regime_label", dtype=object)
    multiplier = pd.Series(np.nan, index=returns.index, name="sizing_multiplier", dtype=float)
    ready = percentile.notna()
    trend_down = ready & (percentile <= 0.25)
    neutral = ready & ~trend_down
    regime_label.loc[trend_down] = "TREND_DOWN"
    regime_label.loc[neutral] = "NEUTRAL"
    multiplier.loc[trend_down] = float(bottom_quartile_multiplier)
    multiplier.loc[neutral] = 1.0

    return TrendSizingResult(
        multiplier=multiplier,
        trailing_return=trailing_return,
        percentile=percentile,
        regime_label=regime_label,
        market_proxy_label=str(market_proxy_name),
        warmup_dates=[pd.Timestamp(date) for date in returns.index[~ready]],
    )


def _compound_return(values) -> float:
    clean = np.asarray(values, dtype=float)
    clean = clean[~np.isnan(clean)]
    if clean.size == 0:
        return float("nan")
    return float(np.prod(1.0 + clean) - 1.0)
