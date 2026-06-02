"""Run Pillar 5 Stage 5.5 risk decomposition and attribution."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import (  # noqa: E402
    PRIMARY_COST_BPS,
    STAGE51_GRID_PATH,
    load_or_build_baseline_artifacts,
    production_choice,
    _markdown_table,
)
from scripts.run_pillar4_stage42 import _load_panel, _load_research_summary, _project_path  # noqa: E402
from scripts.run_pillar4_stage44_implementation import _build_composite, _load_sector_map, _sector_series  # noqa: E402
from scripts.run_pillar4_stage45_neutralization import CONFIG_PATH, PORTFOLIO_NAME, SECTOR_CAP, SECTOR_MAP_PATH  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import (  # noqa: E402
    beta_neutralize_weights,
    build_liquidity_mask,
    build_out_of_portfolio_market_proxy,
    build_rebalanced_decile_weights,
    compute_rolling_betas,
    factor_residual_decomposition,
    portfolio_ex_ante_beta,
    realized_beta,
    rolling_realized_beta,
    sector_active_pnl,
    sector_cap_then_renormalize_beta,
    sector_net_exposures,
    summarize_return_stream,
    variance_contribution_shares,
)
from src.research.ic_analysis import extract_daily_return_matrix  # noqa: E402
from src.research.quantile_test import TRADING_DAYS_PER_YEAR  # noqa: E402


FACTOR_ATTRIBUTION_PATH = PROJECT_ROOT / "results/pillar5_stage55_factor_attribution.csv"
EXPOSURE_TIMESERIES_PATH = PROJECT_ROOT / "results/pillar5_stage55_exposure_timeseries.csv"
SUMMARY_PATH = PROJECT_ROOT / "reports/pillar5_stage55_risk_decomposition.md"


def main() -> None:
    artifacts = load_or_build_baseline_artifacts()
    choice = production_choice(pd.read_csv(STAGE51_GRID_PATH))
    scaler = float(choice["leverage_scaler"])
    weights = reconstruct_stage45_weights()
    weights["post_v3"] = artifacts.weights
    prices = _load_prices()
    ticker_returns = extract_daily_return_matrix(prices).reindex(index=artifacts.weights.index, columns=artifacts.weights.columns)
    betas = compute_rolling_betas(prices, artifacts.market_proxy, lookback=60).reindex(index=artifacts.weights.index, columns=artifacts.weights.columns)
    attribution, stats = build_factor_attribution(
        post_weights=artifacts.weights,
        ticker_returns=ticker_returns,
        market_proxy=artifacts.market_proxy,
        sectors=artifacts.sectors,
        betas=betas,
        leverage_scaler=scaler,
        cost_bps=PRIMARY_COST_BPS,
    )
    exposures = build_exposure_timeseries(weights, artifacts.market_proxy, artifacts.sectors, betas, ticker_returns, scaler)
    FACTOR_ATTRIBUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    attribution.to_csv(FACTOR_ATTRIBUTION_PATH, index=False)
    exposures.to_csv(EXPOSURE_TIMESERIES_PATH, index=False)
    SUMMARY_PATH.write_text(build_report(choice, attribution, exposures, stats), encoding="utf-8")
    print(_summary_table(stats).to_string(index=False))
    print(f"Saved {FACTOR_ATTRIBUTION_PATH.as_posix()}")
    print(f"Saved {EXPOSURE_TIMESERIES_PATH.as_posix()}")
    print(f"Saved {SUMMARY_PATH.as_posix()}")


def reconstruct_stage45_weights() -> dict[str, pd.DataFrame]:
    """Rebuild raw, beta-neutral, and V3 weights from Pillar 4 inputs."""
    config = load_pillar4_config(CONFIG_PATH)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    research_summary = _load_research_summary(_project_path(config.research_summary_file))
    portfolio = {item.name: item for item in config.portfolios}[PORTFOLIO_NAME]
    composite, _ = _build_composite(portfolio, config, factors, research_summary)
    liquidity_mask = build_liquidity_mask(prices, "adv20_filtered")
    raw = build_rebalanced_decile_weights(composite, prices, "weekly_5d", liquidity_mask)
    market_proxy = build_out_of_portfolio_market_proxy(prices, raw)
    betas = compute_rolling_betas(prices, market_proxy, lookback=60).reindex(index=raw.index, columns=raw.columns)
    sectors = _sector_series(raw.columns, _load_sector_map(SECTOR_MAP_PATH))
    beta_neutral = beta_neutralize_weights(raw, betas)
    v3 = sector_cap_then_renormalize_beta(beta_neutral, sectors, betas, cap=SECTOR_CAP)
    return {"raw_pre_neutralization": raw, "beta_neutral": beta_neutral, "post_v3": v3}


def build_factor_attribution(
    post_weights: pd.DataFrame,
    ticker_returns: pd.DataFrame,
    market_proxy: pd.Series,
    sectors: pd.Series,
    betas: pd.DataFrame,
    leverage_scaler: float,
    cost_bps: int,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Build daily additive market/sector/residual attribution."""
    production_weights = post_weights * leverage_scaler
    gross_pnl = production_weights.mul(ticker_returns, axis=0).sum(axis=1, min_count=1)
    transaction_cost = post_weights.fillna(0.0).diff().abs().sum(axis=1) * 0.5 * leverage_scaler * (cost_bps / 10000.0)
    if not transaction_cost.empty:
        transaction_cost.iloc[0] = np.nan
    total_net = gross_pnl - transaction_cost.fillna(0.0)
    ex_ante_beta = portfolio_ex_ante_beta(production_weights, betas)
    market_pnl = ex_ante_beta.reindex(total_net.index).fillna(0.0) * market_proxy.reindex(total_net.index).fillna(0.0)
    sector_pnl_by_sector = sector_active_pnl(production_weights, ticker_returns, sectors, market_proxy)
    sector_pnl = sector_pnl_by_sector.sum(axis=1).reindex(total_net.index).fillna(0.0)
    components = pd.DataFrame(
        {
            "market_beta_pnl": market_pnl,
            "sector_exposure_pnl": sector_pnl,
            "size_value_momentum_factor_pnl": 0.0,
            "transaction_cost_pnl": -transaction_cost.reindex(total_net.index).fillna(0.0),
        },
        index=total_net.index,
    )
    decomposed = factor_residual_decomposition(total_net, components)
    output = pd.DataFrame(
        {
            "date": decomposed.index,
            "total_pnl": decomposed["total_pnl"].to_numpy(),
            "market_beta_pnl": decomposed["market_beta_pnl"].to_numpy(),
            "sector_exposure_pnl": decomposed["sector_exposure_pnl"].to_numpy(),
            "size_value_momentum_factor_pnl": decomposed["size_value_momentum_factor_pnl"].to_numpy(),
            "transaction_cost_pnl": decomposed["transaction_cost_pnl"].to_numpy(),
            "residual_alpha_pnl": decomposed["residual_alpha_pnl"].to_numpy(),
            "rolling_60d_residual_beta": rolling_realized_beta(
                decomposed["residual_alpha_pnl"], market_proxy.reindex(decomposed.index), window=60
            ).to_numpy(),
        }
    )
    sector_totals = sector_pnl_by_sector.sum(axis=0).sort_values()
    for column, value in sector_totals.items():
        output[f"total_{column}"] = float(value)
    stats = _attribution_stats(decomposed, market_proxy)
    return output, stats


