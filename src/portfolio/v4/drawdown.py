"""V4 multi-tier drawdown halt controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DrawdownHaltResult:
    """Drawdown halt state for one as-of date."""

    rolling_60d_drawdown: float
    single_day_return: float
    peak_to_current_drawdown: float
    tier: str
    sizing_factor: float
    risk_adds_blocked: bool
    next_day_order_block: bool
    terminal_kill_switch: bool
    review_required: bool
    reason: str


def evaluate_drawdown_halts(
    portfolio_returns_history: pd.Series,
    *,
    asof_date,
    soft_threshold: float = -0.10,
    hard_threshold: float = -0.15,
    single_day_threshold: float = -0.08,
    terminal_threshold: float = -0.20,
    rolling_window: int = 60,
    soft_sizing_factor: float = 0.50,
    incident_clearance: dict[str, Any] | None = None,
) -> DrawdownHaltResult:
    """Evaluate V4 soft, hard, single-day, and terminal drawdown tiers."""
    if rolling_window <= 0:
        raise ValueError("rolling_window must be positive.")
    if not terminal_threshold < hard_threshold < soft_threshold < 0.0:
        raise ValueError("drawdown thresholds must satisfy terminal < hard < soft < 0.")
    if single_day_threshold >= 0.0:
        raise ValueError("single_day_threshold must be negative.")
    if not 0.0 <= soft_sizing_factor <= 1.0:
        raise ValueError("soft_sizing_factor must be in [0, 1].")

    clean = portfolio_returns_history.astype(float).sort_index()
    asof = pd.Timestamp(asof_date)
    if asof not in clean.index:
        raise KeyError(f"asof_date {asof} not found in portfolio_returns_history.")

    history = clean.loc[:asof].dropna()
    single_day = float(clean.loc[asof])
    if len(history) < rolling_window:
        return DrawdownHaltResult(
            rolling_60d_drawdown=0.0,
            single_day_return=single_day,
            peak_to_current_drawdown=0.0,
            tier="NONE",
            sizing_factor=1.0,
            risk_adds_blocked=False,
            next_day_order_block=False,
            terminal_kill_switch=False,
            review_required=False,
            reason="INSUFFICIENT_HISTORY",
        )

    rolling_slice = history.tail(rolling_window)
    rolling_drawdown = _window_drawdown(rolling_slice)
    peak_to_current = _peak_to_current_drawdown(history)

    triggered: list[str] = []
    if peak_to_current <= terminal_threshold:
        triggered.append("terminal")
    if single_day <= single_day_threshold:
        triggered.append("single_day")
    if rolling_drawdown <= hard_threshold:
        triggered.append("hard")
    elif rolling_drawdown <= soft_threshold:
        triggered.append("soft")

    clearance = incident_clearance or {}
    single_day_cleared = _single_day_cleared(clearance, asof)
    soft_approved = bool(clearance.get("soft_review_approved", False))

    if "terminal" in triggered:
        tier, sizing = "TERMINAL", 0.0
    elif "single_day" in triggered:
        tier, sizing = "SINGLE_DAY", 0.0
    elif "hard" in triggered:
        tier, sizing = "HARD", 0.0
    elif "soft" in triggered:
        tier, sizing = "SOFT", 1.0 if soft_approved else float(soft_sizing_factor)
    else:
        tier, sizing = "NONE", 1.0

    next_day_block = tier == "SINGLE_DAY" and not single_day_cleared
    return DrawdownHaltResult(
        rolling_60d_drawdown=rolling_drawdown,
        single_day_return=single_day,
        peak_to_current_drawdown=peak_to_current,
        tier=tier,
        sizing_factor=sizing,
        risk_adds_blocked=tier in {"HARD", "SINGLE_DAY", "TERMINAL"},
        next_day_order_block=next_day_block,
        terminal_kill_switch=tier == "TERMINAL",
        review_required=tier != "NONE",
        reason=";".join(triggered) if triggered else "NO_DRAWDOWN_HALT",
    )


def _window_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    running_peak = wealth.cummax()
    return float((wealth / running_peak - 1.0).min())


def _peak_to_current_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    return float(wealth.iloc[-1] / wealth.cummax().max() - 1.0)


def _single_day_cleared(clearance: dict[str, Any], asof: pd.Timestamp) -> bool:
    cleared_through = clearance.get("single_day_cleared_through")
    if cleared_through is None:
        return False
    return pd.Timestamp(cleared_through) >= asof + pd.offsets.BDay(1)
