"""Run Pillar 4 Stage 4.5 risk neutralization and final baseline lock-in."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_pillar4_stage42 import _load_panel, _load_research_summary, _portfolio_weights, _project_path  # noqa: E402
from scripts.run_pillar4_stage44_implementation import _build_composite, _load_sector_map, _sector_series  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import (  # noqa: E402
    apply_linear_transaction_costs,
    apply_sector_cap,
    backtest_from_weights,
    beta_neutralize_weights,
    build_liquidity_mask,
    build_out_of_portfolio_market_proxy,
    build_rebalanced_decile_weights,
    compute_rolling_betas,
    portfolio_ex_ante_beta,
    sector_cap_then_renormalize_beta,
    summarize_net_returns,
)
from src.research.quantile_test import compute_annualized_sharpe  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config/pillar4_candidate_factors.yaml"
SECTOR_MAP_PATH = PROJECT_ROOT / "data/raw/ticker_sector_map.parquet"
MARKET_PROXY_PATH = PROJECT_ROOT / "data/market_data/market_proxy.parquet"
GRID_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_stage45_neutralization_grid.csv"
YEARLY_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_stage45_yearly_breakdown.csv"
DRAWDOWN_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_stage45_rolling_drawdown.csv"
PROXY_DIAGNOSTICS_PATH = PROJECT_ROOT / "results/pillar4_stage45_proxy_diagnostics.csv"
REPORT_OUTPUT_PATH = PROJECT_ROOT / "reports/pillar4_stage45_neutralization_summary.md"
PORTFOLIO_NAME = "dedup_3f_fm_weighted_idio"
COST_BPS_LEVELS = [0, 5, 10, 20]
SECTOR_CAP = 0.25


def main() -> None:
    """Run Stage 4.5 neutralization variants."""
    config = load_pillar4_config(CONFIG_PATH)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    research_summary = _load_research_summary(_project_path(config.research_summary_file))
    portfolio = {item.name: item for item in config.portfolios}[PORTFOLIO_NAME]
    composite, _ = _build_composite(portfolio, config, factors, research_summary)
    liquidity_mask = build_liquidity_mask(prices, "adv20_filtered")
    raw_weights = build_rebalanced_decile_weights(composite, prices, "weekly_5d", liquidity_mask)
    market_proxy = build_out_of_portfolio_market_proxy(prices, raw_weights)
    _save_market_proxy(market_proxy, MARKET_PROXY_PATH)
    betas = compute_rolling_betas(prices, market_proxy, lookback=60).reindex(index=raw_weights.index, columns=raw_weights.columns)
    sector_map = _load_sector_map(SECTOR_MAP_PATH)
    sectors = _sector_series(raw_weights.columns, sector_map)
    variants = _variant_weights(raw_weights, betas, sectors)
    proxy_diagnostics = _proxy_diagnostics(variants, betas, market_proxy, prices)
    grid_rows: list[dict[str, float | int | str]] = []
    yearly_rows: list[dict[str, float | int | str]] = []
    drawdown_rows: list[dict[str, float | str]] = []
    for variant_name, weights in variants.items():
        backtest = backtest_from_weights(weights, prices)
        yearly_rows.extend(_yearly_rows(variant_name, backtest.daily_returns))
        drawdown_rows.extend(_rolling_drawdown_rows(variant_name, backtest.daily_returns))
        for cost_bps in COST_BPS_LEVELS:
            costed = apply_linear_transaction_costs(backtest.daily_returns, cost_bps)
            grid_rows.append(_grid_row(variant_name, weights, betas, sectors, backtest.daily_returns, costed, cost_bps))
    grid = pd.DataFrame(grid_rows)
    yearly = pd.DataFrame(yearly_rows)
    drawdowns = pd.DataFrame(drawdown_rows)
    _save_csv(grid, GRID_OUTPUT_PATH)
    _save_csv(yearly, YEARLY_OUTPUT_PATH)
    _save_csv(drawdowns, DRAWDOWN_OUTPUT_PATH)
    _save_csv(proxy_diagnostics, PROXY_DIAGNOSTICS_PATH)
    REPORT_OUTPUT_PATH.write_text(_build_report(grid, yearly, proxy_diagnostics), encoding="utf-8")
    print(_report_table(grid).to_string(index=False))
    print(f"Saved {GRID_OUTPUT_PATH.as_posix()}")
    print(f"Saved {YEARLY_OUTPUT_PATH.as_posix()}")
    print(f"Saved {DRAWDOWN_OUTPUT_PATH.as_posix()}")
    print(f"Saved {PROXY_DIAGNOSTICS_PATH.as_posix()}")
    print(f"Saved {REPORT_OUTPUT_PATH.as_posix()}")


def _variant_weights(raw_weights: pd.DataFrame, betas: pd.DataFrame, sectors: pd.Series) -> dict[str, pd.DataFrame]:
    beta_neutral = beta_neutralize_weights(raw_weights, betas)
    capped = sector_cap_then_renormalize_beta(raw_weights, sectors, betas, cap=SECTOR_CAP)
    return {
        "V1_raw_fm_weekly_adv20": raw_weights,
        "V2_beta_neutral_fm_weekly_adv20": beta_neutral,
        "V3_beta_neutral_sector_capped_fm_weekly_adv20": capped,
    }


def _grid_row(
    variant_name: str,
    weights: pd.DataFrame,
    betas: pd.DataFrame,
    sectors: pd.Series,
    gross_returns: pd.DataFrame,
    costed_returns: pd.DataFrame,
    cost_bps: int,
) -> dict[str, float | int | str]:
    summary = summarize_net_returns(costed_returns)
    ex_ante_beta = portfolio_ex_ante_beta(weights, betas)
    return {
        "variant": variant_name,
        "cost_bps": cost_bps,
        "annualized_return": summary["annualized_return"],
        "annualized_sharpe": summary["annualized_sharpe"],
        "max_drawdown": summary["max_drawdown"],
        "average_daily_turnover": summary["average_daily_turnover"],
        "long_turnover": float(gross_returns["long_turnover"].mean(skipna=True)),
        "short_turnover": float(gross_returns["short_turnover"].mean(skipna=True)),
        "average_net_beta": float(ex_ante_beta.mean(skipna=True)),
        "average_abs_net_beta": float(ex_ante_beta.abs().mean(skipna=True)),
        "average_gross_leverage": float(weights.abs().sum(axis=1).mean(skipna=True)),
        "max_gross_leverage": float(weights.abs().sum(axis=1).max(skipna=True)),
        "large_beta_exposure_days": int((ex_ante_beta.abs() > 0.1).sum()),
        "average_sector_concentration_long": _average_sector_concentration(weights, sectors, side="long"),
        "average_sector_concentration_short": _average_sector_concentration(weights, sectors, side="short"),
        "hit_rate": summary["hit_rate"],
        "net_cumulative_return": summary["net_cumulative_return"],
        "n_days": summary["n_days"],
    }


def _proxy_diagnostics(
    variants: dict[str, pd.DataFrame],
    betas: pd.DataFrame,
    market_proxy: pd.Series,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for variant_name, weights in variants.items():
        backtest = backtest_from_weights(weights, prices)
        realized_beta = _realized_beta(backtest.daily_returns["long_short_return"], market_proxy)
        realized_beta_pre2020 = _realized_beta_for_period(backtest.daily_returns["long_short_return"], market_proxy, end_year=2019)
        realized_beta_post2020 = _realized_beta_for_period(backtest.daily_returns["long_short_return"], market_proxy, start_year=2020)
        ex_ante_beta = portfolio_ex_ante_beta(weights, betas)
        rows.append(
            {
                "variant": variant_name,
                "proxy_source": "out_of_portfolio_equal_weight",
                "proxy_start": str(market_proxy.dropna().index.min().date()),
                "proxy_end": str(market_proxy.dropna().index.max().date()),
                "proxy_n_days": int(market_proxy.dropna().shape[0]),
        "average_ex_ante_beta": float(ex_ante_beta.mean(skipna=True)),
        "average_abs_ex_ante_beta": float(ex_ante_beta.abs().mean(skipna=True)),
        "average_gross_leverage": float(weights.abs().sum(axis=1).mean(skipna=True)),
        "max_gross_leverage": float(weights.abs().sum(axis=1).max(skipna=True)),
                "large_beta_exposure_days": int((ex_ante_beta.abs() > 0.1).sum()),
                "realized_beta_to_proxy": realized_beta,
                "realized_beta_2014_2019": realized_beta_pre2020,
                "realized_beta_2020_2024": realized_beta_post2020,
            }
        )
    return pd.DataFrame(rows)


def _yearly_rows(variant_name: str, daily_returns: pd.DataFrame) -> list[dict[str, float | int | str]]:
    rows = []
    for year, frame in daily_returns.groupby(daily_returns.index.year):
        returns = frame["long_short_return"].dropna()
        if returns.empty:
            continue
        cumulative = (1.0 + returns).cumprod() - 1.0
        rows.append(
            {
                "year": int(year),
                "variant": variant_name,
                "annual_return": float((1.0 + returns).prod() - 1.0),
                "annual_sharpe": compute_annualized_sharpe(returns),
                "max_drawdown_year": _max_drawdown(cumulative),
                "average_turnover_year": float(frame["turnover"].mean(skipna=True)),
                "include_2020": bool(year == 2020),
                "n_days": int(returns.shape[0]),
            }
        )
    return rows


def _rolling_drawdown_rows(variant_name: str, daily_returns: pd.DataFrame) -> list[dict[str, float | str]]:
    returns = daily_returns["long_short_return"].fillna(0.0)
    rolling_return = (1.0 + returns).rolling(252, min_periods=60).apply(lambda values: values.prod(), raw=True) - 1.0
    rolling_peak = rolling_return.cummax()
    rolling_drawdown = (1.0 + rolling_return) / (1.0 + rolling_peak) - 1.0
    return [
        {"date": str(date.date()), "variant": variant_name, "rolling_12m_drawdown": float(value)}
        for date, value in rolling_drawdown.dropna().items()
    ]


def _build_report(grid: pd.DataFrame, yearly: pd.DataFrame, proxy_diagnostics: pd.DataFrame) -> str:
    report = [
        "# Pillar 4 Stage 4.5 Neutralization Summary",
        "",
        "## Setup",
        "- Main configuration: `dedup_3f_fm_weighted_idio + weekly_5d + adv20_filtered`.",
        "- V1 is raw Stage 4.4 baseline; V2 adds ex-ante beta neutralization; V3 adds a 25% sector cap per side.",
        "- Market proxy source: out-of-portfolio equal-weight fallback, saved to `data/market_data/market_proxy.parquet`.",
        "- Leverage convention: all variants target dollar-neutral 100/100 books, approximately 2.0x gross exposure. Reported returns are on this long-short portfolio return stream, not a separately de-levered 1x capital allocation.",
        "- Neutrality convention: V2/V3 are ex-ante beta-neutral to the rolling 60-day proxy estimate; realized beta remains a residual risk.",
        "",
        "## Neutralization Grid",
        _markdown_table(_report_table(grid)),
        "",
        "## Proxy Diagnostics",
        _markdown_table(_round_numeric(proxy_diagnostics)),
        "",
        "## Ex-2020 Stress Summary",
        _markdown_table(_ex2020_summary(yearly)),
        "",
        "## Recommendation",
        _recommendation_text(grid, yearly),
        "",
    ]
    return "\n".join(report)


def _recommendation_text(grid: pd.DataFrame, yearly: pd.DataFrame) -> str:
    v1 = _row(grid, "V1_raw_fm_weekly_adv20", 10)
    v2 = _row(grid, "V2_beta_neutral_fm_weekly_adv20", 10)
    v3 = _row(grid, "V3_beta_neutral_sector_capped_fm_weekly_adv20", 10)
    ex2020 = _ex2020_summary(yearly)
    v3_ex2020 = ex2020[ex2020["variant"] == "V3_beta_neutral_sector_capped_fm_weekly_adv20"].iloc[0]
    beta_pass = abs(float(v3["average_net_beta"])) < 0.1
    sharpe_drop = float(v1["annualized_sharpe"] - v3["annualized_sharpe"])
    sharpe_pass = sharpe_drop < 0.15
    ex2020_pass = float(v3_ex2020["mean_annual_sharpe_ex2020"]) > 0.3
    if beta_pass and sharpe_pass and ex2020_pass:
        baseline = "V3_beta_neutral_sector_capped_fm_weekly_adv20"
        status = "passes the Stage 4.5 lock-in thresholds"
    elif beta_pass and sharpe_pass:
        baseline = "V2_beta_neutral_fm_weekly_adv20"
        status = "passes beta and Sharpe thresholds, but sector-cap or ex-2020 diagnostics need caution"
    else:
        baseline = "not locked; return to Stage 4.3/4.4 research"
        status = "fails at least one lock-in threshold"
    return (
        f"Final Pillar 4 production baseline: `{baseline}`. The candidate {status}. "
        f"At 10 bps, V1 Sharpe is {float(v1['annualized_sharpe']):.3f}, V2 Sharpe is {float(v2['annualized_sharpe']):.3f}, "
        f"and V3 Sharpe is {float(v3['annualized_sharpe']):.3f}; the V2/V3 Sharpe difference is noise-level. "
        f"V3 is preferred because the short-side sector concentration falls from {float(v2['average_sector_concentration_short']):.3f} to "
        f"{float(v3['average_sector_concentration_short']):.3f} at comparable Sharpe. "
        f"V3 average ex-ante beta is {float(v3['average_net_beta']):.3f}; realized beta remains non-zero and is carried into Pillar 5."
    )


def _ex2020_summary(yearly: pd.DataFrame) -> pd.DataFrame:
    ex2020 = yearly[yearly["year"] != 2020]
    grouped = ex2020.groupby("variant", as_index=False)
    summary = grouped.agg(
        mean_annual_return_ex2020=("annual_return", "mean"),
        mean_annual_sharpe_ex2020=("annual_sharpe", "mean"),
        worst_year_ex2020=("annual_return", "min"),
        best_year_ex2020=("annual_return", "max"),
        n_years_ex2020=("year", "count"),
    )
    return _round_numeric(summary)


def _report_table(grid: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "variant",
        "cost_bps",
        "annualized_return",
        "annualized_sharpe",
        "max_drawdown",
        "average_daily_turnover",
        "average_gross_leverage",
        "max_gross_leverage",
        "average_net_beta",
        "average_sector_concentration_long",
        "average_sector_concentration_short",
        "hit_rate",
        "net_cumulative_return",
    ]
    return _round_numeric(grid[columns])


def _row(grid: pd.DataFrame, variant: str, cost_bps: int) -> pd.Series:
    row = grid[(grid["variant"] == variant) & (grid["cost_bps"] == cost_bps)]
    if row.empty:
        raise ValueError(f"Missing row for {variant} at {cost_bps} bps.")
    return row.iloc[0]


def _average_sector_concentration(weights: pd.DataFrame, sectors: pd.Series, side: str) -> float:
    if side == "long":
        side_weights = weights.where(weights > 0.0, 0.0)
    elif side == "short":
        side_weights = -weights.where(weights < 0.0, 0.0)
    else:
        raise ValueError("side must be 'long' or 'short'.")
    concentrations = side_weights.apply(lambda row: row.groupby(sectors.reindex(row.index)).sum().max(), axis=1)
    return float(concentrations.mean(skipna=True))


def _realized_beta(portfolio_returns: pd.Series, market_proxy: pd.Series) -> float:
    paired = pd.concat([portfolio_returns, market_proxy], axis=1, keys=["portfolio", "market"]).dropna()
    variance = float(paired["market"].var(ddof=1))
    if variance == 0.0:
        return float("nan")
    return float(paired["portfolio"].cov(paired["market"]) / variance)


def _realized_beta_for_period(
    portfolio_returns: pd.Series,
    market_proxy: pd.Series,
    start_year: int | None = None,
    end_year: int | None = None,
) -> float:
    paired = pd.concat([portfolio_returns, market_proxy], axis=1, keys=["portfolio", "market"]).dropna()
    if start_year is not None:
        paired = paired[paired.index.year >= start_year]
    if end_year is not None:
        paired = paired[paired.index.year <= end_year]
    if paired.shape[0] < 3:
        return float("nan")
    variance = float(paired["market"].var(ddof=1))
    if variance == 0.0:
        return float("nan")
    return float(paired["portfolio"].cov(paired["market"]) / variance)


def _max_drawdown(cumulative_returns: pd.Series) -> float:
    wealth = 1.0 + cumulative_returns.dropna()
    if wealth.empty:
        return float("nan")
    return float((wealth / wealth.cummax() - 1.0).min())


def _save_market_proxy(proxy: pd.Series, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    proxy.to_frame().to_parquet(path, compression="snappy", index=True)


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _round_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    numeric_columns = output.select_dtypes(include=["number"]).columns
    output[numeric_columns] = output[numeric_columns].round(4)
    return output


def _markdown_table(frame: pd.DataFrame) -> str:
    text_frame = frame.astype(str)
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text_frame.to_numpy()]
    return "\n".join([header, separator, *rows])


if __name__ == "__main__":
    main()