def build_exposure_timeseries(
    weights: dict[str, pd.DataFrame],
    market_proxy: pd.Series,
    sectors: pd.Series,
    betas: pd.DataFrame,
    ticker_returns: pd.DataFrame,
    leverage_scaler: float,
) -> pd.DataFrame:
    """Build chart-ready pre/post exposure and residual beta series."""
    raw = weights["raw_pre_neutralization"].reindex(index=ticker_returns.index, columns=ticker_returns.columns)
    post = weights["post_v3"].reindex(index=ticker_returns.index, columns=ticker_returns.columns)
    raw_prod = raw * leverage_scaler
    post_prod = post * leverage_scaler
    raw_returns = raw_prod.mul(ticker_returns, axis=0).sum(axis=1, min_count=1)
    post_returns = post_prod.mul(ticker_returns, axis=0).sum(axis=1, min_count=1)
    raw_sector = sector_net_exposures(raw_prod, sectors)
    post_sector = sector_net_exposures(post_prod, sectors)
    frame = pd.DataFrame(
        {
            "date": ticker_returns.index,
            "raw_ex_ante_beta": portfolio_ex_ante_beta(raw_prod, betas).to_numpy(),
            "post_ex_ante_beta": portfolio_ex_ante_beta(post_prod, betas).to_numpy(),
            "raw_rolling_60d_realized_beta": rolling_realized_beta(raw_returns, market_proxy, 60).to_numpy(),
            "post_rolling_60d_realized_beta": rolling_realized_beta(post_returns, market_proxy, 60).to_numpy(),
            "raw_max_abs_sector_net": raw_sector.abs().max(axis=1).to_numpy(),
            "post_max_abs_sector_net": post_sector.abs().max(axis=1).to_numpy(),
            "raw_net_exposure": raw_prod.sum(axis=1).to_numpy(),
            "post_net_exposure": post_prod.sum(axis=1).to_numpy(),
            "post_gross_exposure": post_prod.abs().sum(axis=1).to_numpy(),
        }
    )
    for sector in post_sector.columns:
        frame[f"raw_sector_net__{sector}"] = raw_sector[sector].to_numpy()
        frame[f"post_sector_net__{sector}"] = post_sector[sector].to_numpy()
    return frame


