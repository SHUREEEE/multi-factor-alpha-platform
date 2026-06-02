"""Shared helpers for Pillar 5 production sizing and stress tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_pillar4_stage42 import _load_panel, _load_research_summary, _portfolio_weights, _project_path  # noqa: E402
from scripts.run_pillar4_stage44_implementation import _build_composite, _load_sector_map, _sector_series  # noqa: E402
from scripts.run_pillar4_stage45_neutralization import CONFIG_PATH, PORTFOLIO_NAME, SECTOR_CAP, SECTOR_MAP_PATH  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import (  # noqa: E402
    annualized_volatility,
    backtest_from_weights,
    build_liquidity_mask,
    build_out_of_portfolio_market_proxy,
    build_rebalanced_decile_weights,
    compute_rolling_betas,
    realized_beta,
    scale_return_stream,
    sector_cap_then_renormalize_beta,
    summarize_return_stream,
)
from src.research.ic_analysis import extract_daily_return_matrix  # noqa: E402
from src.research.quantile_test import TRADING_DAYS_PER_YEAR, compute_annualized_sharpe  # noqa: E402


BASELINE_VARIANT = "V3_beta_neutral_sector_capped_fm_weekly_adv20"
RESEARCH_GROSS = 2.0
PRIMARY_COST_BPS = 10
SIGMA_TARGETS = [0.06, 0.08, 0.10, 0.12]
COST_BPS_LEVELS = [5, 10, 20]
BORROW_COST_BPS = [0, 50, 100, 200]
RESULTS_DIR = PROJECT_ROOT / "results"
REPORTS_DIR = PROJECT_ROOT / "reports"
ARTIFACT_DIR = RESULTS_DIR / "pillar5_artifacts"
ARTIFACT_DAILY_RETURNS = ARTIFACT_DIR / "v3_daily_returns.parquet"
ARTIFACT_WEIGHTS = ARTIFACT_DIR / "v3_weights.parquet"
ARTIFACT_MARKET_PROXY = ARTIFACT_DIR / "market_proxy.parquet"
ARTIFACT_CAP_WEIGHT_PROXY = ARTIFACT_DIR / "cap_weight_market_proxy.parquet"
ARTIFACT_SECTORS = ARTIFACT_DIR / "v3_sector_map.csv"
STAGE51_GRID_PATH = RESULTS_DIR / "pillar5_stage51_vol_targeting_grid.csv"
STAGE51_ROLLING_VOL_PATH = RESULTS_DIR / "pillar5_stage51_realized_volatility.csv"
STAGE51_SUMMARY_PATH = REPORTS_DIR / "pillar5_stage51_vol_targeting_summary.md"
STAGE52_EVENTS_PATH = RESULTS_DIR / "pillar5_stage52_drawdown_events.csv"
STAGE52_LIMITS_PATH = RESULTS_DIR / "pillar5_stage52_dd_limit_simulation.csv"
STAGE52_RECONCILIATION_PATH = RESULTS_DIR / "pillar5_stage52_dd_reconciliation.csv"
STAGE52_SUMMARY_PATH = REPORTS_DIR / "pillar5_stage52_risk_limits_summary.md"
STAGE53_HISTORICAL_PATH = RESULTS_DIR / "pillar5_stage53_stress_historical.csv"
STAGE53_BETA_SHOCKS_PATH = RESULTS_DIR / "pillar5_stage53_stress_beta_shocks.csv"
STAGE53_BORROW_PATH = RESULTS_DIR / "pillar5_stage53_stress_borrow_cost.csv"
STAGE53_PROXY_PATH = RESULTS_DIR / "pillar5_stage53_stress_proxy_quality.csv"
STAGE53_ATTRIBUTION_PATH = RESULTS_DIR / "pillar5_stage53_event_2023_10_attribution.csv"
STAGE53_SUMMARY_PATH = REPORTS_DIR / "pillar5_stage53_stress_summary.md"
CROSS_STAGE_SUMMARY_PATH = REPORTS_DIR / "pillar5_stages_5_1_to_5_3_summary.md"


@dataclass(frozen=True)
class BaselineArtifacts:
    """Cached baseline daily return stream, weights, market proxies, and sectors."""

    daily_returns: pd.DataFrame
    weights: pd.DataFrame
    market_proxy: pd.Series
    cap_weight_market_proxy: pd.Series
    sectors: pd.Series


def load_or_build_baseline_artifacts(force: bool = False) -> BaselineArtifacts:
    """Load cached V3 artifacts or rebuild them from Pillar 4 inputs."""
    paths = [ARTIFACT_DAILY_RETURNS, ARTIFACT_WEIGHTS, ARTIFACT_MARKET_PROXY, ARTIFACT_CAP_WEIGHT_PROXY, ARTIFACT_SECTORS]
    if not force and all(path.exists() for path in paths):
        return _load_artifacts()
    artifacts = _build_baseline_artifacts()
    _save_artifacts(artifacts)
    return artifacts


def production_choice(grid: pd.DataFrame) -> pd.Series:
    """Select the production sigma row from a Stage 5.1 grid."""
    primary = grid[grid["cost_bps"] == PRIMARY_COST_BPS].copy()
    candidates = primary[primary["max_dd"] > -0.20]
    if candidates.empty:
        candidates = primary
    best_sharpe = candidates["ann_sharpe"].max()
    tied = candidates[np.isclose(candidates["ann_sharpe"], best_sharpe, rtol=0.0, atol=1e-12)]
    if tied.empty:
        tied = candidates.sort_values("ann_sharpe", ascending=False).head(1)
    preferred = tied[tied["sigma_target"] == 0.10]
    if not preferred.empty:
        return preferred.iloc[0]
    return tied.sort_values("sigma_target", ascending=False).iloc[0]


def production_scaled_returns(daily_returns: pd.DataFrame, leverage_scaler: float, cost_bps: int = PRIMARY_COST_BPS) -> pd.Series:
    """Return production-sized net returns for a cost assumption."""
    return scale_return_stream(daily_returns, leverage_scaler, cost_bps)["net_return"]


def gross_return_vol(daily_returns: pd.DataFrame) -> float:
    """Annualized volatility of the uncosted 2x-gross baseline stream."""
    return annualized_volatility(daily_returns["long_short_return"])


def market_window_return(market_proxy: pd.Series, start_date: pd.Timestamp, end_date: object) -> float:
    """Compound market proxy return over a drawdown window."""
    if pd.isna(end_date):
        end_date = market_proxy.dropna().index.max()
    window = market_proxy.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)].dropna()
    if window.empty:
        return float("nan")
    return float((1.0 + window).prod() - 1.0)


def window_metrics(portfolio_returns: pd.Series, market_returns: pd.Series, start_date: str, end_date: str) -> dict[str, float | int]:
    """Compute stress-window metrics on an inclusive date range."""
    returns = portfolio_returns.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)].dropna()
    market = market_returns.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)].dropna()
    if returns.empty:
        return {
            "return": float("nan"),
            "max_dd_in_window": float("nan"),
            "vol": float("nan"),
            "sharpe": float("nan"),
            "beta_to_market_in_window": float("nan"),
            "n_days": 0,
        }
    return {
        "return": float((1.0 + returns).prod() - 1.0),
        "max_dd_in_window": summarize_return_stream(returns)["max_dd"],
        "vol": annualized_volatility(returns),
        "sharpe": compute_annualized_sharpe(returns),
        "beta_to_market_in_window": realized_beta(returns, market),
        "n_days": int(returns.shape[0]),
    }


def _build_baseline_artifacts() -> BaselineArtifacts:
    config = load_pillar4_config(CONFIG_PATH)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    research_summary = _load_research_summary(_project_path(config.research_summary_file))
    portfolio = {item.name: item for item in config.portfolios}[PORTFOLIO_NAME]
    composite, _ = _build_composite(portfolio, config, factors, research_summary)
    liquidity_mask = build_liquidity_mask(prices, "adv20_filtered")
    raw_weights = build_rebalanced_decile_weights(composite, prices, "weekly_5d", liquidity_mask)
    market_proxy = build_out_of_portfolio_market_proxy(prices, raw_weights)
    betas = compute_rolling_betas(prices, market_proxy, lookback=60).reindex(index=raw_weights.index, columns=raw_weights.columns)
    sectors = _sector_series(raw_weights.columns, _load_sector_map(SECTOR_MAP_PATH))
    weights = sector_cap_then_renormalize_beta(raw_weights, sectors, betas, cap=SECTOR_CAP)
    backtest = backtest_from_weights(weights, prices)
    cap_weight_proxy = _build_cap_weight_proxy(prices, weights)
    return BaselineArtifacts(
        daily_returns=backtest.daily_returns,
        weights=weights,
        market_proxy=market_proxy.reindex(backtest.daily_returns.index),
        cap_weight_market_proxy=cap_weight_proxy.reindex(backtest.daily_returns.index),
        sectors=sectors,
    )


def _build_cap_weight_proxy(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    returns = extract_daily_return_matrix(prices).reindex(index=weights.index, columns=weights.columns)
    dollar_volume = (prices["adj_close"] * prices["volume"]).unstack("ticker").astype(float).reindex(index=weights.index, columns=weights.columns)
    proxy = returns.mul(dollar_volume, axis=0).sum(axis=1, min_count=1).div(dollar_volume.sum(axis=1).replace(0.0, np.nan))
    proxy.name = "cap_weight_proxy_return"
    proxy.index.name = "date"
    return proxy.astype(float)


def _save_artifacts(artifacts: BaselineArtifacts) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts.daily_returns.to_parquet(ARTIFACT_DAILY_RETURNS, compression="snappy", index=True)
    artifacts.weights.to_parquet(ARTIFACT_WEIGHTS, compression="snappy", index=True)
    artifacts.market_proxy.rename("market_proxy_return").to_frame().to_parquet(ARTIFACT_MARKET_PROXY, compression="snappy", index=True)
    artifacts.cap_weight_market_proxy.rename("cap_weight_proxy_return").to_frame().to_parquet(
        ARTIFACT_CAP_WEIGHT_PROXY, compression="snappy", index=True
    )
    artifacts.sectors.rename("sector").to_frame().reset_index(names="ticker").to_csv(ARTIFACT_SECTORS, index=False)


def _load_artifacts() -> BaselineArtifacts:
    daily_returns = pd.read_parquet(ARTIFACT_DAILY_RETURNS).sort_index()
    weights = pd.read_parquet(ARTIFACT_WEIGHTS).sort_index()
    market_proxy = pd.read_parquet(ARTIFACT_MARKET_PROXY).iloc[:, 0].sort_index()
    cap_weight_proxy = pd.read_parquet(ARTIFACT_CAP_WEIGHT_PROXY).iloc[:, 0].sort_index()
    sector_frame = pd.read_csv(ARTIFACT_SECTORS)
    sectors = sector_frame.set_index("ticker")["sector"].reindex(weights.columns).fillna("Unknown")
    return BaselineArtifacts(
        daily_returns=daily_returns,
        weights=weights,
        market_proxy=market_proxy,
        cap_weight_market_proxy=cap_weight_proxy,
        sectors=sectors,
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    text_frame = frame.copy()
    numeric_columns = text_frame.select_dtypes(include=["number"]).columns
    text_frame[numeric_columns] = text_frame[numeric_columns].round(4)
    text_frame = text_frame.astype(str)
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = ["| " + " | ".join(str(item) for item in row) + " |" for row in text_frame.to_numpy()]
    return "\n".join([header, separator, *rows])
