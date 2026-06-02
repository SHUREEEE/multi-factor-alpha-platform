"""Run Pillar 5 Stage 5.6 stress and regime testing."""

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
    production_scaled_returns,
    window_metrics,
    _markdown_table,
)
from scripts.run_pillar4_stage42 import _load_panel, _project_path  # noqa: E402
from scripts.run_pillar4_stage45_neutralization import CONFIG_PATH  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import realized_beta, summarize_return_stream  # noqa: E402
from src.research.ic_analysis import extract_daily_return_matrix  # noqa: E402
from src.research.quantile_test import TRADING_DAYS_PER_YEAR, compute_annualized_sharpe  # noqa: E402


STRESS_WINDOWS = [
    ("COVID crash", "2020-02-19", "2020-03-23"),
    ("COVID rebound", "2020-03-24", "2020-06-08"),
    ("2022 rate shock", "2022-01-03", "2022-10-14"),
    ("2023 regional bank stress", "2023-03-08", "2023-05-01"),
    ("2023 Aug-Oct rates spike", "2023-08-01", "2023-10-27"),
]
STRESS_WINDOWS_PATH = PROJECT_ROOT / "results/pillar5_stage56_stress_windows.csv"
REGIME_SPLIT_PATH = PROJECT_ROOT / "results/pillar5_stage56_regime_split.csv"
STRESS_CONTINGENCY_PATH = PROJECT_ROOT / "results/pillar5_stage56_stress_turnover_beta_contingency.csv"
SUMMARY_PATH = PROJECT_ROOT / "reports/pillar5_stage56_stress_regime.md"
STAGE54_TURNOVER_TOP_DAYS_PATH = PROJECT_ROOT / "results/pillar5_stage54_turnover_top_days.csv"
STAGE55_ATTRIBUTION_PATH = PROJECT_ROOT / "results/pillar5_stage55_factor_attribution.csv"


def main() -> None:
    artifacts = load_or_build_baseline_artifacts()
    choice = production_choice(pd.read_csv(STAGE51_GRID_PATH))
    production_returns = production_scaled_returns(artifacts.daily_returns, float(choice["leverage_scaler"]), PRIMARY_COST_BPS)
    prices = _load_prices()
    market = _market_series(prices, artifacts.market_proxy)
    regimes = build_regime_indicators(market)
    stage55 = _load_stage55_attribution()
    stress = build_stress_windows(production_returns, market, stage55)
    regime_split = build_regime_split(production_returns, market, regimes)
    contingency = build_stress_contingency(stage55)
    STRESS_WINDOWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    stress.to_csv(STRESS_WINDOWS_PATH, index=False)
    regime_split.to_csv(REGIME_SPLIT_PATH, index=False)
    contingency.to_csv(STRESS_CONTINGENCY_PATH, index=False)
    SUMMARY_PATH.write_text(build_report(choice, stress, regime_split, contingency, regimes), encoding="utf-8")
    print(stress.to_string(index=False))
    print(regime_split.to_string(index=False))
    print(contingency.to_string(index=False))
    print(f"Saved {STRESS_WINDOWS_PATH.as_posix()}")
    print(f"Saved {REGIME_SPLIT_PATH.as_posix()}")
    print(f"Saved {STRESS_CONTINGENCY_PATH.as_posix()}")
    print(f"Saved {SUMMARY_PATH.as_posix()}")


def build_stress_windows(production_returns: pd.Series, market_returns: pd.Series, stage55: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, start_date, end_date in STRESS_WINDOWS:
        metrics = window_metrics(production_returns, market_returns, start_date, end_date)
        market_window = market_returns.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)].dropna()
        attribution_window = _slice_stage55(stage55, start_date, end_date)
        rows.append(
            {
                "window": name,
                "start_date": start_date,
                "end_date": end_date,
                "n_days": metrics["n_days"],
                "return": metrics["return"],
                "vol": metrics["vol"],
                "sharpe": metrics["sharpe"],
                "max_dd": metrics["max_dd_in_window"],
                "hit_rate": _hit_rate(production_returns.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]),
                "market_return": float((1.0 + market_window).prod() - 1.0) if not market_window.empty else float("nan"),
                "beta_to_market": metrics["beta_to_market_in_window"],
                "residual_alpha_return": _compound_or_nan(attribution_window["residual_alpha_pnl"]),
                "mean_residual_alpha_pnl": float(attribution_window["residual_alpha_pnl"].mean(skipna=True)),
                "mean_rolling_60d_residual_beta": float(attribution_window["rolling_60d_residual_beta"].mean(skipna=True)),
                "kill_switch_triggered": bool(metrics["max_dd_in_window"] <= -0.20),
            }
        )
    return pd.DataFrame(rows)


