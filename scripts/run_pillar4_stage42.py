"""Run Pillar 4 Stage 4.2 de-duplication and simple weighting comparison."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.combination import EqualWeightCombiner, WeightedCombiner, build_sign_adjusted_panel  # noqa: E402
from src.combination.baseline import BaselineBacktestResult, backtest_top_bottom_decile  # noqa: E402
from src.combination.config import Pillar4Config, PortfolioConfig, load_pillar4_config, specs_for_portfolio  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config/pillar4_candidate_factors.yaml"
COMPARISON_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_portfolio_comparison.csv"
REPORT_OUTPUT_PATH = PROJECT_ROOT / "reports/pillar4_stage42_comparison.md"


def main() -> None:
    """Run every configured Stage 4.2 comparison portfolio."""
    config = load_pillar4_config(CONFIG_PATH)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    research_summary = _load_research_summary(_project_path(config.research_summary_file))
    rows: list[dict[str, float | int | str]] = []
    for portfolio in config.portfolios:
        backtest, weights = _run_one_portfolio(portfolio, config, factors, prices, research_summary)
        rows.append(_comparison_row(portfolio, backtest, weights))
    comparison = pd.DataFrame(rows)
    _save_csv(comparison, COMPARISON_OUTPUT_PATH)
    REPORT_OUTPUT_PATH.write_text(_build_report(comparison, config), encoding="utf-8")
    print(comparison.to_string(index=False))
    print(f"Saved {COMPARISON_OUTPUT_PATH.as_posix()}")
    print(f"Saved {REPORT_OUTPUT_PATH.as_posix()}")


def _run_one_portfolio(
    portfolio: PortfolioConfig,
    config: Pillar4Config,
    factors: pd.DataFrame,
    prices: pd.DataFrame,
    research_summary: pd.DataFrame,
) -> tuple[BaselineBacktestResult, dict[str, float]]:
    """Build one composite and run the common long-short backtest."""
    specs = specs_for_portfolio(config, portfolio)
    adjusted = build_sign_adjusted_panel(factors, specs)
    selected = adjusted[[spec.name for spec in specs]]
    weights = _portfolio_weights(portfolio, selected.columns.tolist(), research_summary)
    combiner = EqualWeightCombiner() if portfolio.weighting == "equal" else WeightedCombiner(weights)
    composite = combiner.combine(selected)
    return backtest_top_bottom_decile(composite, prices, n_quantiles=10), weights


def _portfolio_weights(portfolio: PortfolioConfig, factor_names: list[str], research_summary: pd.DataFrame) -> dict[str, float]:
    """Return equal, FM t-stat, or IC IR weights for a portfolio."""
    if portfolio.weighting == "equal":
        return {factor_name: 1.0 / len(factor_names) for factor_name in factor_names}
    metric_column = _weight_metric_column(portfolio.weighting)
    metric_values = research_summary.set_index("factor_name")[metric_column].reindex(factor_names).abs()
    if metric_values.isna().any():
        missing_names = metric_values[metric_values.isna()].index.tolist()
        raise ValueError(f"Missing research weights for {portfolio.name}: {missing_names}")
    total_metric = float(metric_values.sum())
    if total_metric <= 0.0 or np.isnan(total_metric):
        raise ValueError(f"Research weights for {portfolio.name} sum to zero.")
    normalized = metric_values / total_metric
    return {factor_name: float(normalized.loc[factor_name]) for factor_name in factor_names}


def _weight_metric_column(weighting: str) -> str:
    """Map config weighting names to research-summary columns."""
    if weighting == "fm_abs_tstat":
        return "fama_macbeth_tstat"
    if weighting == "icir_abs":
        return "ic_ir_1d"
    raise ValueError(f"Unsupported weighting scheme: {weighting}")


def _comparison_row(
    portfolio: PortfolioConfig,
    backtest: BaselineBacktestResult,
    weights: dict[str, float],
) -> dict[str, float | int | str]:
    """Flatten one backtest result into a report row."""
    summary = backtest.summary
    return {
        "portfolio": portfolio.name,
        "factors": ", ".join(portfolio.factors),
        "weighting": portfolio.weighting,
        "weights": _format_weights(weights),
        "annualized_return": summary["annualized_return"],
        "annualized_sharpe": summary["annualized_sharpe"],
        "max_drawdown": summary["max_drawdown"],
        "average_daily_turnover": summary["average_daily_turnover"],
        "hit_rate": summary["hit_rate"],
        "average_long_count": summary["average_long_count"],
        "average_short_count": summary["average_short_count"],
        "n_days": summary["n_days"],
    }


def _format_weights(weights: dict[str, float]) -> str:
    """Format weights compactly for CSV and Markdown outputs."""
    return "; ".join(f"{name}={value:.4f}" for name, value in weights.items())


def _load_panel(path: Path, name: str) -> pd.DataFrame:
    """Load a standard MultiIndex project panel."""
    if not path.exists():
        raise FileNotFoundError(f"Missing {name} file: {path.as_posix()}")
    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError(f"{name} must use MultiIndex(date, ticker).")
    frame.index = frame.index.set_names(["date", "ticker"])
    if frame.index.has_duplicates:
        raise ValueError(f"{name} contains duplicate (date, ticker) rows.")
    return frame.sort_index()


def _load_research_summary(path: Path) -> pd.DataFrame:
    """Load Pillar 3 research metrics used for simple research weights."""
    if not path.exists():
        raise FileNotFoundError(f"Missing research summary file: {path.as_posix()}")
    summary = pd.read_csv(path)
    required_columns = {"factor_name", "ic_ir_1d", "fama_macbeth_tstat"}
    missing_columns = sorted(required_columns - set(summary.columns))
    if missing_columns:
        raise ValueError(f"research summary missing columns: {missing_columns}")
    return summary


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    """Save a CSV file after creating its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _project_path(path_text: str) -> Path:
    """Resolve config paths relative to the project root."""
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _build_report(comparison: pd.DataFrame, config: Pillar4Config) -> str:
    """Render the Stage 4.2 Markdown comparison report."""
    lines = [
        "# Pillar 4 Stage 4.2 Portfolio Comparison",
        "",
        "## Setup",
        f"- Factor source: `{config.source_factor_file}`.",
        "- Direction transforms are applied before z-scoring and do not modify raw factor definitions.",
        "- All composites are re-zscored by date before portfolio formation.",
        "- All portfolios use top decile long, bottom decile short, daily rebalance, and 1-day lag.",
        "- Transaction costs are still excluded.",
        "",
        "## Comparison Table",
        _markdown_table(comparison),
        "",
        "## Decision",
        _decision_text(comparison),
        "",
    ]
    return "\n".join(lines)


