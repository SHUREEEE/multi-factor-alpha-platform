"""Run Pillar 4 Stage 4.3 transaction-cost-aware portfolio evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_pillar4_stage42 import _load_panel, _load_research_summary, _portfolio_weights, _project_path  # noqa: E402
from src.combination import EqualWeightCombiner, WeightedCombiner, build_sign_adjusted_panel  # noqa: E402
from src.combination.config import Pillar4Config, PortfolioConfig, load_pillar4_config, specs_for_portfolio  # noqa: E402
from src.portfolio.costs import apply_linear_transaction_costs, summarize_net_returns  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config/pillar4_candidate_factors.yaml"
OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_stage43_cost_comparison.csv"
REPORT_PATH = PROJECT_ROOT / "reports/pillar4_stage43_cost_summary.md"
STAGE43_PORTFOLIOS = ["dedup_3f_equal_weight_idio", "dedup_3f_fm_weighted_idio"]
COST_BPS_LEVELS = [0, 5, 10, 20]


def main() -> None:
    """Evaluate primary and challenger portfolios under transaction costs."""
    config = load_pillar4_config(CONFIG_PATH)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    research_summary = _load_research_summary(_project_path(config.research_summary_file))
    portfolios = _stage43_portfolios(config)
    rows: list[dict[str, float | int | str]] = []
    for portfolio in portfolios:
        gross_returns, weights = _gross_backtest(portfolio, config, factors, prices, research_summary)
        for cost_bps in COST_BPS_LEVELS:
            costed = apply_linear_transaction_costs(gross_returns, cost_bps)
            rows.append(_cost_row(portfolio, weights, cost_bps, costed))
    comparison = pd.DataFrame(rows)
    _save_csv(comparison, OUTPUT_PATH)
    REPORT_PATH.write_text(_build_report(comparison, config), encoding="utf-8")
    print(comparison.to_string(index=False))
    print(f"Saved {OUTPUT_PATH.as_posix()}")
    print(f"Saved {REPORT_PATH.as_posix()}")


def _stage43_portfolios(config: Pillar4Config) -> list[PortfolioConfig]:
    """Select the two portfolios promoted from Stage 4.2."""
    portfolio_map = {portfolio.name: portfolio for portfolio in config.portfolios}
    missing_names = sorted(set(STAGE43_PORTFOLIOS) - set(portfolio_map))
    if missing_names:
        raise ValueError(f"Stage 4.3 portfolios missing from config: {missing_names}")
    return [portfolio_map[name] for name in STAGE43_PORTFOLIOS]


def _gross_backtest(
    portfolio: PortfolioConfig,
    config: Pillar4Config,
    factors: pd.DataFrame,
    prices: pd.DataFrame,
    research_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Run the no-cost long-short backtest for one Stage 4.3 portfolio."""
    specs = specs_for_portfolio(config, portfolio)
    adjusted = build_sign_adjusted_panel(factors, specs)
    selected = adjusted[[spec.name for spec in specs]]
    weights = _portfolio_weights(portfolio, selected.columns.tolist(), research_summary)
    combiner = EqualWeightCombiner() if portfolio.weighting == "equal" else WeightedCombiner(weights)
    composite = combiner.combine(selected)
    from src.combination.baseline import backtest_top_bottom_decile

    return backtest_top_bottom_decile(composite, prices, n_quantiles=10).daily_returns, weights


def _cost_row(
    portfolio: PortfolioConfig,
    weights: dict[str, float],
    cost_bps: int,
    costed_returns: pd.DataFrame,
) -> dict[str, float | int | str]:
    """Flatten one cost scenario into a comparison row."""
    summary = summarize_net_returns(costed_returns)
    gross_summary = summarize_net_returns(_gross_as_net(costed_returns))
    return {
        "portfolio": portfolio.name,
        "cost_bps": cost_bps,
        "weighting": portfolio.weighting,
        "weights": _format_weights(weights),
        "annualized_return": summary["annualized_return"],
        "annualized_sharpe": summary["annualized_sharpe"],
        "gross_annualized_sharpe": gross_summary["annualized_sharpe"],
        "max_drawdown": summary["max_drawdown"],
        "average_daily_turnover": summary["average_daily_turnover"],
        "hit_rate": summary["hit_rate"],
        "net_cumulative_return": summary["net_cumulative_return"],
        "average_daily_cost": summary["average_daily_cost"],
        "n_days": summary["n_days"],
        "break_even_cost_bps": _break_even_cost_bps(costed_returns),
    }


def _gross_as_net(costed_returns: pd.DataFrame) -> pd.DataFrame:
    """Re-label gross returns so the common net summary can be reused."""
    output = costed_returns.copy()
    output["net_return"] = output["gross_return"]
    output["transaction_cost"] = 0.0
    output["net_cumulative_return"] = (1.0 + output["net_return"].fillna(0.0)).cumprod() - 1.0
    return output