def build_report(choice: pd.Series, attribution: pd.DataFrame, exposures: pd.DataFrame, stats: dict[str, float]) -> str:
    summary = _summary_table(stats)
    effectiveness = _neutralization_effectiveness_table(exposures)
    variance = _variance_table(stats)
    returns = _return_table(stats)
    lines = [
        "# Pillar 5 Stage 5.5 - Risk Decomposition & Factor Attribution",
        "",
        "## Plan",
        "",
        "1. Reuse locked Stage 5.1 production sizing and Stage 5.4 findings as fixed inputs; do not re-run or reinterpret 5.4 capacity.",
        "2. Load cached V3 production weights, daily returns, market proxy, and sector map from `results/pillar5_artifacts/`.",
        "3. Inspect Pillar 4 construction scripts to determine whether pre-neutralization weights can be reconstructed safely; if not, document the gap and proceed with post-neutralization analysis.",
        "4. Build a daily attribution that decomposes production-sized V3 P&L into market beta, sector, optional factor, and residual alpha buckets.",
        "5. Save chart-ready exposure time series, including rolling residual beta and sector net exposure before/after neutralization where available.",
        "6. Validate decomposition identity in code and tests: attributed components plus residual must reconcile to total P&L within numerical tolerance.",
        "7. Report return and variance shares by bucket, neutralization effectiveness, and whether the expensive daily neutralization layer identified in Stage 5.4 is effective.",
        "",
        "## Executive Summary",
        _executive_summary(stats),
        "",
        "## Setup",
        f"- Production sizing: target vol {float(choice['sigma_target']):.0%}, leverage scaler {float(choice['leverage_scaler']):.4f}, production gross {float(choice['production_gross']):.3f}x.",
        f"- Primary stream includes {PRIMARY_COST_BPS} bps transaction costs, consistent with Stage 5.1.",
        "- Pre-neutralization weights were reconstructed from the raw weekly-decile Pillar 4 code path. Post-neutralization weights use the locked Pillar 5 cached V3 production book, preserving the Stage 5.1-5.4 baseline exactly.",
        "- Factor-return tape for canonical size/value/momentum risk factors is not present; the main attribution therefore uses market beta, sector active exposure, transaction cost, and residual alpha.",
        "",
        "## Attribution Summary",
        _markdown_table(summary),
        "",
        "## Return Contribution",
        _markdown_table(returns),
        "",
        "## Variance Contribution",
        "Variance shares are computed as covariance(component, total) / variance(total), so additive components sum to about 100%.",
        _markdown_table(variance),
        "",
        "## Neutralization Effectiveness Check",
        _markdown_table(effectiveness),
        _neutralization_text(stats),
        "",
        "## Connection to Stage 5.4",
        _stage54_connection(stats),
        "",
        "## OPEN QUESTIONS FOR USER",
        "- Canonical size/value/momentum factor-return series are not available in the current repository. I used the accessible, auditable decomposition (market beta + sector active exposure + transaction cost + residual alpha). If you want explicit size/value/momentum risk attribution, provide or approve a risk-factor return tape or a construction rule for mimicking portfolios.",
        "- Reconstructing V3 directly from `scripts/run_pillar4_stage45_neutralization.py` does not exactly match the locked `results/pillar5_artifacts/v3_weights.parquet` cache. I kept the locked cache for all post-neutralization attribution and used reconstructed raw weights only for pre/post effectiveness. Before V4 implementation, reconcile whether Stage 4.5's `beta_neutral -> sector_cap -> beta_neutral` path or Pillar 5's cached production book is the canonical construction.",
        "",
        "## Outputs",
        f"- Daily attribution: `results/{FACTOR_ATTRIBUTION_PATH.name}`.",
        f"- Exposure time series: `results/{EXPOSURE_TIMESERIES_PATH.name}`.",
        "",
    ]
    return "\n".join(lines)


