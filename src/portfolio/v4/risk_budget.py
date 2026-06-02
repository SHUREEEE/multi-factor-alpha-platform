"""V4 historical VaR and expected shortfall budgets."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class VarEsBudgetResult:
    """Historical VaR/ES budget state for one as-of date."""

    var: dict[float, float]
    es: dict[float, float]
    realized_return: float
    breach_flags: dict[str, bool]
    window_used: int
    warmup: bool
    method: str = "historical"


def compute_var_es_budget(
    portfolio_returns_history: pd.Series,
    *,
    asof_date,
    window: int = 252,
    confidence_levels: tuple[float, ...] = (0.95, 0.99),
    var_budget_95: float | None = None,
    var_budget_99: float | None = None,
    es_budget_95: float | None = None,
    es_budget_99: float | None = None,
    min_obs: int = 252,
) -> VarEsBudgetResult:
    """Compute one-date historical VaR/ES and optional budget breaches."""
    if window <= 1:
        raise ValueError("window must be greater than 1.")
    if min_obs <= 0:
        raise ValueError("min_obs must be positive.")
    if any(level <= 0.0 or level >= 1.0 for level in confidence_levels):
        raise ValueError("confidence levels must be in (0, 1).")

    clean = portfolio_returns_history.astype(float).sort_index()
    asof = pd.Timestamp(asof_date)
    if asof not in clean.index:
        raise KeyError(f"asof_date {asof} not found in portfolio_returns_history.")
    history = clean.loc[:asof].dropna().tail(window)
    realized = float(clean.loc[asof])
    warmup = len(history) < min_obs
    var: dict[float, float] = {}
    es: dict[float, float] = {}
    flags: dict[str, bool] = {}
    budgets = {
        "var_95": var_budget_95,
        "var_99": var_budget_99,
        "es_95": es_budget_95,
        "es_99": es_budget_99,
    }

    for level in confidence_levels:
        alpha = 1.0 - level
        var_value = float(history.quantile(alpha)) if not history.empty else float("nan")
        tail = history[history <= var_value]
        es_value = float(tail.mean()) if len(tail) > 1 else var_value
        var[level] = var_value
        es[level] = es_value
        label = int(round(level * 100))
        flags[f"var_{label}"] = False if warmup or budgets.get(f"var_{label}") is None else var_value < float(budgets[f"var_{label}"])
        flags[f"es_{label}"] = False if warmup or budgets.get(f"es_{label}") is None else es_value < float(budgets[f"es_{label}"])

    return VarEsBudgetResult(
        var=var,
        es=es,
        realized_return=realized,
        breach_flags=flags,
        window_used=len(history),
        warmup=warmup,
    )
