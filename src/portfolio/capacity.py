"""Capacity and live-readiness helpers for long-short portfolios."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_participation(weights: pd.DataFrame, adv20_usd: pd.DataFrame, aum_usd: float, gross: float) -> pd.DataFrame:
    """Compute per-name participation using AUM, gross, absolute weights, and ADV20."""
    if aum_usd < 0.0:
        raise ValueError("aum_usd must be non-negative.")
    if gross < 0.0:
        raise ValueError("gross must be non-negative.")
    aligned_weights, aligned_adv = weights.abs().align(adv20_usd, join="inner", axis=None)
    denominator = aligned_adv.replace(0.0, np.nan)
    return aligned_weights.mul(aum_usd * gross).div(denominator)


def compute_turnover_impact_cost(
    weights: pd.DataFrame,
    adv20_usd: pd.DataFrame,
    daily_vol: pd.DataFrame,
    aum_usd: float,
    gross: float,
    impact_coefficient: float,
) -> pd.Series:
    """Compute daily impact cost as impact on traded notional, not gross exposure."""
    if impact_coefficient < 0.0:
        raise ValueError("impact_coefficient must be non-negative.")
    participation = compute_participation(weights, adv20_usd, aum_usd, gross)
    aligned_vol = daily_vol.reindex(index=participation.index, columns=participation.columns)
    delta_weight = weights.fillna(0.0).diff().abs().reindex(index=participation.index, columns=participation.columns)
    if not delta_weight.empty:
        delta_weight.iloc[0] = np.nan
    impact_rate = impact_coefficient * aligned_vol * np.sqrt(participation.clip(lower=0.0))
    impact_cost = impact_rate.mul(delta_weight * gross).sum(axis=1, min_count=1)
    impact_cost.name = "daily_impact_cost"
    return impact_cost.replace([np.inf, -np.inf], np.nan)


def borrow_feasible_flag(htb_share: float, top10_short_concentration: float) -> bool:
    """Return whether borrow proxy constraints pass industry-rule thresholds."""
    return bool(htb_share < 0.30 and top10_short_concentration < 0.40)


def top_short_concentration(short_weights: pd.Series, top_n: int = 10) -> float:
    """Compute top-N short concentration as share of short book absolute notional."""
    short_abs = (-short_weights.where(short_weights < 0.0, 0.0)).dropna()
    total = float(short_abs.sum())
    if total <= 0.0:
        return float("nan")
    return float(short_abs.nlargest(top_n).sum() / total)
