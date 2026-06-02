"""PnL, cost, and metric utilities for a T+1 vectorized backtest.

Time alignment convention:

    Decision T  ->  Execution T+1 OPEN  ->  Hold T+1  ->  Return T+1  ->  PnL T+1
    w(T) made      trade to w(T)           own w(T)      close/close     w(T) * r(T+1)
    with data <=T

weights.shift(1) is non-negotiable whenever weights interact with returns.
It means today's close-to-close return is earned by yesterday's decided
portfolio, not by weights that could only be known after today's signal run.

Costs are decomposed into linear trading cost and square-root impact. Linear
cost is bps x |dw|. Impact is c x sigma x |dw| x sqrt(|dw| x portfolio_size / ADV).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252
DEFAULT_PORTFOLIO_SIZE = 1.0


def compute_pnl(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.Series:
    """Compute gross daily PnL using weights.shift(1) to enforce T+1 alignment."""

    aligned_weights, aligned_returns = weights.align(returns, join="inner", axis=0)
    aligned_weights, aligned_returns = aligned_weights.align(aligned_returns, join="inner", axis=1)
    pnl = aligned_weights.shift(1).fillna(0.0).mul(aligned_returns.fillna(0.0)).sum(axis=1)
    pnl.name = "pnl"
    return pnl


def compute_costs(
    trades: pd.DataFrame,
    cost_config: dict,
    adv: pd.DataFrame | None,
    prices: pd.DataFrame,
) -> pd.Series:
    """Compute daily transaction costs from a long-form trade blotter."""

    if trades.empty:
        index = _price_index(prices)
        return pd.Series(0.0, index=index, name="daily_cost")

    required = {"date", "symbol", "dw"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"trades missing required columns: {sorted(missing)}")

    config = _default_cost_config() | dict(cost_config or {})
    trade_frame = trades.copy()
    trade_frame["date"] = pd.to_datetime(trade_frame["date"])
    trade_frame["abs_dw"] = trade_frame["dw"].astype(float).abs()
    trade_frame["linear_cost"] = (float(config["linear_bps"]) / 10_000.0) * trade_frame["abs_dw"]

    if bool(config.get("use_sqrt_impact", True)) and float(config.get("impact_coefficient", 0.0)) != 0.0:
        sigma = _return_sigma(prices)
        adv_panel = _coerce_panel(adv, "adv") if adv is not None else None
        trade_frame["impact_cost"] = [
            _impact_cost(row, sigma, adv_panel, float(config["impact_coefficient"]), float(config.get("portfolio_size", DEFAULT_PORTFOLIO_SIZE)))
            for row in trade_frame.itertuples(index=False)
        ]
    else:
        trade_frame["impact_cost"] = 0.0

    trade_frame["cost"] = trade_frame["linear_cost"] + trade_frame["impact_cost"]
    daily = trade_frame.groupby("date")["cost"].sum().sort_index()
    index = _price_index(prices).union(daily.index).sort_values()
    daily_cost = daily.reindex(index, fill_value=0.0)
    daily_cost.name = "daily_cost"
    return daily_cost


def compute_metrics(pnl: pd.Series) -> dict:
    """Return standard daily-return performance metrics."""

    clean = pnl.dropna().astype(float)
    if clean.empty:
        clean = pd.Series([0.0])

    nav = (1.0 + clean).cumprod()
    drawdown = 1.0 - nav / nav.cummax()
    max_drawdown = float(drawdown.max())
    annual_return = float(nav.iloc[-1] ** (TRADING_DAYS / len(clean)) - 1.0)
    annual_vol = float(clean.std(ddof=0) * math.sqrt(TRADING_DAYS))
    sharpe = _safe_ratio(float(clean.mean() * TRADING_DAYS), annual_vol)
    downside = clean[clean < 0.0]
    downside_vol = float(downside.std(ddof=0) * math.sqrt(TRADING_DAYS)) if not downside.empty else 0.0
    sortino = _safe_ratio(float(clean.mean() * TRADING_DAYS), downside_vol)
    calmar = _safe_ratio(annual_return, max_drawdown)
    wins = clean[clean > 0.0]
    losses = clean[clean < 0.0]
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0

    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "hit_rate": float((clean > 0.0).mean()),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_win_loss_ratio": _safe_ratio(avg_win, abs(avg_loss)),
        "turnover_annual_x": 0.0,
    }


def _default_cost_config() -> dict:
    return {"linear_bps": 5.0, "impact_coefficient": 0.1, "use_sqrt_impact": True}


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0 or not np.isfinite(denominator):
        return 0.0
    return float(numerator / denominator)


def _price_index(prices: pd.DataFrame) -> pd.DatetimeIndex:
    panel = _coerce_panel(prices, "prices")
    return pd.DatetimeIndex(panel.index)


def _return_sigma(prices: pd.DataFrame) -> pd.Series:
    panel = _coerce_panel(prices, "prices")
    returns = panel.pct_change(fill_method=None)
    sigma = returns.rolling(20, min_periods=2).std().shift(1)
    fallback = returns.std().replace(0.0, np.nan).fillna(0.0)
    return sigma.stack().fillna(fallback).fillna(0.0)


def _impact_cost(row, sigma: pd.Series, adv: pd.DataFrame | None, coefficient: float, portfolio_size: float) -> float:
    if adv is None:
        return 0.0
    date = row.date
    symbol = row.symbol
    adv_value = adv.at[date, symbol] if date in adv.index and symbol in adv.columns else np.nan
    if pd.isna(adv_value) or float(adv_value) <= 0.0:
        return 0.0
    sigma_value = sigma.get((date, symbol), 0.0)
    trade_notional = row.abs_dw * portfolio_size
    return float(coefficient * sigma_value * row.abs_dw * math.sqrt(trade_notional / float(adv_value)))


def _coerce_panel(frame: pd.DataFrame | None, name: str) -> pd.DataFrame:
    if frame is None:
        raise ValueError(f"{name} is required")
    if isinstance(frame.index, pd.MultiIndex):
        value_column = "adj_close" if "adj_close" in frame.columns else frame.columns[0]
        panel = frame[value_column].unstack("ticker")
    elif "adj_close" in frame.columns and {"date", "ticker"}.issubset(frame.columns):
        panel = frame.pivot(index="date", columns="ticker", values="adj_close")
    else:
        panel = frame.copy()
    panel.index = pd.to_datetime(panel.index)
    return panel.astype(float).sort_index().sort_index(axis=1)
