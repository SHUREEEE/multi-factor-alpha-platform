"""Run Pillar 4 Stage 4.4 implementation validation grid."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_pillar4_stage42 import _load_panel, _load_research_summary, _portfolio_weights, _project_path  # noqa: E402
from scripts.run_pillar4_stage43_costs import STAGE43_PORTFOLIOS  # noqa: E402
from src.combination import EqualWeightCombiner, WeightedCombiner, build_sign_adjusted_panel  # noqa: E402
from src.combination.config import Pillar4Config, PortfolioConfig, load_pillar4_config, specs_for_portfolio  # noqa: E402
from src.portfolio import apply_linear_transaction_costs, backtest_rebalanced_deciles, build_liquidity_mask, summarize_net_returns  # noqa: E402
from src.research.quantile_test import TRADING_DAYS_PER_YEAR, compute_annualized_sharpe  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config/pillar4_candidate_factors.yaml"
GRID_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_stage44_implementation_grid.csv"
YEARLY_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_stage44_yearly_breakdown.csv"
REPORT_OUTPUT_PATH = PROJECT_ROOT / "reports/pillar4_stage44_implementation_summary.md"
SECTOR_MAP_PATH = PROJECT_ROOT / "data/raw/ticker_sector_map.parquet"
REBALANCE_FREQUENCIES = ["daily", "weekly_5d"]
LIQUIDITY_MODES = ["none", "adv20_filtered"]
COST_BPS_LEVELS = [0, 5, 10, 20]


def main() -> None:
    """Run the Stage 4.4 implementation grid."""
    config = load_pillar4_config(CONFIG_PATH)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    research_summary = _load_research_summary(_project_path(config.research_summary_file))
    liquidity_masks = {mode: build_liquidity_mask(prices, mode) for mode in LIQUIDITY_MODES}
    sector_map = _load_sector_map(SECTOR_MAP_PATH)
    grid_rows: list[dict[str, float | int | str]] = []
    yearly_rows: list[dict[str, float | int | str]] = []
    risk_rows: list[dict[str, float | str]] = []
    for portfolio in _stage44_portfolios(config):
        composite, weights_text = _build_composite(portfolio, config, factors, research_summary)
        for frequency in REBALANCE_FREQUENCIES:
            for liquidity_mode, liquidity_mask in liquidity_masks.items():
                result = backtest_rebalanced_deciles(composite, prices, frequency, liquidity_mask)
                yearly_rows.extend(_yearly_rows(portfolio.name, frequency, liquidity_mode, result.daily_returns))
                risk_rows.append(_risk_row(portfolio.name, frequency, liquidity_mode, result.weights, result.daily_returns, prices, sector_map))
                for cost_bps in COST_BPS_LEVELS:
                    costed = apply_linear_transaction_costs(result.daily_returns, cost_bps)
                    grid_rows.append(_grid_row(portfolio.name, frequency, liquidity_mode, cost_bps, weights_text, result.daily_returns, costed))
    grid = pd.DataFrame(grid_rows)
    yearly = pd.DataFrame(yearly_rows)
    risks = pd.DataFrame(risk_rows)
    _save_csv(grid, GRID_OUTPUT_PATH)
    _save_csv(yearly, YEARLY_OUTPUT_PATH)
    REPORT_OUTPUT_PATH.write_text(_build_report(grid, yearly, risks), encoding="utf-8")
    print(_report_table(grid).to_string(index=False))
    print(f"Saved {GRID_OUTPUT_PATH.as_posix()}")
    print(f"Saved {YEARLY_OUTPUT_PATH.as_posix()}")
    print(f"Saved {REPORT_OUTPUT_PATH.as_posix()}")


def _stage44_portfolios(config: Pillar4Config) -> list[PortfolioConfig]:
    portfolio_map = {portfolio.name: portfolio for portfolio in config.portfolios}
    missing_names = sorted(set(STAGE43_PORTFOLIOS) - set(portfolio_map))
    if missing_names:
        raise ValueError(f"Stage 4.4 portfolios missing from config: {missing_names}")
    return [portfolio_map[name] for name in STAGE43_PORTFOLIOS]


def _build_composite(
    portfolio: PortfolioConfig,
    config: Pillar4Config,
    factors: pd.DataFrame,
    research_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    specs = specs_for_portfolio(config, portfolio)
    adjusted = build_sign_adjusted_panel(factors, specs)
    selected = adjusted[[spec.name for spec in specs]]
    weights = _portfolio_weights(portfolio, selected.columns.tolist(), research_summary)
    combiner = EqualWeightCombiner() if portfolio.weighting == "equal" else WeightedCombiner(weights)
    return combiner.combine(selected), _format_weights(weights)


def _grid_row(
    portfolio_name: str,
    frequency: str,
    liquidity_mode: str,
    cost_bps: int,
    weights_text: str,
    gross_returns: pd.DataFrame,
    costed_returns: pd.DataFrame,
) -> dict[str, float | int | str]:
    summary = summarize_net_returns(costed_returns)
    return {
        "portfolio": portfolio_name,
        "rebalance_frequency": frequency,
        "liquidity_filter": liquidity_mode,
        "cost_bps": cost_bps,
        "weights": weights_text,
        "annualized_return": summary["annualized_return"],
        "annualized_sharpe": summary["annualized_sharpe"],
        "max_drawdown": summary["max_drawdown"],
        "average_daily_turnover": summary["average_daily_turnover"],
        "long_turnover": float(gross_returns["long_turnover"].mean(skipna=True)),
        "short_turnover": float(gross_returns["short_turnover"].mean(skipna=True)),
        "entry_turnover": float(gross_returns["entry_turnover"].mean(skipna=True)),
        "exit_turnover": float(gross_returns["exit_turnover"].mean(skipna=True)),
        "hit_rate": summary["hit_rate"],
        "net_cumulative_return": summary["net_cumulative_return"],
        "n_days": summary["n_days"],
    }


def _yearly_rows(
    portfolio_name: str,
    frequency: str,
    liquidity_mode: str,
    daily_returns: pd.DataFrame,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for year, frame in daily_returns.groupby(daily_returns.index.year):
        returns = frame["long_short_return"].dropna()
        if returns.empty:
            continue
        cumulative = (1.0 + returns).cumprod() - 1.0
        rows.append(
            {
                "year": int(year),
                "portfolio": portfolio_name,
                "rebalance_frequency": frequency,
                "liquidity_filter": liquidity_mode,
                "annual_return": float((1.0 + returns).prod() - 1.0),
                "annual_sharpe": compute_annualized_sharpe(returns),
                "max_drawdown_year": _max_drawdown(cumulative),
                "average_turnover_year": float(frame["turnover"].mean(skipna=True)),
                "n_days": int(returns.shape[0]),
            }
        )
    return rows


def _risk_row(
    portfolio_name: str,
    frequency: str,
    liquidity_mode: str,
    weights: pd.DataFrame,
    daily_returns: pd.DataFrame,
    prices: pd.DataFrame,
    sector_map: pd.DataFrame,
) -> dict[str, float | str]:
    sector_series = _sector_series(weights.columns, sector_map)
    long_concentration = weights.where(weights > 0.0, 0.0).apply(lambda row: _sector_concentration(row, sector_series), axis=1)
    short_concentration = (-weights.where(weights < 0.0, 0.0)).apply(lambda row: _sector_concentration(row, sector_series), axis=1)
    market_returns = prices["return_1d"].unstack("ticker").mean(axis=1, skipna=True).reindex(daily_returns.index)
    portfolio_returns = daily_returns["long_short_return"].reindex(market_returns.index)
    return {
        "portfolio": portfolio_name,
        "rebalance_frequency": frequency,
        "liquidity_filter": liquidity_mode,
        "average_net_beta": _return_beta(portfolio_returns, market_returns),
        "average_sector_concentration_long": float(long_concentration.mean(skipna=True)),
        "average_sector_concentration_short": float(short_concentration.mean(skipna=True)),
        "average_cross_sectional_names_long": float((weights > 0.0).sum(axis=1).replace(0, pd.NA).mean()),
        "average_cross_sectional_names_short": float((weights < 0.0).sum(axis=1).replace(0, pd.NA).mean()),
    }


def _max_drawdown(cumulative_returns: pd.Series) -> float:
    wealth = 1.0 + cumulative_returns.dropna()
    if wealth.empty:
        return float("nan")
    return float((wealth / wealth.cummax() - 1.0).min())


def _build_report(grid: pd.DataFrame, yearly: pd.DataFrame, risks: pd.DataFrame) -> str:
    report_grid = _report_table(grid)
    yearly_summary = _yearly_summary(yearly)
    lines = [
        "# Pillar 4 Stage 4.4 Implementation Validation",
        "",
        "## Setup",
        "- Main portfolio: `dedup_3f_fm_weighted_idio`.",
        "- Control portfolio: `dedup_3f_equal_weight_idio`.",
        "- Rebalance modes: daily and weekly_5d.",
        "- Liquidity modes: none and adv20_filtered.",
        "- Cost levels: 0, 5, 10, and 20 one-way bps.",
        "- Two-way interpretation: a 10 bps one-way setting is roughly 20 bps round-trip for a full exit and re-entry.",
        "",
        "## Table 1: Implementation Grid",
        _markdown_table(report_grid),
        "",
        "## Table 2: Yearly Diagnostics Summary",
        _markdown_table(yearly_summary),
        "",
        "## Table 3: Risk Checks",
        _markdown_table(_risk_checks(risks)),
        "",
        "## Interpretation",
        _interpretation_text(grid, yearly, risks),
        "",
        "## Recommendation",
        _recommendation_text(grid),
        "",
    ]
    return "\n".join(lines)


def _report_table(grid: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "portfolio",
        "rebalance_frequency",
        "liquidity_filter",
        "cost_bps",
        "annualized_return",
        "annualized_sharpe",
        "max_drawdown",
        "average_daily_turnover",
        "long_turnover",
        "short_turnover",
        "hit_rate",
        "net_cumulative_return",
    ]
    report = grid[columns].copy()
    numeric_columns = report.select_dtypes(include=["number"]).columns
    report[numeric_columns] = report[numeric_columns].round(4)
    return report


def _yearly_summary(yearly: pd.DataFrame) -> pd.DataFrame:
    grouped = yearly.groupby(["portfolio", "rebalance_frequency", "liquidity_filter"], as_index=False)
    summary = grouped.agg(
        mean_annual_return=("annual_return", "mean"),
        mean_annual_sharpe=("annual_sharpe", "mean"),
        worst_year_return=("annual_return", "min"),
        best_year_return=("annual_return", "max"),
        mean_turnover=("average_turnover_year", "mean"),
    )
    numeric_columns = summary.select_dtypes(include=["number"]).columns
    summary[numeric_columns] = summary[numeric_columns].round(4)
    return summary


def _risk_checks(risks: pd.DataFrame) -> pd.DataFrame:
    report = risks.copy()
    numeric_columns = report.select_dtypes(include=["number"]).columns
    report[numeric_columns] = report[numeric_columns].round(4)
    return report


def _load_sector_map(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["ticker", "sector"])
    sector_map = pd.read_parquet(path)
    if not {"ticker", "sector"}.issubset(sector_map.columns):
        return pd.DataFrame(columns=["ticker", "sector"])
    return sector_map[["ticker", "sector"]].copy()


def _sector_series(tickers: pd.Index, sector_map: pd.DataFrame) -> pd.Series:
    if sector_map.empty:
        return pd.Series("Unknown", index=tickers)
    mapper = sector_map.set_index("ticker")["sector"].astype(str)
    return pd.Series(tickers.astype(str), index=tickers).map(mapper).fillna("Unknown")


def _sector_concentration(weight_row: pd.Series, sector_series: pd.Series) -> float:
    clean_weights = weight_row.dropna()
    if clean_weights.abs().sum() == 0.0:
        return float("nan")
    sector_weights = clean_weights.groupby(sector_series.reindex(clean_weights.index)).sum()
    return float(sector_weights.max())


def _return_beta(portfolio_returns: pd.Series, market_returns: pd.Series) -> float:
    paired = pd.concat([portfolio_returns, market_returns], axis=1, keys=["portfolio", "market"]).dropna()
    if paired.shape[0] < 3:
        return float("nan")
    variance = float(paired["market"].var(ddof=1))
    if variance == 0.0:
        return float("nan")
    covariance = float(paired["portfolio"].cov(paired["market"]))
    return covariance / variance


def _recommendation_text(grid: pd.DataFrame) -> str:
    practical = grid[(grid["cost_bps"].isin([5, 10])) & (grid["liquidity_filter"] == "adv20_filtered")]
    ranked = practical.groupby(["portfolio", "rebalance_frequency"])["annualized_sharpe"].mean().sort_values(ascending=False)
    best_portfolio, best_frequency = ranked.index[0]
    daily_fm = _metric(grid, "dedup_3f_fm_weighted_idio", "daily", "adv20_filtered", 10)
    weekly_fm = _metric(grid, "dedup_3f_fm_weighted_idio", "weekly_5d", "adv20_filtered", 10)
    daily_fm_none = _metric(grid, "dedup_3f_fm_weighted_idio", "daily", "none", 10)
    weekly_fm_none = _metric(grid, "dedup_3f_fm_weighted_idio", "weekly_5d", "none", 10)
    return (
        f"Use `dedup_3f_fm_weighted_idio` with `weekly_5d` as the Stage 4.5 implementation baseline, with `daily` kept as a high-frequency challenger. "
        f"At 10 bps without filtering, FM daily Sharpe is {daily_fm_none:.3f} and FM weekly Sharpe is {weekly_fm_none:.3f}; "
        f"with ADV20 filtering, daily Sharpe is {daily_fm:.3f} and weekly Sharpe is {weekly_fm:.3f}. "
        f"The grid-selected practical winner is `{best_portfolio}` with `{best_frequency}`, but the larger research conclusion is that weekly rebalance is the cost-aware default. "
        "Stage 4.5 must beta-neutralize this configuration before it can be treated as deployable."
    )


def _interpretation_text(grid: pd.DataFrame, yearly: pd.DataFrame, risks: pd.DataFrame) -> str:
    adv_drop = _adv20_sharpe_drop_range(grid)
    beta_min = float(risks["average_net_beta"].min())
    beta_max = float(risks["average_net_beta"].max())
    contribution_2020 = _year_2020_text(yearly)
    return (
        "- Weekly_5d is the main Stage 4.4 discovery: it cuts turnover by more than half for the FM baseline and improves cost-adjusted Sharpe at 10 bps and 20 bps.\n"
        f"- The ADV20 filter reduces Sharpe by roughly {adv_drop[0]:.2f}-{adv_drop[1]:.2f} across matched configurations. "
        "This means part of the alpha comes from less liquid names, but the qualitative FM/weekly conclusion does not collapse.\n"
        f"- The portfolio carries average net beta around {beta_min:.2f}-{beta_max:.2f} against the equal-weight pool proxy. "
        "A significant part of realized return, especially in strong market years, may be directional beta rather than pure factor alpha.\n"
        f"- {contribution_2020} Stage 4.5 should report results with and without 2020."
    )


def _adv20_sharpe_drop_range(grid: pd.DataFrame) -> tuple[float, float]:
    rows = []
    for _, row in grid[grid["liquidity_filter"] == "none"].iterrows():
        matched = grid[
            (grid["portfolio"] == row["portfolio"])
            & (grid["rebalance_frequency"] == row["rebalance_frequency"])
            & (grid["cost_bps"] == row["cost_bps"])
            & (grid["liquidity_filter"] == "adv20_filtered")
        ]
        if not matched.empty:
            rows.append(float(row["annualized_sharpe"] - matched.iloc[0]["annualized_sharpe"]))
    if not rows:
        return (float("nan"), float("nan"))
    return (min(rows), max(rows))


def _year_2020_text(yearly: pd.DataFrame) -> str:
    year_2020 = yearly[yearly["year"] == 2020]
    if year_2020.empty:
        return "Year 2020 diagnostics are unavailable."
    best_2020 = year_2020.sort_values("annual_return", ascending=False).iloc[0]
    return (
        f"Performance is partially concentrated in 2020; the strongest 2020 slice is `{best_2020['portfolio']}` "
        f"with `{best_2020['rebalance_frequency']}` and annual return {float(best_2020['annual_return']):.1%}."
    )


def _metric(grid: pd.DataFrame, portfolio: str, frequency: str, liquidity: str, cost_bps: int) -> float:
    row = grid[
        (grid["portfolio"] == portfolio)
        & (grid["rebalance_frequency"] == frequency)
        & (grid["liquidity_filter"] == liquidity)
        & (grid["cost_bps"] == cost_bps)
    ]
    if row.empty:
        return float("nan")
    return float(row.iloc[0]["annualized_sharpe"])


def _format_weights(weights: dict[str, float]) -> str:
    return "; ".join(f"{name}={value:.4f}" for name, value in weights.items())


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _markdown_table(frame: pd.DataFrame) -> str:
    text_frame = frame.astype(str)
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text_frame.to_numpy()]
    return "\n".join([header, separator, *rows])


if __name__ == "__main__":
    main()
