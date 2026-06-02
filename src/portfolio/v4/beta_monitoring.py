"""V4 realized residual-beta monitoring."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


PASS = "PASS"
WARN = "WARN"
HARD_REVIEW = "HARD_REVIEW"


@dataclass(frozen=True)
class BetaMonitorResult:
    """Rolling realized beta monitor state."""

    beta: pd.Series
    abs_beta: pd.Series
    warning_flag: pd.Series
    hard_review_flag: pd.Series
    consecutive_breach_count: pd.Series
    window_label: str
    market_proxy_label: str
    warmup_dates: list[pd.Timestamp]


def compute_realized_beta_monitor_20d(
    portfolio_returns: pd.Series,
    market_returns: pd.Series,
    *,
    window: int = 20,
    warning_threshold: float = 0.30,
    hard_review_threshold: float = 0.50,
    hard_review_consecutive_days: int = 3,
    min_obs: int = 20,
    market_proxy_name: str = "SPY",
) -> BetaMonitorResult:
    """Compute the 20d realized beta monitor for fast dislocations."""
    return _compute_beta_monitor(
        portfolio_returns,
        market_returns,
        window=window,
        warning_threshold=warning_threshold,
        hard_review_threshold=hard_review_threshold,
        hard_review_consecutive_days=hard_review_consecutive_days,
        min_obs=min_obs,
        window_label="20d",
        market_proxy_name=market_proxy_name,
    )


def compute_realized_beta_monitor_60d(
    portfolio_returns: pd.Series,
    market_returns: pd.Series,
    *,
    window: int = 60,
    warning_threshold: float = 0.25,
    hard_review_threshold: float = 0.40,
    hard_review_consecutive_days: int = 5,
    min_obs: int = 60,
    market_proxy_name: str = "SPY",
) -> BetaMonitorResult:
    """Compute the 60d realized beta monitor for persistent drift."""
    return _compute_beta_monitor(
        portfolio_returns,
        market_returns,
        window=window,
        warning_threshold=warning_threshold,
        hard_review_threshold=hard_review_threshold,
        hard_review_consecutive_days=hard_review_consecutive_days,
        min_obs=min_obs,
        window_label="60d",
        market_proxy_name=market_proxy_name,
    )


def _compute_beta_monitor(
    portfolio_returns: pd.Series,
    market_returns: pd.Series,
    *,
    window: int,
    warning_threshold: float,
    hard_review_threshold: float,
    hard_review_consecutive_days: int,
    min_obs: int,
    window_label: str,
    market_proxy_name: str,
) -> BetaMonitorResult:
    if window < 3:
        raise ValueError("window must be at least 3.")
    if min_obs <= 0 or min_obs > window:
        raise ValueError("min_obs must be in (0, window].")
    if warning_threshold < 0.0 or hard_review_threshold < warning_threshold:
        raise ValueError("thresholds must be non-negative and ordered.")
    if hard_review_consecutive_days <= 0:
        raise ValueError("hard_review_consecutive_days must be positive.")
    if not portfolio_returns.index.equals(market_returns.index):
        raise ValueError("portfolio_returns and market_returns indexes must match.")

    portfolio = portfolio_returns.astype(float)
    market = market_returns.astype(float)
    valid = portfolio.notna() & market.notna()
    covariance = portfolio.rolling(window, min_periods=min_obs).cov(market)
    variance = market.rolling(window, min_periods=min_obs).var(ddof=1)
    beta = (covariance / variance).replace([float("inf"), float("-inf")], pd.NA).astype(float)
    beta.name = "beta"
    obs_count = valid.rolling(window, min_periods=1).sum()
    beta.loc[obs_count < min_obs] = pd.NA

    abs_beta = beta.abs().rename("abs_beta")
    warning_flag = (abs_beta > warning_threshold).fillna(False).astype(bool)
    hard_raw = (abs_beta > hard_review_threshold).fillna(False).astype(bool)
    consecutive = _consecutive_true_counts(hard_raw)
    hard_review_flag = (consecutive >= hard_review_consecutive_days).astype(bool)

    return BetaMonitorResult(
        beta=beta,
        abs_beta=abs_beta,
        warning_flag=warning_flag,
        hard_review_flag=hard_review_flag,
        consecutive_breach_count=consecutive,
        window_label=window_label,
        market_proxy_label=str(market_proxy_name),
        warmup_dates=[pd.Timestamp(date) for date in portfolio.index[obs_count < min_obs]],
    )


def _consecutive_true_counts(flags: pd.Series) -> pd.Series:
    counts = []
    current = 0
    for flag in flags.astype(bool):
        current = current + 1 if flag else 0
        counts.append(current)
    return pd.Series(counts, index=flags.index, name="consecutive_breach_count", dtype=int)
