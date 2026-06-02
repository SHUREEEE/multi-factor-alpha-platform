"""Transaction cost utilities for portfolio backtests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.quantile_test import TRADING_DAYS_PER_YEAR, compute_annualized_sharpe


def apply_linear_transaction_costs(daily_returns: pd.DataFrame, cost_bps: int) -> pd.DataFrame:
    """Apply a one-way linear transaction cost to daily long-short returns.

    Parameters
    ----------
    daily_returns:
        DataFrame containing ``long_short_return`` and ``turnover`` columns.
    cost_bps:
        One-way cost in basis points. For example, ``5`` means 5 bps per unit
        of turnover.

    Returns
    -------
    pandas.DataFrame
        Daily gross return, cost, net return, turnover, and net cumulative return.
    """
    _validate_cost_inputs(daily_returns, cost_bps)
    cost_rate = float(cost_bps) / 10000.0
    output = pd.DataFrame(index=daily_returns.index.copy())
    output["gross_return"] = daily_returns["long_short_return"].astype(float)
    output["turnover"] = daily_returns["turnover"].astype(float)
    output["transaction_cost"] = cost_rate * output["turnover"].fillna(0.0)
    output.loc[output["gross_return"].isna(), "transaction_cost"] = np.nan
    output["net_return"] = output["gross_return"] - output["transaction_cost"]
    output["net_cumulative_return"] = (1.0 + output["net_return"].fillna(0.0)).cumprod() - 1.0
    output.index.name = daily_returns.index.name
    return output


def summarize_net_returns(costed_returns: pd.DataFrame) -> dict[str, float | int]:
    """Summarize transaction-cost-adjusted daily returns."""
    _validate_summary_inputs(costed_returns)
    returns = costed_returns["net_return"].replace([np.inf, -np.inf], np.nan).dropna()
    cumulative = costed_returns["net_cumulative_return"].replace([np.inf, -np.inf], np.nan)
    return {
        "annualized_return": _annualized_return(returns),
        "annualized_sharpe": compute_annualized_sharpe(returns),
        "max_drawdown": _max_drawdown(cumulative),
        "average_daily_turnover": float(costed_returns["turnover"].mean(skipna=True)),
        "hit_rate": float((returns > 0.0).mean()) if not returns.empty else float("nan"),
        "net_cumulative_return": float(cumulative.dropna().iloc[-1]) if not cumulative.dropna().empty else float("nan"),
        "average_daily_cost": float(costed_returns["transaction_cost"].mean(skipna=True)),
        "n_days": int(returns.shape[0]),
    }


def _validate_cost_inputs(daily_returns: pd.DataFrame, cost_bps: int) -> None:
    if not isinstance(daily_returns, pd.DataFrame):
        raise TypeError("daily_returns must be a pandas DataFrame.")
    missing_columns = sorted({"long_short_return", "turnover"} - set(daily_returns.columns))
    if missing_columns:
        raise ValueError(f"daily_returns missing required columns: {missing_columns}")
    if not isinstance(cost_bps, int) or cost_bps < 0:
        raise ValueError("cost_bps must be a non-negative integer.")


def _validate_summary_inputs(costed_returns: pd.DataFrame) -> None:
    if not isinstance(costed_returns, pd.DataFrame):
        raise TypeError("costed_returns must be a pandas DataFrame.")
    missing_columns = sorted({"net_return", "turnover", "transaction_cost", "net_cumulative_return"} - set(costed_returns.columns))
    if missing_columns:
        raise ValueError(f"costed_returns missing required columns: {missing_columns}")


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
