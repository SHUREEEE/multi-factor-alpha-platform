"""V4 participation-cap checks."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ParticipationResult:
    """Name-level participation check and aggregate capacity statistics."""

    detail: pd.DataFrame
    p50: float | None
    p95: float | None
    max: float | None
    breached_symbols: list[str]
    missing_adv_symbols: list[str]
    any_breach: bool
    aggregate_gross_used: float


def check_order_participation(
    target_weights: pd.Series,
    current_weights: pd.Series,
    adv20_usd: pd.Series,
    *,
    aum_usd: float,
    gross: float,
    max_participation: float = 0.05,
) -> ParticipationResult:
    """Return order participation detail and p50/p95/max diagnostics."""
    if aum_usd <= 0.0:
        raise ValueError("aum_usd must be positive.")
    if gross <= 0.0:
        raise ValueError("gross must be positive.")
    if max_participation <= 0.0:
        raise ValueError("max_participation must be positive.")

    symbols = target_weights.index.union(current_weights.index).union(adv20_usd.index)
    target = target_weights.reindex(symbols).fillna(0.0).astype(float)
    current = current_weights.reindex(symbols).fillna(0.0).astype(float)
    adv = adv20_usd.reindex(symbols).astype(float)
    order_notional = (target - current).abs() * float(aum_usd) * float(gross)
    missing_adv = adv.isna() | (adv <= 0.0)
    participation = (order_notional / adv.where(~missing_adv)).fillna(pd.NA)

    detail = pd.DataFrame(
        {
            "symbol": symbols,
            "order_notional": order_notional.to_numpy(dtype=float),
            "adv20_usd": adv.to_numpy(dtype=float),
            "participation": participation.to_numpy(dtype=float, na_value=float("nan")),
        }
    )
    detail["pass_fail"] = True
    detail["reason"] = "PASS"
    missing_rows = missing_adv.to_numpy(dtype=bool)
    detail.loc[missing_rows, "pass_fail"] = False
    detail.loc[missing_rows, "reason"] = "MISSING_ADV20"
    breach_rows = (detail["participation"] > max_participation).fillna(False)
    detail.loc[breach_rows, "pass_fail"] = False
    detail.loc[breach_rows, "reason"] = "PARTICIPATION_BREACH"
    zero_trade = detail["order_notional"] == 0.0
    detail.loc[zero_trade & ~missing_rows, "participation"] = 0.0
    detail.loc[zero_trade & ~missing_rows, "pass_fail"] = True
    detail.loc[zero_trade & ~missing_rows, "reason"] = "NO_TRADE"

    traded = detail[detail["order_notional"] > 0.0]
    traded_participation = traded["participation"].dropna()
    p50 = float(traded_participation.quantile(0.50)) if not traded_participation.empty else None
    p95 = float(traded_participation.quantile(0.95)) if not traded_participation.empty else None
    max_value = float(traded_participation.max()) if not traded_participation.empty else None
    breached = sorted(detail.loc[breach_rows, "symbol"].astype(str).tolist())
    missing = sorted(detail.loc[missing_rows, "symbol"].astype(str).tolist())
    return ParticipationResult(
        detail=detail,
        p50=p50,
        p95=p95,
        max=max_value,
        breached_symbols=breached,
        missing_adv_symbols=missing,
        any_breach=bool(breached or missing),
        aggregate_gross_used=float(gross),
    )