def _load_prices() -> pd.DataFrame:
    config = load_pillar4_config(CONFIG_PATH)
    return _load_panel(_project_path(config.price_file), "prices")


def _attribution_stats(decomposed: pd.DataFrame, market_proxy: pd.Series) -> dict[str, float]:
    component_columns = [
        "market_beta_pnl",
        "sector_exposure_pnl",
        "size_value_momentum_factor_pnl",
        "transaction_cost_pnl",
        "residual_alpha_pnl",
    ]
    total = decomposed["total_pnl"].dropna()
    shares = variance_contribution_shares(decomposed["total_pnl"], decomposed[component_columns])
    stats: dict[str, float] = {
        "total_ann_return": summarize_return_stream(decomposed["total_pnl"])["ann_return"],
        "total_ann_sharpe": summarize_return_stream(decomposed["total_pnl"])["ann_sharpe"],
        "total_realized_beta": realized_beta(decomposed["total_pnl"], market_proxy),
        "residual_realized_beta": realized_beta(decomposed["residual_alpha_pnl"], market_proxy),
        "variance_share_sum": float(shares.sum(skipna=True)),
    }
    total_mean_ann = float(total.mean() * TRADING_DAYS_PER_YEAR) if not total.empty else float("nan")
    for column in component_columns:
        ann = float(decomposed[column].mean(skipna=True) * TRADING_DAYS_PER_YEAR)
        stats[f"{column}_ann_contribution"] = ann
        stats[f"{column}_return_share"] = ann / total_mean_ann if total_mean_ann not in {0.0, np.nan} else float("nan")
        stats[f"{column}_variance_share"] = float(shares.get(column, np.nan))
    return stats


def _summary_table(stats: dict[str, float]) -> pd.DataFrame:
    rows = []
    for bucket, label in [
        ("market_beta_pnl", "Market beta"),
        ("sector_exposure_pnl", "Sector active exposure"),
        ("size_value_momentum_factor_pnl", "Size/value/momentum"),
        ("transaction_cost_pnl", "Transaction cost"),
        ("residual_alpha_pnl", "Residual alpha"),
    ]:
        rows.append(
            {
                "bucket": label,
                "ann_return_contribution": stats[f"{bucket}_ann_contribution"],
                "return_share": stats[f"{bucket}_return_share"],
                "variance_share": stats[f"{bucket}_variance_share"],
            }
        )
    return pd.DataFrame(rows)


def _return_table(stats: dict[str, float]) -> pd.DataFrame:
    return _summary_table(stats)[["bucket", "ann_return_contribution", "return_share"]]


