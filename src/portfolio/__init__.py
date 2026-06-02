"""Portfolio construction and evaluation utilities."""

from src.portfolio.costs import apply_linear_transaction_costs, summarize_net_returns
from src.portfolio.capacity import (
    borrow_feasible_flag,
    compute_participation,
    compute_turnover_impact_cost,
    top_short_concentration,
)
from src.portfolio.attribution import (
    factor_residual_decomposition,
    rolling_realized_beta,
    sector_active_pnl,
    sector_net_exposures,
    variance_contribution_shares,
)
from src.portfolio.implementation import (
    ImplementationBacktestResult,
    backtest_from_weights,
    backtest_rebalanced_deciles,
    build_rebalanced_decile_weights,
    build_liquidity_mask,
    decompose_turnover,
)
from src.portfolio.neutralization import (
    apply_sector_cap,
    beta_neutralize_weights,
    build_out_of_portfolio_market_proxy,
    compute_rolling_betas,
    portfolio_ex_ante_beta,
    sector_cap_then_renormalize_beta,
)
from src.portfolio.risk import (
    annualized_volatility,
    drawdown_events,
    drawdown_series,
    max_drawdown,
    max_drawdown_duration_days,
    realized_beta,
    scale_return_stream,
    slice_returns_window,
    summarize_return_stream,
)

__all__ = [
    "ImplementationBacktestResult",
    "apply_linear_transaction_costs",
    "factor_residual_decomposition",
    "borrow_feasible_flag",
    "backtest_from_weights",
    "backtest_rebalanced_deciles",
    "build_rebalanced_decile_weights",
    "build_liquidity_mask",
    "apply_sector_cap",
    "beta_neutralize_weights",
    "build_out_of_portfolio_market_proxy",
    "compute_rolling_betas",
    "compute_participation",
    "compute_turnover_impact_cost",
    "decompose_turnover",
    "portfolio_ex_ante_beta",
    "annualized_volatility",
    "drawdown_events",
    "drawdown_series",
    "max_drawdown",
    "max_drawdown_duration_days",
    "realized_beta",
    "scale_return_stream",
    "slice_returns_window",
    "sector_cap_then_renormalize_beta",
    "summarize_net_returns",
    "summarize_return_stream",
    "top_short_concentration",
    "rolling_realized_beta",
    "sector_active_pnl",
    "sector_net_exposures",
    "variance_contribution_shares",
]
