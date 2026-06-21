"""Regime-specific factor and portfolio validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.risk import realized_beta, summarize_return_stream
from src.research.ic_analysis import compute_ic_timeseries
from src.research.quantile_test import compute_long_short_return, quantile_portfolio_returns


def build_default_regimes(market_returns: pd.Series) -> pd.DataFrame:
    """Build price-only market regimes from a market return proxy."""
    if not isinstance(market_returns, pd.Series):
        raise TypeError("market_returns must be a pandas Series.")
    market = market_returns.astype(float).sort_index()
    rv20 = market.rolling(20, min_periods=20).std() * np.sqrt(252)
    trailing60 = (1.0 + market).rolling(60, min_periods=60).apply(np.prod, raw=True) - 1.0
    regimes = pd.DataFrame({"market_return": market, "realized_vol_20d": rv20, "trailing_return_60d": trailing60})
    regimes["full_sample"] = True
    regimes["high_vol"] = rv20 >= float(rv20.dropna().quantile(0.75)) if not rv20.dropna().empty else False
    regimes["low_vol"] = rv20 <= float(rv20.dropna().quantile(0.25)) if not rv20.dropna().empty else False
    regimes["market_drawdown"] = trailing60 <= float(trailing60.dropna().quantile(0.25)) if not trailing60.dropna().empty else False
    regimes["market_uptrend"] = trailing60 >= float(trailing60.dropna().quantile(0.75)) if not trailing60.dropna().empty else False
    regimes["covid_crash_2020"] = (regimes.index >= pd.Timestamp("2020-02-19")) & (regimes.index <= pd.Timestamp("2020-03-23"))
    regimes["rate_shock_2022"] = (regimes.index >= pd.Timestamp("2022-01-03")) & (regimes.index <= pd.Timestamp("2022-10-14"))
    return regimes


def summarize_portfolio_by_regime(portfolio_returns: pd.Series, market_returns: pd.Series, regimes: pd.DataFrame) -> pd.DataFrame:
    """Summarize portfolio return behavior inside each boolean regime column."""
    rows = []
    boolean_columns = [column for column in regimes.columns if regimes[column].dtype == bool]
    for regime_name in boolean_columns:
        mask = regimes[regime_name].reindex(portfolio_returns.index).fillna(False).astype(bool)
        returns = portfolio_returns.loc[mask]
        market = market_returns.reindex(returns.index)
        summary = summarize_return_stream(returns)
        rows.append(
            {
                "regime": regime_name,
                "n_days": summary["n_days"],
                "ann_return": summary["ann_return"],
                "ann_sharpe": summary["ann_sharpe"],
                "max_dd": summary["max_dd"],
                "hit_rate": summary["hit_rate"],
                "beta_to_market": realized_beta(returns, market),
            }
        )
    return pd.DataFrame(rows)


def summarize_factor_by_regime(
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    regimes: pd.DataFrame,
    *,
    n_quantiles: int = 10,
    already_shifted: bool = True,
) -> pd.DataFrame:
    """Compute IC and quantile spread diagnostics inside each regime."""
    ic_table = compute_ic_timeseries(factor_df, return_df, periods=[1], already_shifted=already_shifted)
    quantiles = quantile_portfolio_returns(factor_df, return_df, n_quantiles=n_quantiles, already_shifted=already_shifted)
    long_short = compute_long_short_return(quantiles)
    rows = []
    boolean_columns = [column for column in regimes.columns if regimes[column].dtype == bool]
    for regime_name in boolean_columns:
        mask = regimes[regime_name].reindex(ic_table.index).fillna(False).astype(bool)
        regime_ic = ic_table.loc[mask, "ic_1d"].replace([np.inf, -np.inf], np.nan).dropna()
        regime_ls = long_short.reindex(ic_table.index).loc[mask].replace([np.inf, -np.inf], np.nan).dropna()
        rows.append(
            {
                "regime": regime_name,
                "n_days": int(mask.sum()),
                "ic_mean_1d": float(regime_ic.mean()) if not regime_ic.empty else np.nan,
                "ic_hit_rate_1d": float((regime_ic > 0.0).mean()) if not regime_ic.empty else np.nan,
                "long_short_mean_1d": float(regime_ls.mean()) if not regime_ls.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)
