"""Risk neutralization tools for implementation-ready portfolios."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.ic_analysis import extract_daily_return_matrix


def build_out_of_portfolio_market_proxy(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    """Build an equal-weight market proxy excluding current portfolio names."""
    returns = extract_daily_return_matrix(prices).reindex(index=weights.index, columns=weights.columns)
    in_portfolio = weights.fillna(0.0).ne(0.0)
    proxy_returns = returns.where(~in_portfolio).mean(axis=1, skipna=True).rename("market_proxy_return")
    proxy_returns.index.name = "date"
    return proxy_returns.astype(float)


def compute_rolling_betas(
    prices: pd.DataFrame,
    market_proxy: pd.Series,
    lookback: int = 60,
) -> pd.DataFrame:
    """Estimate lagged rolling beta for every stock against the market proxy."""
    if lookback < 3:
        raise ValueError("lookback must be at least 3.")
    returns = extract_daily_return_matrix(prices)
    market = market_proxy.reindex(returns.index).astype(float)
    market_mean = market.rolling(lookback, min_periods=lookback).mean()
    return_mean = returns.rolling(lookback, min_periods=lookback).mean()
    covariance = returns.mul(market, axis=0).rolling(lookback, min_periods=lookback).mean().sub(return_mean.mul(market_mean, axis=0))
    market_variance = market.pow(2).rolling(lookback, min_periods=lookback).mean() - market_mean.pow(2)
    betas = covariance.div(market_variance, axis=0).shift(1)
    betas.index.name = "date"
    return betas.replace([np.inf, -np.inf], np.nan)


def beta_neutralize_weights(weights: pd.DataFrame, betas: pd.DataFrame) -> pd.DataFrame:
    """Scale long and short books so ex-ante beta is approximately zero."""
    aligned_betas = betas.reindex(index=weights.index, columns=weights.columns)
    rows = [_neutralize_one_date(weights.loc[date], aligned_betas.loc[date]) for date in weights.index]
    neutralized = pd.DataFrame(rows, index=weights.index, columns=weights.columns)
    return _normalize_long_short(neutralized)


def apply_sector_cap(weights: pd.DataFrame, sectors: pd.Series, cap: float = 0.25) -> pd.DataFrame:
    """Cap long and short sector exposure separately and renormalize each side."""
    if not 0.0 < cap <= 1.0:
        raise ValueError("cap must be in (0, 1].")
    capped = weights.apply(lambda row: _cap_one_date(row, sectors, cap), axis=1)
    return _normalize_long_short(capped)


def sector_cap_then_renormalize_beta(
    weights: pd.DataFrame,
    sectors: pd.Series,
    betas: pd.DataFrame,
    cap: float = 0.25,
) -> pd.DataFrame:
    """Apply a sector cap, then re-neutralize beta under dollar-neutral books."""
    capped = apply_sector_cap(weights, sectors, cap=cap)
    return beta_neutralize_weights(capped, betas)


def portfolio_ex_ante_beta(weights: pd.DataFrame, betas: pd.DataFrame) -> pd.Series:
    """Compute ex-ante portfolio beta from weights and stock betas."""
    aligned_betas = betas.reindex(index=weights.index, columns=weights.columns)
    return (weights * aligned_betas).sum(axis=1, min_count=1).rename("ex_ante_beta")


def _neutralize_one_date(weight_row: pd.Series, beta_row: pd.Series) -> pd.Series:
    clean_weights = weight_row.fillna(0.0).astype(float)
    clean_betas = beta_row.reindex(clean_weights.index).astype(float)
    if clean_weights.abs().sum() == 0.0 or clean_betas.dropna().empty:
        return clean_weights * np.nan
    long_weights = clean_weights.where(clean_weights > 0.0, 0.0)
    short_abs_weights = -clean_weights.where(clean_weights < 0.0, 0.0)
    long_beta = _side_beta(long_weights, clean_betas)
    short_beta = _side_beta(short_abs_weights, clean_betas)
    target_beta = _shared_target_beta(long_weights, short_abs_weights, clean_betas, long_beta, short_beta)
    if pd.isna(target_beta):
        return clean_weights
    adjusted_long = _tilt_side_to_beta(long_weights, clean_betas, target_beta)
    adjusted_short = _tilt_side_to_beta(short_abs_weights, clean_betas, target_beta)
    return adjusted_long - adjusted_short


def _side_beta(side_weights: pd.Series, betas: pd.Series) -> float:
    total = float(side_weights.sum())
    if total <= 0.0:
        return float("nan")
    return float((side_weights * betas).sum(skipna=True) / total)


def _shared_target_beta(
    long_weights: pd.Series,
    short_weights: pd.Series,
    betas: pd.Series,
    long_beta: float,
    short_beta: float,
) -> float:
    long_betas = betas[long_weights > 0.0].dropna()
    short_betas = betas[short_weights > 0.0].dropna()
    if long_betas.empty or short_betas.empty:
        return float("nan")
    lower_bound = max(float(long_betas.min()), float(short_betas.min()))
    upper_bound = min(float(long_betas.max()), float(short_betas.max()))
    target = (long_beta + short_beta) / 2.0
    if lower_bound <= upper_bound:
        return float(np.clip(target, lower_bound, upper_bound))
    return float(np.clip(target, float(short_betas.min()), float(long_betas.max())))


def _tilt_side_to_beta(side_weights: pd.Series, betas: pd.Series, target_beta: float) -> pd.Series:
    active = side_weights[side_weights > 0.0].copy()
    result = pd.Series(0.0, index=side_weights.index, dtype=float)
    if active.empty:
        return result
    active_betas = betas.reindex(active.index).astype(float)
    if active_betas.dropna().shape[0] < 2:
        result.loc[active.index] = active / active.sum()
        return result
    base = active / active.sum()
    feasible_target = float(np.clip(target_beta, float(active_betas.min()), float(active_betas.max())))
    adjusted = _project_to_beta_simplex(base, active_betas, feasible_target)
    result.loc[adjusted.index] = adjusted
    return result


def _project_to_beta_simplex(base: pd.Series, betas: pd.Series, target_beta: float) -> pd.Series:
    """Find the closest non-negative weights with sum 1 and target beta."""
    active = base[base > 0.0].copy()
    active_betas = betas.reindex(active.index).astype(float)
    for _ in range(len(active) + 1):
        if active.empty:
            break
        centered = active_betas - active_betas.mean()
        current_beta = float((active * active_betas).sum())
        gap = current_beta - target_beta
        denominator = float((centered * active_betas).sum())
        if abs(gap) < 1e-10 or abs(denominator) < 1e-12:
            break
        candidate = active - gap * centered / denominator
        negative_names = candidate[candidate < 0.0].index
        if negative_names.empty:
            return candidate / candidate.sum()
        active = candidate.drop(index=negative_names)
        active = active.clip(lower=0.0)
        if active.sum() > 0.0:
            active /= active.sum()
        active_betas = active_betas.drop(index=negative_names)
    if active.empty:
        active = base.copy()
    return active.clip(lower=0.0) / active.clip(lower=0.0).sum()


def _normalize_long_short(weights: pd.DataFrame) -> pd.DataFrame:
    normalized = weights.copy().astype(float)
    long_sum = normalized.where(normalized > 0.0, 0.0).sum(axis=1).replace(0.0, np.nan)
    short_sum = -normalized.where(normalized < 0.0, 0.0).sum(axis=1).replace(0.0, np.nan)
    positive = normalized.where(normalized > 0.0, 0.0).div(long_sum, axis=0)
    negative = normalized.where(normalized < 0.0, 0.0).div(short_sum, axis=0)
    return (positive + negative).replace([np.inf, -np.inf], np.nan)


def _cap_one_date(weight_row: pd.Series, sectors: pd.Series, cap: float) -> pd.Series:
    capped_long = _cap_side(weight_row.where(weight_row > 0.0, 0.0), sectors, cap)
    capped_short = -_cap_side((-weight_row.where(weight_row < 0.0, 0.0)), sectors, cap)
    return capped_long + capped_short


def _cap_side(side_weights: pd.Series, sectors: pd.Series, cap: float) -> pd.Series:
    output = side_weights.fillna(0.0).astype(float).copy()
    total = float(output.sum())
    if total <= 0.0:
        return output
    normalized = output / total
    sector_labels = sectors.reindex(normalized.index).fillna("Unknown")
    sector_weights = normalized.groupby(sector_labels).sum()
    capped_sector_weights = _cap_sector_allocations(sector_weights, cap)
    result = normalized.copy() * 0.0
    for sector_name, sector_weight in capped_sector_weights.items():
        names = sector_labels[sector_labels == sector_name].index
        original_total = float(normalized.loc[names].sum())
        if original_total > 0.0:
            result.loc[names] = normalized.loc[names] / original_total * float(sector_weight)
    return result


def _cap_sector_allocations(sector_weights: pd.Series, cap: float) -> pd.Series:
    allocations = sector_weights.astype(float).copy()
    fixed = pd.Series(False, index=allocations.index)
    for _ in range(len(allocations) + 1):
        over_cap = (allocations > cap) & (~fixed)
        if not over_cap.any():
            break
        excess = float((allocations[over_cap] - cap).sum())
        allocations.loc[over_cap] = cap
        fixed.loc[over_cap] = True
        receivers = ~fixed
        receiver_total = float(allocations[receivers].sum())
        if receiver_total <= 0.0:
            break
        allocations.loc[receivers] += allocations.loc[receivers] / receiver_total * excess
    total = float(allocations.sum())
    if total > 0.0:
        allocations /= total
    return allocations