def _break_even_cost_bps(costed_returns: pd.DataFrame) -> float:
    """Estimate the one-way bps cost that would reduce mean net return to zero."""
    gross_mean = float(costed_returns["gross_return"].mean(skipna=True))
    turnover_mean = float(costed_returns["turnover"].mean(skipna=True))
    if turnover_mean <= 0.0 or np.isnan(turnover_mean):
        return float("nan")
    return float(gross_mean / turnover_mean * 10000.0)


def _build_report(comparison: pd.DataFrame, config: Pillar4Config) -> str:
    """Render the Stage 4.3 transaction-cost Markdown report."""
    lines = [
        "# Pillar 4 Stage 4.3 Transaction Cost Summary",
        "",
        "## Setup",
        f"- Factor source: `{config.source_factor_file}`.",
        "- Evaluated portfolios: `dedup_3f_equal_weight_idio` and `dedup_3f_fm_weighted_idio`.",
        "- `dedup_3f_equal_weight_idio` is the no-cost research winner, while `dedup_3f_fm_weighted_idio` is the implementation-aware default baseline after transaction costs.",
        "- Cost model: `net_return = gross_return - (cost_bps / 10000) * turnover`.",
        "- Cost levels: 0, 5, 10, and 20 one-way basis points.",
        "- Portfolio construction remains top decile long, bottom decile short, daily rebalance, and 1-day lag.",
        "",
        "## Cost Comparison",
        _markdown_table(_report_table(comparison)),
        "",
        "## Sensitivity",
        _sensitivity_text(comparison),
        "",
        "## Recommendation",
        _recommendation_text(comparison),
        "",
    ]
    return "\n".join(lines)


def _sensitivity_text(comparison: pd.DataFrame) -> str:
    """List the winning portfolio at each cost level."""
    lines = []
    for cost_bps in COST_BPS_LEVELS:
        cost_slice = comparison[comparison["cost_bps"] == cost_bps]
        winner = cost_slice.sort_values(["annualized_sharpe", "max_drawdown"], ascending=[False, False]).iloc[0]
        lines.append(f"- {cost_bps} bps winner: `{winner['portfolio']}` with Sharpe {winner['annualized_sharpe']:.3f}.")
    return "\n".join(lines)


def _report_table(comparison: pd.DataFrame) -> pd.DataFrame:
    """Build a compact report table while keeping the CSV fully detailed."""
    columns = [
        "portfolio",
        "cost_bps",
        "annualized_return",
        "annualized_sharpe",
        "max_drawdown",
        "average_daily_turnover",
        "hit_rate",
        "net_cumulative_return",
        "break_even_cost_bps",
    ]
    report = comparison[columns].copy()
    rename_map = {
        "average_daily_turnover": "avg_turnover",
        "net_cumulative_return": "net_cum_return",
        "break_even_cost_bps": "break_even_bps",
    }
    report = report.rename(columns=rename_map)
    numeric_columns = report.select_dtypes(include=["number"]).columns
    report[numeric_columns] = report[numeric_columns].round(4)
    return report


def _recommendation_text(comparison: pd.DataFrame) -> str:
    """Recommend the default Stage 4 baseline for Stage 4.4."""
    practical = comparison[comparison["cost_bps"].isin([5, 10, 20])]
    average_sharpe = practical.groupby("portfolio")["annualized_sharpe"].mean().sort_values(ascending=False)
    selected = str(average_sharpe.index[0])
    equal_10 = _metric(comparison, "dedup_3f_equal_weight_idio", 10, "annualized_sharpe")
    fm_10 = _metric(comparison, "dedup_3f_fm_weighted_idio", 10, "annualized_sharpe")
    return (
        f"Use `{selected}` as the default Stage 4.4 baseline. At 10 bps, equal-weight Sharpe is {equal_10:.3f} "
        f"and FM-weighted Sharpe is {fm_10:.3f}. The choice balances cost-adjusted Sharpe with implementation realism."
    )


def _metric(comparison: pd.DataFrame, portfolio_name: str, cost_bps: int, column: str) -> float:
    """Read one metric from the cost comparison table."""
    row = comparison[(comparison["portfolio"] == portfolio_name) & (comparison["cost_bps"] == cost_bps)]
    if row.empty:
        return float("nan")
    return float(row.iloc[0][column])


def _format_weights(weights: dict[str, float]) -> str:
    """Format factor weights for reports."""
    return "; ".join(f"{name}={value:.4f}" for name, value in weights.items())


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    """Save a CSV file after creating its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a Markdown table without optional dependencies."""
    text_frame = frame.astype(str)
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text_frame.to_numpy()]
    return "\n".join([header, separator, *rows])


if __name__ == "__main__":
    main()
