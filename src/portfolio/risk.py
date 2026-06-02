"""Risk sizing and drawdown utilities for production portfolio analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.quantile_test import TRADING_DAYS_PER_YEAR, compute_annualized_sharpe


def annualized_volatility(returns: pd.Series) -> float:
    """Return annualized sample volatility for a daily return series."""
    clean = _clean_returns(returns)
    if clean.shape[0] < 2:
        return float("nan")
    return float(clean.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def scale_return_stream(daily_returns: pd.DataFrame, leverage_scaler: float, cost_bps: int) -> pd.DataFrame:
    """Scale gross returns and turnover, then apply linear transaction costs."""
    if leverage_scaler < 0.0:
        raise ValueError("leverage_scaler must be non-negative.")
    if cost_bps < 0:
        raise ValueError("cost_bps must be non-negative.")
    missing = sorted({"long_short_return", "turnover"} - set(daily_returns.columns))
    if missing:
        raise ValueError(f"daily_returns missing required columns: {missing}")
    output = pd.DataFrame(index=daily_returns.index.copy())
    output["gross_return"] = daily_returns["long_short_return"].astype(float) * leverage_scaler
    output["turnover"] = daily_returns["turnover"].astype(float) * leverage_scaler
    output["transaction_cost"] = output["turnover"].fillna(0.0) * (float(cost_bps) / 10000.0)
    output.loc[output["gross_return"].isna(), "transaction_cost"] = np.nan
    output["net_return"] = output["gross_return"] - output["transaction_cost"]
    output["net_cumulative_return"] = (1.0 + output["net_return"].fillna(0.0)).cumprod() - 1.0
    output.index.name = daily_returns.index.name
    return output


def summarize_return_stream(returns: pd.Series) -> dict[str, float | int]:
    """Summarize a daily return stream with production risk metrics."""
    clean = _clean_returns(returns)
    cumulative = (1.0 + returns.fillna(0.0)).cumprod() - 1.0
    return {
        "ann_return": _annualized_return(clean),
        "ann_sharpe": compute_annualized_sharpe(clean),
        "max_dd": max_drawdown(returns),
        "dd_duration_days": max_drawdown_duration_days(returns),
        "hit_rate": float((clean > 0.0).mean()) if not clean.empty else float("nan"),
        "ann_vol_realized": annualized_volatility(clean),
        "net_cumulative_return": float(cumulative.dropna().iloc[-1]) if not cumulative.dropna().empty else float("nan"),
        "n_days": int(clean.shape[0]),
    }


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Compute drawdown as wealth divided by running high-water mark minus one."""
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    drawdown.name = "drawdown"
    return drawdown


def max_drawdown(returns: pd.Series) -> float:
    """Return maximum drawdown for daily returns."""
    drawdown = drawdown_series(returns)
    if drawdown.empty:
        return float("nan")
    return float(drawdown.min())


def max_drawdown_duration_days(returns: pd.Series) -> int:
    """Return the longest number of observations spent below a prior high."""
    drawdown = drawdown_series(returns)
    longest = 0
    current = 0
    for value in drawdown.fillna(0.0):
        if value < 0.0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def drawdown_events(returns: pd.Series) -> pd.DataFrame:
    """Extract peak-to-trough drawdown events from a daily return series."""
    clean = returns.fillna(0.0)
    if clean.empty:
        return pd.DataFrame(
            columns=["start_date", "trough_date", "recovery_date", "peak_to_trough", "drawdown_duration_days", "recovery_duration_days"]
        )
    wealth = (1.0 + clean).cumprod()
    running_peak = wealth.cummax()
    underwater = wealth < running_peak
    rows: list[dict[str, object]] = []
    dates = list(clean.index)
    i = 0
    while i < len(dates):
        if not bool(underwater.iloc[i]):
            i += 1
            continue
        start_pos = max(i - 1, 0)
        trough_pos = i
        while i < len(dates) and bool(underwater.iloc[i]):
            if wealth.iloc[i] < wealth.iloc[trough_pos]:
                trough_pos = i
            i += 1
        recovery_pos = i if i < len(dates) else None
        rows.append(
            {
                "start_date": pd.Timestamp(dates[start_pos]),
                "trough_date": pd.Timestamp(dates[trough_pos]),
                "recovery_date": pd.Timestamp(dates[recovery_pos]) if recovery_pos is not None else pd.NaT,
                "peak_to_trough": float(wealth.iloc[trough_pos] / wealth.iloc[start_pos] - 1.0),
                "drawdown_duration_days": int(trough_pos - start_pos),
                "recovery_duration_days": int(recovery_pos - trough_pos) if recovery_pos is not None else pd.NA,
            }
        )
    return pd.DataFrame(rows)


def slice_returns_window(returns: pd.Series, start_date: str, end_date: str) -> pd.Series:
    """Slice returns inclusively between two date strings."""
    clean = returns.sort_index()
    return clean.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]


def realized_beta(portfolio_returns: pd.Series, market_returns: pd.Series) -> float:
    """Compute realized beta of portfolio returns to a market return proxy."""
    paired = pd.concat([portfolio_returns, market_returns], axis=1, keys=["portfolio", "market"]).dropna()
    if paired.shape[0] < 3:
        return float("nan")
    variance = float(paired["market"].var(ddof=1))
    if variance == 0.0:
        return float("nan")
    return float(paired["portfolio"].cov(paired["market"]) / variance)


def _annualized_return(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    total_return = float((1.0 + returns).prod() - 1.0)
    years = returns.shape[0] / TRADING_DAYS_PER_YEAR
    if years <= 0.0:
        return float("nan")
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def _clean_returns(returns: pd.Series) -> pd.Series:
    return returns.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