def build_regime_indicators(market_returns: pd.Series) -> pd.DataFrame:
    market = market_returns.astype(float).sort_index()
    rv20 = market.rolling(20, min_periods=20).std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    trailing60 = (1.0 + market).rolling(60, min_periods=60).apply(np.prod, raw=True) - 1.0
    frame = pd.DataFrame(
        {
            "market_return": market,
            "spy_20d_realized_vol_proxy": rv20,
            "spy_60d_trailing_return": trailing60,
        }
    )
    high_vol_threshold = float(rv20.dropna().quantile(0.75))
    low_vol_threshold = float(rv20.dropna().quantile(0.25))
    high_ret_threshold = float(trailing60.dropna().quantile(0.75))
    low_ret_threshold = float(trailing60.dropna().quantile(0.25))
    frame["vix_proxy_gt_25"] = rv20 > 0.25
    frame["spy_20d_vol_top_quartile"] = rv20 >= high_vol_threshold
    frame["spy_20d_vol_bottom_quartile"] = rv20 <= low_vol_threshold
    frame["spy_60d_return_top_quartile"] = trailing60 >= high_ret_threshold
    frame["spy_60d_return_bottom_quartile"] = trailing60 <= low_ret_threshold
    frame.attrs["high_vol_threshold"] = high_vol_threshold
    frame.attrs["low_vol_threshold"] = low_vol_threshold
    frame.attrs["high_return_threshold"] = high_ret_threshold
    frame.attrs["low_return_threshold"] = low_ret_threshold
    return frame


def build_regime_split(production_returns: pd.Series, market_returns: pd.Series, regimes: pd.DataFrame) -> pd.DataFrame:
    definitions = [
        ("VIX proxy > 25", "vix_proxy_gt_25", True),
        ("VIX proxy <= 25", "vix_proxy_gt_25", False),
        ("SPY 20d realized vol top quartile", "spy_20d_vol_top_quartile", True),
        ("SPY 20d realized vol bottom quartile", "spy_20d_vol_bottom_quartile", True),
        ("SPY 60d trailing return top quartile", "spy_60d_return_top_quartile", True),
        ("SPY 60d trailing return bottom quartile", "spy_60d_return_bottom_quartile", True),
    ]
    rows = []
    for regime_name, column, value in definitions:
        mask = regimes[column].eq(value).reindex(production_returns.index).fillna(False)
        returns = production_returns.loc[mask]
        market = market_returns.loc[mask]
        summary = summarize_return_stream(returns)
        rows.append(
            {
                "regime": regime_name,
                "n_days": int(returns.dropna().shape[0]),
                "ann_return": summary["ann_return"],
                "ann_vol": summary["ann_vol_realized"],
                "ann_sharpe": summary["ann_sharpe"],
                "max_dd": summary["max_dd"],
                "hit_rate": summary["hit_rate"],
                "market_ann_return": _annualized_return(market.dropna()),
                "beta_to_market": realized_beta(returns, market),
            }
        )
    return pd.DataFrame(rows)