def _decision_text(comparison: pd.DataFrame) -> str:
    """Build a short research recommendation from the comparison table."""
    best_row = comparison.sort_values(["annualized_sharpe", "max_drawdown"], ascending=[False, False]).iloc[0]
    idio_sharpe = _metric(comparison, "dedup_3f_equal_weight_idio", "annualized_sharpe")
    realized_sharpe = _metric(comparison, "dedup_3f_equal_weight_realized", "annualized_sharpe")
    redundant_choice = "remove `realized_vol` first" if idio_sharpe >= realized_sharpe else "remove `idiosyncratic_vol` first"
    return (
        f"- Volatility de-duplication: {redundant_choice}, because the 3-factor idio Sharpe is {idio_sharpe:.3f} "
        f"versus realized-vol Sharpe {realized_sharpe:.3f}.\n"
        f"- Preferred Stage 4.3 baseline: `{best_row['portfolio']}` based on the highest Sharpe in this no-cost comparison.\n"
        "- Keep equal-weight as the robustness benchmark because research weights are simple historical diagnostics, not optimized live weights."
    )


def _metric(comparison: pd.DataFrame, portfolio_name: str, column: str) -> float:
    """Read one metric from the comparison table."""
    row = comparison[comparison["portfolio"] == portfolio_name]
    if row.empty:
        return float("nan")
    return float(row.iloc[0][column])


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a Markdown table without optional dependencies."""
    text_frame = frame.astype(str)
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text_frame.to_numpy()]
    return "\n".join([header, separator, *rows])


if __name__ == "__main__":
    main()