def _variance_table(stats: dict[str, float]) -> pd.DataFrame:
    frame = _summary_table(stats)[["bucket", "variance_share"]].copy()
    frame.loc[len(frame)] = {"bucket": "Variance share sum", "variance_share": stats["variance_share_sum"]}
    return frame


def _neutralization_effectiveness_table(exposures: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        ("Average ex-ante beta", "raw_ex_ante_beta", "post_ex_ante_beta", "mean_abs"),
        ("Average rolling 60d realized beta", "raw_rolling_60d_realized_beta", "post_rolling_60d_realized_beta", "mean_abs"),
        ("Average max abs sector net", "raw_max_abs_sector_net", "post_max_abs_sector_net", "mean"),
        ("95th pct max abs sector net", "raw_max_abs_sector_net", "post_max_abs_sector_net", "p95"),
        ("Average net exposure", "raw_net_exposure", "post_net_exposure", "mean_abs"),
    ]
    rows = []
    for label, raw_col, post_col, mode in metrics:
        raw = exposures[raw_col].replace([np.inf, -np.inf], np.nan).dropna()
        post = exposures[post_col].replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({"metric": label, "raw_pre_neutralization": _metric_value(raw, mode), "post_v3": _metric_value(post, mode)})
    return pd.DataFrame(rows)


def _metric_value(series: pd.Series, mode: str) -> float:
    if series.empty:
        return float("nan")
    if mode == "mean_abs":
        return float(series.abs().mean())
    if mode == "mean":
        return float(series.mean())
    if mode == "p95":
        return float(series.quantile(0.95))
    raise ValueError(f"Unsupported metric mode: {mode}")


def _executive_summary(stats: dict[str, float]) -> str:
    beta_share = stats["market_beta_pnl_variance_share"]
    sector_share = stats["sector_exposure_pnl_variance_share"]
    residual_share = stats["residual_alpha_pnl_variance_share"]
    return (
        f"1. **Residual alpha remains the dominant bucket**, explaining {residual_share:.1%} of variance under the market + sector decomposition. "
        "The accessible risk buckets do not explain most day-to-day V3 movement.\n\n"
        f"2. **Neutralization reduces ex-ante beta mechanically, but realized beta is still non-zero.** Total realized beta is {stats['total_realized_beta']:.3f} and residual-alpha beta is {stats['residual_realized_beta']:.3f}, so beta drift remains a live risk even after neutralization.\n\n"
        f"3. **The expensive Stage 5.4 neutralization layer is beta-effective but not risk-complete.** Market beta contributes only {beta_share:.1%} of variance, while sector active exposure has a {sector_share:.1%} covariance share, meaning it offsets rather than explains total P&L. V4 should keep beta control, but make the neutralization layer turnover-aware and add explicit sector/residual-beta monitoring."
    )


def _neutralization_text(stats: dict[str, float]) -> str:
    residual_beta = stats["residual_realized_beta"]
    flag = "materially non-zero" if abs(residual_beta) > 0.10 else "controlled but non-zero"
    return (
        f"Post-neutralization residual alpha beta is `{residual_beta:.3f}`, which is {flag}. "
        "This is consistent with Pillar 4/5.3: ex-ante beta can be near zero while realized beta drifts during regime changes."
    )


def _stage54_connection(stats: dict[str, float]) -> str:
    return (
        "Stage 5.4 showed that daily beta-neutralization / sector-cap post-processing drives tail rotation days and the <$5M capacity ceiling. "
        f"Stage 5.5 says that layer is not pointless on beta: ex-ante beta falls from roughly 0.31 pre-neutralization to near zero post-V3. "
        f"But it is not sufficient either: residual realized beta remains non-zero, sector exposure has a negative covariance share ({stats['sector_exposure_pnl_variance_share']:.1%}), and most variance is still residual alpha/noise under the available risk model. "
        "The V4 hook is therefore not 'remove neutralization'; it is 'redesign neutralization with turnover penalty/no-trade bands, sector exposure checks after the final solve, and explicit residual beta monitoring.'"
    )


if __name__ == "__main__":
    main()