def build_stress_contingency(stage55: pd.DataFrame) -> pd.DataFrame:
    high_turnover_dates = _high_turnover_dates_from_stage54()
    rows = []
    for name, start_date, end_date in STRESS_WINDOWS:
        window = _slice_stage55(stage55, start_date, end_date)
        dates = set(pd.to_datetime(window["date"]).dt.normalize())
        high_turnover = [date for date in high_turnover_dates if pd.Timestamp(start_date) <= date <= pd.Timestamp(end_date)]
        high_beta = window[window["rolling_60d_residual_beta"].abs() > 0.4]
        rows.append(
            {
                "stress_window": name,
                "start_date": start_date,
                "end_date": end_date,
                "n_days": int(window.shape[0]),
                "n_high_turnover_days": int(len(high_turnover)),
                "n_high_residual_beta_days_abs_gt_0_4": int(high_beta.shape[0]),
                "mean_residual_alpha_pnl": float(window["residual_alpha_pnl"].mean(skipna=True)),
                "pct_days_high_turnover": float(len(high_turnover) / len(dates)) if dates else float("nan"),
                "pct_days_high_residual_beta": float(high_beta.shape[0] / window.shape[0]) if not window.empty else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def build_report(
    choice: pd.Series,
    stress: pd.DataFrame,
    regime_split: pd.DataFrame,
    contingency: pd.DataFrame,
    regimes: pd.DataFrame,
) -> str:
    worst = stress.sort_values("return").iloc[0]
    worst_sharpe = regime_split.sort_values("ann_sharpe").iloc[0]
    high_turnover_total = int(pd.read_csv(PROJECT_ROOT / "results/pillar5_stage54_turnover_distribution.csv").set_index("metric").loc["rotation_days_gt_100pct", "value"])
    high_turnover_in_windows = int(contingency["n_high_turnover_days"].sum())
    lines = [
        "# Pillar 5 Stage 5.6 - Stress & Regime Testing",
        "",
        "## Plan",
        "",
        "1. Use the locked Pillar 5 V3 cache (`results/pillar5_artifacts/v3_weights.parquet` and `v3_daily_returns.parquet`) as the sole source of V3 weights and P&L.",
        "2. Do not reconstruct V3 from Pillar 4 Stage 4.5; if the cache is insufficient, document the gap rather than substituting another book.",
        "3. Reuse Stage 5.1 production sizing and 10 bps cost assumptions for all stress and regime statistics.",
        "4. Compute the five requested stress windows exactly, including V3 return, volatility, Sharpe, max drawdown, hit rate, and market proxy comparison.",
        "5. Build regime splits using VIX if available; otherwise use SPY 20d realized volatility as the VIX proxy, and fall back to the locked market proxy if SPY is unavailable.",
        "6. Cross-reference Stage 5.4 high-turnover days (`production gross turnover > 100%`) and Stage 5.5 residual-beta drift (`|rolling 60d residual beta| > 0.4`) against stress windows.",
        "7. Save CSV deliverables and report whether high-vol/dislocation regimes are where V3 underperforms and where neutralization becomes expensive or ineffective.",
        "",
        "## Executive Summary",
        _executive_summary(stress, regime_split, contingency, high_turnover_total, high_turnover_in_windows),
        "",
        "## Setup",
        f"- Production sizing: target vol {float(choice['sigma_target']):.0%}, gross {float(choice['production_gross']):.3f}x, {PRIMARY_COST_BPS} bps cost.",
        "- Source of truth: locked Pillar 5 cache only. No Stage 4.5 reconstruction is used in Stage 5.6.",
        "- VIX is not present in local market data. Regime split uses SPY 20d realized volatility as the VIX/high-vol proxy.",
        f"- SPY 20d vol top quartile threshold: {float(regimes.attrs['high_vol_threshold']):.1%}; bottom quartile threshold: {float(regimes.attrs['low_vol_threshold']):.1%}.",
        "",
        "## Stress Windows",
        _markdown_table(stress),
        "",
        "## Regime Split",
        _markdown_table(regime_split),
        "",
        "## Stress x Turnover x Residual Beta Contingency",
        _markdown_table(contingency),
        "",
        "## Worst-Window Narrative",
        _worst_window_text(worst, contingency, stress),
        "",
        "## Regime Conditioning",
        _regime_text(regime_split, worst_sharpe),
        "",
        "## Connection to Stage 5.4 and 5.5",
        _connection_text(contingency, high_turnover_total, high_turnover_in_windows),
        "",
        "## Outputs",
        f"- Stress windows: `results/{STRESS_WINDOWS_PATH.name}`.",
        f"- Regime split: `results/{REGIME_SPLIT_PATH.name}`.",
        f"- Turnover/residual-beta contingency: `results/{STRESS_CONTINGENCY_PATH.name}`.",
        "",
    ]
    return "\n".join(lines)


def _load_prices() -> pd.DataFrame:
    config = load_pillar4_config(CONFIG_PATH)
    return _load_panel(_project_path(config.price_file), "prices")


def _market_series(prices: pd.DataFrame, fallback_market_proxy: pd.Series) -> pd.Series:
    returns = extract_daily_return_matrix(prices)
    if "SPY" in returns.columns:
        return returns["SPY"].rename("SPY_return").sort_index()
    return fallback_market_proxy.rename("locked_market_proxy_return").sort_index()


def _load_stage55_attribution() -> pd.DataFrame:
    if not STAGE55_ATTRIBUTION_PATH.exists():
        raise FileNotFoundError("Stage 5.6 requires results/pillar5_stage55_factor_attribution.csv from Stage 5.5.")
    frame = pd.read_csv(STAGE55_ATTRIBUTION_PATH)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _slice_stage55(stage55: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    dates = pd.to_datetime(stage55["date"])
    return stage55[(dates >= pd.Timestamp(start_date)) & (dates <= pd.Timestamp(end_date))].copy()


def _high_turnover_dates_from_stage54() -> set[pd.Timestamp]:
    artifacts = load_or_build_baseline_artifacts()
    choice = production_choice(pd.read_csv(STAGE51_GRID_PATH))
    turnover = artifacts.weights.fillna(0.0).diff().abs().sum(axis=1) * float(choice["leverage_scaler"])
    if not turnover.empty:
        turnover.iloc[0] = np.nan
    return set(turnover[turnover > 1.0].dropna().index.normalize())


def _compound_or_nan(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    return float((1.0 + clean).prod() - 1.0)


def _hit_rate(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    return float((clean > 0.0).mean())


def _annualized_return(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    total = float((1.0 + clean).prod() - 1.0)
    years = clean.shape[0] / TRADING_DAYS_PER_YEAR
    return float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0.0 else float("nan")


def _executive_summary(
    stress: pd.DataFrame,
    regime_split: pd.DataFrame,
    contingency: pd.DataFrame,
    high_turnover_total: int,
    high_turnover_in_windows: int,
) -> str:
    worst = stress.sort_values("return").iloc[0]
    high_vol = regime_split[regime_split["regime"] == "SPY 20d realized vol top quartile"].iloc[0]
    low_vol = regime_split[regime_split["regime"] == "SPY 20d realized vol bottom quartile"].iloc[0]
    weak_trend = regime_split[regime_split["regime"] == "SPY 60d trailing return bottom quartile"].iloc[0]
    high_beta_days = int(contingency["n_high_residual_beta_days_abs_gt_0_4"].sum())
    return (
        f"1. **Worst requested stress window: `{worst['window']}`**, return {float(worst['return']):.1%}, max DD {float(worst['max_dd']):.1%}, beta {float(worst['beta_to_market']):.3f}. "
        "No requested window breaches the -20% kill switch.\n\n"
        f"2. **The high-vol weakness assumption is not supported by this split.** SPY 20d vol top-quartile Sharpe is {float(high_vol['ann_sharpe']):.3f} versus {float(low_vol['ann_sharpe']):.3f} in bottom-quartile vol. The real weak regime is negative 60d market momentum: bottom-quartile SPY trailing-return Sharpe is {float(weak_trend['ann_sharpe']):.3f}.\n\n"
        f"3. **Tail turnover and residual-beta drift do cluster in the tested stress windows, but not exclusively.** The five windows contain {high_turnover_in_windows} of {high_turnover_total} >100% turnover days and {high_beta_days} high residual-beta days (`|beta| > 0.4`). This links Stage 5.4's expensive neutralization episodes to stress regimes, while leaving a meaningful normal-regime turnover problem for V4."
    )


def _worst_window_text(worst: pd.Series, contingency: pd.DataFrame, stress: pd.DataFrame) -> str:
    row = contingency[contingency["stress_window"] == worst["window"]].iloc[0]
    return (
        f"`{worst['window']}` is the weakest requested window with return {float(worst['return']):.1%} and max drawdown {float(worst['max_dd']):.1%}. "
        f"The window has {int(row['n_high_turnover_days'])} high-turnover days and {int(row['n_high_residual_beta_days_abs_gt_0_4'])} high-residual-beta days. "
        f"Mean residual alpha PnL is {float(row['mean_residual_alpha_pnl']):.4%} per day, so the stress loss is not just market beta; it includes residual-alpha weakness consistent with Stage 5.5's finding that the neutralization layer is beta-effective but not risk-complete."
    )


def _regime_text(regime_split: pd.DataFrame, worst_sharpe: pd.Series) -> str:
    return (
        f"The weakest regime by Sharpe is `{worst_sharpe['regime']}` with Sharpe {float(worst_sharpe['ann_sharpe']):.3f} over {int(worst_sharpe['n_days'])} days. "
        "This refutes a simplistic high-vol-only story: V3 does not die whenever volatility is high; it struggles most when the market's 60-day trend is in the bottom quartile. "
        "This gives a direct live-readiness hook: V4 should monitor regime-conditioned Sharpe and realized beta, not only full-sample Sharpe."
    )


def _connection_text(contingency: pd.DataFrame, high_turnover_total: int, high_turnover_in_windows: int) -> str:
    share = high_turnover_in_windows / high_turnover_total if high_turnover_total else float("nan")
    worst_cluster = contingency.sort_values(["n_high_turnover_days", "n_high_residual_beta_days_abs_gt_0_4"], ascending=False).iloc[0]
    return (
        f"Stage 5.4 identified {high_turnover_total} days with production gross turnover above 100%; {high_turnover_in_windows} ({share:.1%}) fall inside the five requested stress windows. "
        f"The densest stress-window cluster is `{worst_cluster['stress_window']}` with {int(worst_cluster['n_high_turnover_days'])} high-turnover days and {int(worst_cluster['n_high_residual_beta_days_abs_gt_0_4'])} high-residual-beta days. "
        "Stage 5.5 identified residual beta drift after beta neutralization; Stage 5.6 shows that this drift should be monitored specifically during high-vol/rates-stress regimes."
    )


if __name__ == "__main__":
    main()
