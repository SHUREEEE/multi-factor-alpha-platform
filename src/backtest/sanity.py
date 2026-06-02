"""
Sanity check expectations:

random alpha -> |Sharpe| < 0.3 typically
perfect foresight WITHOUT shift -> Sharpe > 5 (proves engine can show alpha)
perfect foresight WITH shift -> Sharpe modest (proves shift protects us)
reverse strategy -> Sharpe sign flips, magnitude similar (within 10%)
If your real strategy Sharpe > 3, suspect look-ahead bias.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import VectorizedBacktester
from src.backtest.pnl import compute_metrics, compute_pnl

ZERO_COST = {"linear_bps": 0.0, "impact_coefficient": 0.0, "use_sqrt_impact": False}


def random_alpha_sharpe(prices: pd.DataFrame, returns: pd.DataFrame, n_trials: int = 20, seed: int = 42) -> dict:
    """Run random long-short books through the shifted engine."""

    price_panel, return_panel = _aligned_panels(prices, returns)
    rng = np.random.default_rng(seed)
    trials = []
    n_pairs = n_trials // 2
    for _ in range(n_pairs):
        raw = pd.DataFrame(rng.normal(size=return_panel.shape), index=return_panel.index, columns=return_panel.columns)
        for weights in (_normalize_long_short(raw), _normalize_long_short(-raw)):
            pnl = VectorizedBacktester(weights, price_panel, ZERO_COST).run().pnl
            trials.append(float(compute_metrics(pnl)["sharpe"]))
    if n_trials % 2:
        raw = pd.DataFrame(rng.normal(size=return_panel.shape), index=return_panel.index, columns=return_panel.columns)
        pnl = VectorizedBacktester(_normalize_long_short(raw), price_panel, ZERO_COST).run().pnl
        trials.append(float(compute_metrics(pnl)["sharpe"]))
    return {"mean_sharpe": float(np.mean(trials)), "std_sharpe": float(np.std(trials)), "trials": trials}


def perfect_foresight_sharpe(prices: pd.DataFrame, returns: pd.DataFrame) -> dict:
    """Compare same-row lookahead PnL against the shifted engine path."""

    price_panel, return_panel = _aligned_panels(prices, returns)
    weights = _top_bottom_decile_weights(return_panel)
    lookahead_pnl = weights.mul(return_panel).sum(axis=1)
    shifted_pnl = VectorizedBacktester(weights, price_panel, ZERO_COST).run().pnl
    return {
        "sharpe_with_lookahead": float(compute_metrics(lookahead_pnl)["sharpe"]),
        "sharpe_with_shift": float(compute_metrics(shifted_pnl)["sharpe"]),
    }


def reverse_strategy_sharpe(prices: pd.DataFrame, returns: pd.DataFrame, base_weights: pd.DataFrame) -> dict:
    """Check that reversing a baseline book flips Sharpe with similar magnitude."""

    price_panel, return_panel = _aligned_panels(prices, returns)
    weights = base_weights.reindex(index=return_panel.index, columns=return_panel.columns).fillna(0.0)
    original = compute_metrics(VectorizedBacktester(weights, price_panel, ZERO_COST).run().pnl)["sharpe"]
    reversed_sharpe = compute_metrics(VectorizedBacktester(-weights, price_panel, ZERO_COST).run().pnl)["sharpe"]
    return {"original_sharpe": float(original), "reversed_sharpe": float(reversed_sharpe)}


def _aligned_panels(prices: pd.DataFrame, returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    price_panel = _price_panel(prices)
    return_panel = _panel(returns)
    price_panel, return_panel = price_panel.align(return_panel, join="inner", axis=0)
    price_panel, return_panel = price_panel.align(return_panel, join="inner", axis=1)
    return price_panel, return_panel.fillna(0.0)


def _price_panel(prices: pd.DataFrame) -> pd.DataFrame:
    if isinstance(prices.index, pd.MultiIndex):
        if "adj_close" not in prices.columns:
            raise ValueError("prices must contain adj_close in long form.")
        panel = prices["adj_close"].unstack("ticker")
    elif "adj_close" in prices.columns and {"date", "ticker"}.issubset(prices.columns):
        panel = prices.pivot(index="date", columns="ticker", values="adj_close")
    else:
        panel = prices.copy()
    return _panel(panel)


def _panel(frame: pd.DataFrame) -> pd.DataFrame:
    panel = frame.copy()
    panel.index = pd.to_datetime(panel.index)
    return panel.astype(float).sort_index().sort_index(axis=1)


def _normalize_long_short(raw: pd.DataFrame) -> pd.DataFrame:
    demeaned = raw.sub(raw.mean(axis=1), axis=0)
    gross = demeaned.abs().sum(axis=1).replace(0.0, np.nan)
    return demeaned.div(gross, axis=0).fillna(0.0)


def _top_bottom_decile_weights(scores: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    n_names = scores.shape[1]
    bucket = max(1, int(n_names * 0.1))
    for date, row in scores.iterrows():
        ranked = row.dropna().sort_values()
        if len(ranked) < 2 * bucket:
            continue
        shorts = ranked.index[:bucket]
        longs = ranked.index[-bucket:]
        weights.loc[date, longs] = 1.0 / bucket
        weights.loc[date, shorts] = -1.0 / bucket
    return weights
