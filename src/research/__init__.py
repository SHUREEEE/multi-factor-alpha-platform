"""Research tools for single-factor alpha testing."""

from src.research.fama_macbeth import run_fama_macbeth
from src.research.ic_analysis import compute_ic, compute_ic_timeseries, make_forward_returns, summarize_ic
from src.research.quantile_test import compute_long_short_return, compute_monotonicity, quantile_portfolio_returns

__all__ = [
    "compute_ic",
    "compute_ic_timeseries",
    "compute_long_short_return",
    "compute_monotonicity",
    "make_forward_returns",
    "quantile_portfolio_returns",
    "run_fama_macbeth",
    "summarize_ic",
]
