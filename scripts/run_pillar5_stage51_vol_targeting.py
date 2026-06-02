"""Run Pillar 5 Stage 5.1 volatility targeting for the locked V3 baseline."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import (  # noqa: E402
    BASELINE_VARIANT,
    COST_BPS_LEVELS,
    PRIMARY_COST_BPS,
    RESEARCH_GROSS,
    SIGMA_TARGETS,
    STAGE51_GRID_PATH,
    STAGE51_ROLLING_VOL_PATH,
    STAGE51_SUMMARY_PATH,
    gross_return_vol,
    load_or_build_baseline_artifacts,
    production_choice,
    scale_return_stream,
    summarize_return_stream,
    _markdown_table,
)
from src.portfolio import annualized_volatility  # noqa: E402
from src.research.quantile_test import TRADING_DAYS_PER_YEAR  # noqa: E402


def main() -> None:
    artifacts = load_or_build_baseline_artifacts()
    grid = build_vol_targeting_grid(artifacts.daily_returns)
    realized_vol = build_realized_volatility_diagnostics(artifacts.daily_returns)
    STAGE51_GRID_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGE51_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(STAGE51_GRID_PATH, index=False)
    realized_vol.to_csv(STAGE51_ROLLING_VOL_PATH, index=False)
    STAGE51_SUMMARY_PATH.write_text(build_report(grid, realized_vol), encoding="utf-8")
    print(grid.to_string(index=False))
    print(f"Saved {STAGE51_GRID_PATH.as_posix()}")
    print(f"Saved {STAGE51_ROLLING_VOL_PATH.as_posix()}")
    print(f"Saved {STAGE51_SUMMARY_PATH.as_posix()}")


def build_vol_targeting_grid(daily_returns: pd.DataFrame) -> pd.DataFrame:
    realized_vol = gross_return_vol(daily_returns)
    rows = []
    for sigma_target in SIGMA_TARGETS:
        leverage_scaler = sigma_target / realized_vol
        production_gross = leverage_scaler * RESEARCH_GROSS
        for cost_bps in COST_BPS_LEVELS:
            scaled = scale_return_stream(daily_returns, leverage_scaler, cost_bps)
            summary = summarize_return_stream(scaled["net_return"])
            rows.append(
                {
                    "sigma_target": sigma_target,
                    "cost_bps": cost_bps,
                    "leverage_scaler": leverage_scaler,
                    "production_gross": production_gross,
                    "ann_return": summary["ann_return"],
                    "ann_sharpe": summary["ann_sharpe"],
                    "max_dd": summary["max_dd"],
                    "dd_duration_days": summary["dd_duration_days"],
                    "hit_rate": summary["hit_rate"],
                    "ann_vol_realized": summary["ann_vol_realized"],
                }
            )
    return pd.DataFrame(rows)


def build_realized_volatility_diagnostics(daily_returns: pd.DataFrame) -> pd.DataFrame:
    returns = daily_returns["long_short_return"].dropna()
    rows = [
        {"metric": "full_sample", "period": "full", "ann_vol": annualized_volatility(returns)},
        {"metric": "rolling_60d_mean", "period": "full", "ann_vol": float(returns.rolling(60).std().mean() * TRADING_DAYS_PER_YEAR**0.5)},
        {"metric": "rolling_60d_max", "period": "full", "ann_vol": float(returns.rolling(60).std().max() * TRADING_DAYS_PER_YEAR**0.5)},
        {"metric": "rolling_252d_mean", "period": "full", "ann_vol": float(returns.rolling(252).std().mean() * TRADING_DAYS_PER_YEAR**0.5)},
        {"metric": "rolling_252d_max", "period": "full", "ann_vol": float(returns.rolling(252).std().max() * TRADING_DAYS_PER_YEAR**0.5)},
    ]
    for year, values in returns.groupby(returns.index.year):
        rows.append({"metric": "calendar_year", "period": str(year), "ann_vol": annualized_volatility(values)})
    return pd.DataFrame(rows)


def build_report(grid: pd.DataFrame, realized_vol: pd.DataFrame) -> str:
    choice = production_choice(grid)
    table = grid.copy()
    table["sigma_target"] = table["sigma_target"].map(lambda value: f"{value:.0%}")
    lines = [
        "# Pillar 5 Stage 5.1 Volatility Targeting Summary",
        "",
        "## Production Choice",
        f"- Baseline variant: `{BASELINE_VARIANT}`.",
        f"- Selected target volatility: {float(choice['sigma_target']):.0%}.",
        f"- Leverage scaler: k = {float(choice['leverage_scaler']):.4f}.",
        f"- Production gross: {float(choice['production_gross']):.4f}x.",
        f"- Sharpe at {PRIMARY_COST_BPS} bps: {float(choice['ann_sharpe']):.3f}.",
        f"- Max drawdown at {PRIMARY_COST_BPS} bps: {float(choice['max_dd']):.1%}.",
        "",
        "## Volatility Diagnostics",
        _markdown_table(realized_vol),
        "",
        "## Targeting Grid",
        _markdown_table(table),
        "",
        "## Recommendation",
        _recommendation_text(grid),
        "",
        "## Static Volatility Caveat",
        _static_vol_caveat(grid, realized_vol),
        "",
    ]
    return "\n".join(lines)


def _recommendation_text(grid: pd.DataFrame) -> str:
    choice = production_choice(grid)
    within_expected = 0.8 <= float(choice["production_gross"]) <= 1.3
    expectation_text = "inside" if within_expected else "outside"
    return (
        f"Use the {float(choice['sigma_target']):.0%} production volatility setting because it is the selected post-cost Sharpe/DD row under the "
        f"{PRIMARY_COST_BPS} bps primary cost assumption. The resulting production gross is {float(choice['production_gross']):.2f}x, "
        f"{expectation_text} the pre-task 0.8-1.3x sanity band; this is driven by the realized full-sample volatility of the 2x research stream."
    )


def _static_vol_caveat(grid: pd.DataFrame, realized_vol: pd.DataFrame) -> str:
    choice = production_choice(grid)
    rolling_max = realized_vol[(realized_vol["metric"] == "rolling_60d_max") & (realized_vol["period"] == "full")]
    if rolling_max.empty:
        return "Production sizing is static and should be revisited with a dynamic volatility overlay in Pillar 5 live-readiness."
    sized_rolling_max = float(rolling_max.iloc[0]["ann_vol"]) * float(choice["leverage_scaler"])
    return (
        f"Production uses static {float(choice['production_gross']):.3f}x gross leverage based on full-sample volatility. "
        f"Realized volatility will exceed the {float(choice['sigma_target']):.0%} target in high-volatility regimes: the 60-day max annualized vol scales to approximately {sized_rolling_max:.1%}. "
        "A dynamic volatility-targeting overlay that scales leverage by trailing realized vol should be evaluated in Pillar 5 live-readiness."
    )


if __name__ == "__main__":
    main()
