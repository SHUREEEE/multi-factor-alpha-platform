"""Return attribution helpers for portfolio risk decomposition."""

from __future__ import annotations

import numpy as np
import pandas as pd


def factor_residual_decomposition(total: pd.Series, components: pd.DataFrame) -> pd.DataFrame:
    """Append residual so row-wise components reconcile to total returns."""
    if not isinstance(total, pd.Series):
        raise TypeError("total must be a pandas Series.")
    if not isinstance(components, pd.DataFrame):
        raise TypeError("components must be a pandas DataFrame.")
    aligned_total = total.astype(float).sort_index()
    aligned_components = components.astype(float).reindex(aligned_total.index).fillna(0.0)
    output = aligned_components.copy()
    output["residual_alpha_pnl"] = aligned_total - output.sum(axis=1)
    output["total_pnl"] = aligned_total
    return output


def variance_contribution_shares(total: pd.Series, components: pd.DataFrame) -> pd.Series:
    """Estimate component variance shares using covariance with total return."""
    paired = pd.concat([total.rename("total"), components], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if paired.empty:
        return pd.Series(dtype=float)
    total_var = float(paired["total"].var(ddof=1))
    if total_var == 0.0 or np.isnan(total_var):
        return pd.Series(np.nan, index=components.columns, dtype=float)
    shares = paired.drop(columns=["total"]).apply(lambda col: float(col.cov(paired["total"]) / total_var))
    shares.name = "variance_share"
    return shares


def rolling_realized_beta(portfolio_returns: pd.Series, market_returns: pd.Series, window: int = 60) -> pd.Series:
    """Compute rolling realized beta of a return stream to a market proxy."""
    if window < 3:
        raise ValueError("window must be at least 3.")
    paired = pd.concat([portfolio_returns, market_returns], axis=1, keys=["portfolio", "market"]).astype(float)
    cov = paired["portfolio"].rolling(window, min_periods=window).cov(paired["market"])
    var = paired["market"].rolling(window, min_periods=window).var()
    beta = cov.div(var.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    beta.name = f"rolling_{window}d_beta"
    return beta


def sector_net_exposures(weights: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    """Aggregate date-by-ticker weights into date-by-sector net exposures."""
    labels = sectors.reindex(weights.columns).fillna("Unknown")
    exposures = weights.fillna(0.0).T.groupby(labels).sum().T
    exposures.index.name = weights.index.name
    return exposures.sort_index(axis=1)


def sector_active_pnl(
    weights: pd.DataFrame,
    ticker_returns: pd.DataFrame,
    sectors: pd.Series,
    market_returns: pd.Series,
) -> pd.DataFrame:
    """Attribute sector active PnL from sector net weights times sector return spreads."""
    labels = sectors.reindex(weights.columns).fillna("Unknown")
    aligned_weights = weights.fillna(0.0).reindex(index=ticker_returns.index, columns=ticker_returns.columns).fillna(0.0)
    sector_exposure = sector_net_exposures(aligned_weights, labels)
    sector_returns = ticker_returns.reindex(columns=aligned_weights.columns).T.groupby(labels).mean().T
    sector_spreads = sector_returns.sub(market_returns.reindex(sector_returns.index), axis=0)
    pnl = sector_exposure.reindex(columns=sector_spreads.columns).mul(sector_spreads, axis=0)
    pnl.columns = [f"sector_pnl__{column}" for column in pnl.columns]
    return pnl

