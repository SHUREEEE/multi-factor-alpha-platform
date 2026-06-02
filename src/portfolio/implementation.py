"""Implementation-aware portfolio construction diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.factors.utils import validate_multiindex_frame
from src.research.ic_analysis import extract_daily_return_matrix


@dataclass(frozen=True)
class ImplementationBacktestResult:
    """Daily implementation-aware portfolio outputs."""

    daily_returns: pd.DataFrame
    weights: pd.DataFrame


def build_liquidity_mask(prices: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Build an investability mask from price and 20-day average dollar volume."""
    _validate_prices(prices)
    adj_close = prices["adj_close"].unstack("ticker").astype(float).sort_index()
    if mode == "none":
        return adj_close.notna()
    if mode != "adv20_filtered":
        raise ValueError("mode must be either 'none' or 'adv20_filtered'.")
    dollar_volume = (prices["adj_close"] * prices["volume"]).unstack("ticker").astype(float).sort_index()
    adv20 = dollar_volume.rolling(window=20, min_periods=20).mean()
    price_mask = adj_close >= 5.0
    adv_rank = adv20.rank(axis=1, pct=True)
    liquidity_mask = price_mask & adv_rank.gt(0.10)
    return liquidity_mask.reindex(adj_close.index)


def backtest_rebalanced_deciles(
    composite: pd.DataFrame | pd.Series,
    prices: pd.DataFrame,
    rebalance_frequency: str,
    liquidity_mask: pd.DataFrame,
    n_quantiles: int = 10,
) -> ImplementationBacktestResult:
    """Backtest decile long-short weights with daily or weekly refresh."""
    weights = build_rebalanced_decile_weights(composite, prices, rebalance_frequency, liquidity_mask, n_quantiles)
    return backtest_from_weights(weights, prices)


def build_rebalanced_decile_weights(
    composite: pd.DataFrame | pd.Series,
    prices: pd.DataFrame,
    rebalance_frequency: str,
    liquidity_mask: pd.DataFrame,
    n_quantiles: int = 10,
) -> pd.DataFrame:
    """Build lagged decile weights without computing portfolio returns."""
    _validate_frequency(rebalance_frequency)
    composite_series = _as_series(composite, "composite")
    daily_returns = extract_daily_return_matrix(prices)
    signal = composite_series.unstack("ticker").sort_index().shift(1)
    signal, returns = signal.align(daily_returns, join="inner", axis=None)
    clean_mask = liquidity_mask.reindex(index=signal.index, columns=signal.columns).fillna(False)
    masked_signal = signal.where(clean_mask)
    target_weights = masked_signal.apply(lambda row: _daily_decile_weights(row, n_quantiles), axis=1)
    return _apply_rebalance_frequency(target_weights, rebalance_frequency)


def backtest_from_weights(weights: pd.DataFrame, prices: pd.DataFrame) -> ImplementationBacktestResult:
    """Backtest a supplied date-by-ticker weight matrix."""
    returns = extract_daily_return_matrix(prices).reindex(index=weights.index, columns=weights.columns)
    portfolio_returns = (weights * returns).sum(axis=1, min_count=1).rename("long_short_return")
    turnover = decompose_turnover(weights)
    output = pd.concat([portfolio_returns, turnover], axis=1)
    output["cumulative_return"] = (1.0 + output["long_short_return"].fillna(0.0)).cumprod() - 1.0
    output.index.name = "date"
    return ImplementationBacktestResult(daily_returns=output, weights=weights)


def decompose_turnover(weights: pd.DataFrame) -> pd.DataFrame:
    """Split daily turnover into long, short, entry, and exit components."""
    clean_weights = weights.fillna(0.0)
    previous = clean_weights.shift(1).fillna(0.0)
    delta = clean_weights - previous
    long_turnover = delta.where((clean_weights > 0.0) | (previous > 0.0), 0.0).abs().sum(axis=1) * 0.5
    short_turnover = delta.where((clean_weights < 0.0) | (previous < 0.0), 0.0).abs().sum(axis=1) * 0.5
    total_turnover = clean_weights.diff().abs().sum(axis=1) * 0.5
    entry_turnover = delta.where((previous == 0.0) & (clean_weights != 0.0), 0.0).abs().sum(axis=1) * 0.5
    exit_turnover = delta.where((previous != 0.0) & (clean_weights == 0.0), 0.0).abs().sum(axis=1) * 0.5
    output = pd.DataFrame(
        {
            "turnover": total_turnover,
            "long_turnover": long_turnover,
            "short_turnover": short_turnover,
            "entry_turnover": entry_turnover,
            "exit_turnover": exit_turnover,
        },
        index=weights.index,
    )
    if not output.empty:
        output.iloc[0] = np.nan
    return output


def _validate_prices(prices: pd.DataFrame) -> None:
    if not isinstance(prices, pd.DataFrame):
        raise TypeError("prices must be a pandas DataFrame.")
    validate_multiindex_frame(prices, "prices")
    missing_columns = sorted({"adj_close", "volume"} - set(prices.columns))
    if missing_columns:
        raise ValueError(f"prices missing required columns: {missing_columns}")


def _as_series(composite: pd.DataFrame | pd.Series, name: str) -> pd.Series:
    validate_multiindex_frame(composite, name)
    if isinstance(composite, pd.DataFrame):
        if composite.shape[1] != 1:
            raise ValueError(f"{name} must contain exactly one column.")
        series = composite.iloc[:, 0]
    else:
        series = composite
    return series.replace([np.inf, -np.inf], np.nan).astype(float).sort_index().rename(name)


def _validate_frequency(rebalance_frequency: str) -> None:
    if rebalance_frequency not in {"daily", "weekly_5d"}:
        raise ValueError("rebalance_frequency must be 'daily' or 'weekly_5d'.")


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
    weights.loc[long_names] = 1.0 / len(long_names)
    weights.loc[short_names] = -1.0 / len(short_names)
    return weights


def _apply_rebalance_frequency(target_weights: pd.DataFrame, rebalance_frequency: str) -> pd.DataFrame:
    if rebalance_frequency == "daily":
        return target_weights
    rebalance_positions = np.arange(len(target_weights)) % 5 == 0
    rebalance_mask = pd.Series(rebalance_positions, index=target_weights.index)
    refresh_weights = target_weights.where(rebalance_mask, axis=0)
    return refresh_weights.ffill()
