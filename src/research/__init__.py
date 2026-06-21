"""Research tools for single-factor alpha testing."""

from src.research.fama_macbeth import run_fama_macbeth
from src.research.factor_turnover import (
    quantile_membership_turnover,
    rank_autocorrelation,
    signal_half_life,
    summarize_factor_turnover,
)
from src.research.ic_decay import compute_ic_decay, rolling_ic_summary
from src.research.ic_analysis import compute_ic, compute_ic_timeseries, make_forward_returns, summarize_ic
from src.research.quantile_test import compute_long_short_return, compute_monotonicity, quantile_portfolio_returns
from src.research.regime_validation import build_default_regimes, summarize_factor_by_regime, summarize_portfolio_by_regime
from src.research.significance import benjamini_hochberg, bootstrap_mean_ci, newey_west_mean_test

__all__ = [
    "compute_ic",
    "compute_ic_decay",
    "compute_ic_timeseries",
    "compute_long_short_return",
    "compute_monotonicity",
    "benjamini_hochberg",
    "bootstrap_mean_ci",
    "build_default_regimes",
    "make_forward_returns",
    "newey_west_mean_test",
    "quantile_membership_turnover",
    "quantile_portfolio_returns",
    "rank_autocorrelation",
    "rolling_ic_summary",
    "run_fama_macbeth",
    "signal_half_life",
    "summarize_factor_by_regime",
    "summarize_factor_turnover",
    "summarize_ic",
    "summarize_portfolio_by_regime",
]
