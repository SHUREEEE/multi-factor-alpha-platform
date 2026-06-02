"""V4 slippage attribution against square-root impact model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SlippageAttributionResult:
    """Slippage attribution detail and aggregate diagnostics."""

    detail: pd.DataFrame
    by_sector: pd.DataFrame
    total_modeled_bps: float
    total_realized_bps: float
    total_residual_bps: float
    tail_rotation_day_residual_bps: float | None
    missing_inputs_symbols: list[str]
    notional_weighted: bool = True
    impact_coefficient: float = 0.1


def attribute_slippage_vs_model(
    target_weights: pd.Series,
    current_weights: pd.Series,
    adv20_usd: pd.Series,
    daily_vol: pd.Series,
    realized_slippage_bps: pd.Series,
    sectors: pd.Series,
    *,
    aum_usd: float,
    gross: float,
    impact_coefficient: float = 0.1,
    rotation_day_tag: bool = False,
) -> SlippageAttributionResult:
    """Attribute realized slippage versus modeled square-root impact."""
    if aum_usd <= 0.0:
        raise ValueError("aum_usd must be positive.")
    if gross <= 0.0:
        raise ValueError("gross must be positive.")
    if impact_coefficient < 0.0:
        raise ValueError("impact_coefficient must be non-negative.")

    symbols = target_weights.index.union(current_weights.index).union(realized_slippage_bps.index)
    target = target_weights.reindex(symbols).fillna(0.0).astype(float)
    current = current_weights.reindex(symbols).fillna(0.0).astype(float)
    adv = adv20_usd.reindex(symbols).astype(float)
    vol = daily_vol.reindex(symbols).astype(float)
    realized = realized_slippage_bps.reindex(symbols).astype(float)
    order_notional = (target - current).abs() * float(aum_usd) * float(gross)
    missing = adv.isna() | (adv <= 0.0) | vol.isna() | realized.isna()
    participation = order_notional / adv.where(~missing)
    modeled = float(impact_coefficient) * vol * np.sqrt(participation.clip(lower=0.0)) * 10000.0
    residual = realized - modeled
    zero_trade = order_notional == 0.0
    modeled.loc[zero_trade] = 0.0
    residual.loc[zero_trade] = np.nan
    residual.loc[missing] = np.nan

    detail = pd.DataFrame(
        {
            "symbol": symbols,
            "sector": sectors.reindex(symbols).fillna("Unknown").to_numpy(),
            "order_notional": order_notional.to_numpy(dtype=float),
            "participation": participation.to_numpy(dtype=float, na_value=np.nan),
            "daily_vol": vol.to_numpy(dtype=float, na_value=np.nan),
            "modeled_impact_bps": modeled.to_numpy(dtype=float, na_value=np.nan),
            "realized_slippage_bps": realized.to_numpy(dtype=float, na_value=np.nan),
            "residual_bps": residual.to_numpy(dtype=float, na_value=np.nan),
            "rotation_day_tag": bool(rotation_day_tag),
            "requirement": "REQ-F-011",
        }
    )
    detail["status"] = np.where(detail["residual_bps"].abs() <= detail["modeled_impact_bps"].abs().clip(lower=1.0), "PASS", "WARN")
    detail.loc[detail["residual_bps"].isna(), "status"] = "MISSING_INPUT"
    traded = detail[(detail["order_notional"] > 0.0) & detail["residual_bps"].notna()]
    total_modeled = _weighted_average(traded, "modeled_impact_bps")
    total_realized = _weighted_average(traded, "realized_slippage_bps")
    total_residual = _weighted_average(traded, "residual_bps")
    return SlippageAttributionResult(
        detail=detail,
        by_sector=_sector_aggregate(traded),
        total_modeled_bps=total_modeled,
        total_realized_bps=total_realized,
        total_residual_bps=total_residual,
        tail_rotation_day_residual_bps=total_residual if rotation_day_tag else None,
        missing_inputs_symbols=sorted(symbols[missing].astype(str).tolist()),
        impact_coefficient=float(impact_coefficient),
    )


def _weighted_average(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return 0.0
    total = float(frame["order_notional"].sum())
    if total <= 0.0:
        return 0.0
    return float((frame[column] * frame["order_notional"]).sum() / total)


def _sector_aggregate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["sector", "order_notional", "modeled_impact_bps", "realized_slippage_bps", "residual_bps"])
    rows = []
    for sector, group in frame.groupby("sector"):
        rows.append(
            {
                "sector": sector,
                "order_notional": float(group["order_notional"].sum()),
                "modeled_impact_bps": _weighted_average(group, "modeled_impact_bps"),
                "realized_slippage_bps": _weighted_average(group, "realized_slippage_bps"),
                "residual_bps": _weighted_average(group, "residual_bps"),
            }
        )
    return pd.DataFrame(rows)
