"""Vectorized T+1 backtest engine for Pillar 6.1.

Time alignment contract:

    Decision at T: compute factor f(T) and target w(T) using data <= T
    Execution T+1: trade at T+1 OPEN to reach w(T)
    Hold T+1: position w(T) throughout the day
    Return T+1: r(T+1) = adj_close(T+1) / adj_close(T) - 1
    PnL T+1: w(T).dot(r(T+1)) - cost(T+1)

Implementation rule: use weights.shift(1) everywhere weights interact with
returns. This is non-negotiable because using w(T) against r(T) would allow
today's target, computed after observing data through T, to earn today's
close-to-close return.

Costs are decomposed into linear transaction cost plus optional square-root
impact. Linear cost is bps x |dw|. Impact is c x sigma x |dw| x
sqrt(|dw| x portfolio_size / ADV).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.pnl import compute_costs, compute_pnl
from src.backtest.rebalancer import apply_t1_execution, compute_trades


@dataclass(frozen=True)
class BacktestResult:
    pnl: pd.Series
    nav: pd.Series
    positions: pd.DataFrame
    trades: pd.DataFrame
    daily_cost: pd.Series


class VectorizedBacktester:
    """Run a vectorized close-to-close backtest from target weight and adj_close panels."""

    def __init__(
        self,
        target_weights: pd.DataFrame,
        prices: pd.DataFrame,
        cost_config: dict,
        adv: pd.DataFrame | None = None,
    ) -> None:
        self.target_weights = _coerce_panel(target_weights, "target_weights")
        self.prices = _coerce_price_panel(prices)
        self.cost_config = _default_cost_config() | dict(cost_config or {})
        self.adv = _coerce_panel(adv, "adv") if adv is not None else None

    def run(self) -> BacktestResult:
        weights, prices = self.target_weights.align(self.prices, join="inner", axis=0)
        weights, prices = weights.align(prices, join="inner", axis=1)
        returns = prices.pct_change(fill_method=None).fillna(0.0)
        decision_weights = weights.apply(apply_t1_execution, axis=1)
        positions = decision_weights.shift(1).fillna(0.0)
        current_weights = decision_weights.shift(1).fillna(0.0)
        trades = _shift_trades_to_execution_date(compute_trades(decision_weights, current_weights), decision_weights.index)
        daily_cost = compute_costs(trades, self.cost_config, self.adv, prices).reindex(returns.index, fill_value=0.0)
        gross_pnl = compute_pnl(decision_weights, returns)
        pnl = (gross_pnl - daily_cost).rename("pnl")
        nav = (1.0 + pnl).cumprod().rename("nav")
        trades = _attach_trade_costs(trades, daily_cost)
        return BacktestResult(pnl=pnl, nav=nav, positions=positions, trades=trades, daily_cost=daily_cost)


def _default_cost_config() -> dict:
    return {"linear_bps": 5.0, "impact_coefficient": 0.1, "use_sqrt_impact": True}


def _coerce_price_panel(prices: pd.DataFrame) -> pd.DataFrame:
    if isinstance(prices.index, pd.MultiIndex):
        if "adj_close" not in prices.columns:
            raise ValueError("prices must contain adj_close when provided in long form.")
        panel = prices["adj_close"].unstack("ticker")
    elif "adj_close" in prices.columns and {"date", "ticker"}.issubset(prices.columns):
        panel = prices.pivot(index="date", columns="ticker", values="adj_close")
    else:
        panel = prices.copy()
    return _coerce_panel(panel, "prices")


def _coerce_panel(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    if frame is None:
        raise ValueError(f"{name} is required")
    panel = frame.copy()
    panel.index = pd.to_datetime(panel.index)
    return panel.astype(float).sort_index().sort_index(axis=1)


def _attach_trade_costs(trades: pd.DataFrame, daily_cost: pd.Series) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["date", "symbol", "dw", "cost"])
    annotated = trades.copy()
    annotated["abs_dw"] = annotated["dw"].abs()
    daily_abs_dw = annotated.groupby("date")["abs_dw"].transform("sum").replace(0.0, pd.NA)
    annotated["daily_cost"] = annotated["date"].map(daily_cost)
    annotated["cost"] = (annotated["daily_cost"] * annotated["abs_dw"] / daily_abs_dw).fillna(0.0)
    return annotated.drop(columns=["abs_dw", "daily_cost"])


def _shift_trades_to_execution_date(trades: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
    if trades.empty:
        return trades
    execution_dates = pd.Series(index[1:], index=index[:-1])
    shifted = trades.copy()
    shifted["date"] = shifted["date"].map(execution_dates)
    return shifted.dropna(subset=["date"]).reset_index(drop=True)
