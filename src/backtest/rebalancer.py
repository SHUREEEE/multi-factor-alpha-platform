"""Backtest rebalancing utilities with strict T+1 execution discipline.

Time alignment convention:

    Decision T  ->  Execution T+1 OPEN  ->  Hold T+1  ->  Return T+1  ->  PnL T+1
    w(T) made      trade to w(T)           own w(T)      close/close     w(T) * r(T+1)
    with data <=T

Weights decided at T are applied at T+1 OPEN. When weights interact with
returns, the PnL layer must therefore use weights.shift(1). That shift is
non-negotiable because same-day weights times same-day returns would create
lookahead bias.

Costs are decomposed downstream as linear transaction cost plus optional
square-root market impact: linear bps times absolute weight change, plus an
impact term driven by volatility, trade notional, and ADV.
"""

from __future__ import annotations

import pandas as pd


def compute_trades(target_weights: pd.DataFrame, current_weights: pd.DataFrame) -> pd.DataFrame:
    """Return a long-form trade blotter from target and current weight panels."""

    target = target_weights.astype(float).sort_index().sort_index(axis=1).fillna(0.0)
    current = current_weights.reindex(index=target.index, columns=target.columns).astype(float).fillna(0.0)
    delta = target - current
    trades = delta.stack().rename("dw").reset_index()
    trades.columns = ["date", "symbol", "dw"]
    return trades.loc[trades["dw"].abs() > 0].reset_index(drop=True)


def apply_t1_execution(target_weights_t: pd.Series) -> pd.Series:
    """Return weights decided at T for application at T+1 OPEN."""

    return target_weights_t.astype(float).fillna(0.0).copy()
