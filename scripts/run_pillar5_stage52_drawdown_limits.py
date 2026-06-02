"""Run Pillar 5 Stage 5.2 drawdown and capital-at-risk diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import (  # noqa: E402
    PRIMARY_COST_BPS,
    BASELINE_VARIANT,
    RESULTS_DIR,
    STAGE51_GRID_PATH,
    STAGE52_EVENTS_PATH,
    STAGE52_LIMITS_PATH,
    STAGE52_RECONCILIATION_PATH,
    STAGE52_SUMMARY_PATH,
    load_or_build_baseline_artifacts,
    market_window_return,
    production_choice,
    production_scaled_returns,
    scale_return_stream,
    _markdown_table,
)
from scripts.run_pillar5_stage51_vol_targeting import build_vol_targeting_grid  # noqa: E402
from src.portfolio import drawdown_events, drawdown_series  # noqa: E402


DD_LIMITS = [
    ("soft_warning", -0.06),
    ("hard_stop_derisk_50", -0.12),
    ("kill_switch", -0.20),
]


def main() -> None:
    artifacts = load_or_build_baseline_artifacts()
    grid = _load_or_build_stage51_grid(artifacts.daily_returns)
    choice = production_choice(grid)
    returns = production_scaled_returns(artifacts.daily_returns, float(choice["leverage_scaler"]), PRIMARY_COST_BPS)
    events = build_drawdown_events(returns, artifacts.market_proxy)
    limits = build_limit_simulation(returns)
    reconciliation = build_dd_reconciliation(artifacts.daily_returns, float(choice["leverage_scaler"]))
    STAGE52_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGE52_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(STAGE52_EVENTS_PATH, index=False)
    limits.to_csv(STAGE52_LIMITS_PATH, index=False)
    reconciliation.to_csv(STAGE52_RECONCILIATION_PATH, index=False)
    STAGE52_SUMMARY_PATH.write_text(build_report(choice, events, limits, reconciliation), encoding="utf-8")
    print(events.to_string(index=False))
    print(limits.to_string(index=False))
    print(f"Saved {STAGE52_EVENTS_PATH.as_posix()}")
    print(f"Saved {STAGE52_LIMITS_PATH.as_posix()}")
    print(f"Saved {STAGE52_RECONCILIATION_PATH.as_posix()}")
    print(f"Saved {STAGE52_SUMMARY_PATH.as_posix()}")


def build_drawdown_events(returns: pd.Series, market_proxy: pd.Series) -> pd.DataFrame:
    events = drawdown_events(returns).sort_values("peak_to_trough").head(5).copy()
    rows = []
    for _, row in events.iterrows():
        recovery = row["recovery_date"]
        rows.append(
            {
                "start_date": _date_text(row["start_date"]),
                "trough_date": _date_text(row["trough_date"]),
                "recovery_date": "ongoing" if pd.isna(recovery) else _date_text(recovery),
                "peak_to_trough": float(row["peak_to_trough"]),
                "drawdown_duration_days": int(row["drawdown_duration_days"]),
                "recovery_duration_days": "" if pd.isna(row["recovery_duration_days"]) else int(row["recovery_duration_days"]),
                "market_proxy_return_same_window": market_window_return(market_proxy, row["start_date"], recovery),
            }
        )
    return pd.DataFrame(rows)


def build_limit_simulation(returns: pd.Series) -> pd.DataFrame:
    drawdowns = drawdown_series(returns)
    rows = []
    for name, threshold in DD_LIMITS:
        triggers = _threshold_crossings(drawdowns, threshold)
        future_returns = [_future_compound_return(returns, trigger_date, 60, scaler=1.0) for trigger_date in triggers]
        derisk_returns = [_future_compound_return(returns, trigger_date, 60, scaler=0.5) for trigger_date in triggers]
        valid_future = pd.Series(future_returns, dtype=float).dropna()
        valid_derisk = pd.Series(derisk_returns, dtype=float).dropna()
        fp_rate = float((valid_future > 0.0).mean()) if not valid_future.empty else 0.0
        rows.append(
            {
                "limit_line": name,
                "threshold": threshold,
                "n_triggers": int(len(triggers)),
                "fp_rate": fp_rate,
                "post_trigger_60d_mean_ret": float(valid_future.mean()) if not valid_future.empty else float("nan"),
                "with_derisk_vs_without": float(valid_derisk.mean() - valid_future.mean())
                if not valid_derisk.empty and not valid_future.empty
                else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def build_dd_reconciliation(daily_returns: pd.DataFrame, leverage_scaler: float) -> pd.DataFrame:
    """Reconcile Pillar 4 rolling-return DD with Stage 5 capital wealth DD."""
    pillar4_path = RESULTS_DIR / "pillar4_stage45_rolling_drawdown.csv"
    pillar4 = pd.read_csv(pillar4_path, parse_dates=["date"])
    pillar4 = pillar4[pillar4["variant"] == BASELINE_VARIANT].set_index("date").sort_index()
    uncosted = daily_returns["long_short_return"].dropna()
    rolling_return = (1.0 + uncosted).rolling(252, min_periods=60).apply(lambda values: values.prod(), raw=True) - 1.0
    rolling_dd_recomputed = (1.0 + rolling_return).div(1.0 + rolling_return.cummax()).sub(1.0)
    unsized_10bps = scale_return_stream(daily_returns, 1.0, PRIMARY_COST_BPS)["net_return"]
    sized_10bps = scale_return_stream(daily_returns, leverage_scaler, PRIMARY_COST_BPS)["net_return"]
    unsized_wealth_dd = drawdown_series(unsized_10bps)
    sized_wealth_dd = drawdown_series(sized_10bps)
    window_sized_wealth = (1.0 + sized_10bps.loc["2023-09-01":"2023-11-30"].fillna(0.0)).cumprod()
    window_sized_local_dd = window_sized_wealth.div(window_sized_wealth.cummax()).sub(1.0)
    frame = pd.DataFrame(
        {
            "pillar4_rolling12m_return_dd": pillar4["rolling_12m_drawdown"],
            "pillar4_rolling12m_return_dd_scaled_by_k": pillar4["rolling_12m_drawdown"] * leverage_scaler,
            "pillar4_rolling12m_return_dd_recomputed": rolling_dd_recomputed,
            "stage4_v3_2x_wealth_dd_10bps": unsized_wealth_dd,
            "stage5_sized_wealth_dd_10bps": sized_wealth_dd,
            "stage5_sized_window_local_dd_10bps": window_sized_local_dd,
        }
    ).loc["2023-09-01":"2023-11-30"]
    frame = frame.reset_index().rename(columns={"index": "date"})
    frame["leverage_scaler"] = leverage_scaler
    frame["note"] = (
        "Pillar4 rolling12m_return_dd is drawdown of trailing-252d return, not capital wealth DD; "
        "it should not be linearly scaled to infer kill-switch triggers."
    )
    return frame


def build_report(choice: pd.Series, events: pd.DataFrame, limits: pd.DataFrame, reconciliation: pd.DataFrame) -> str:
    recon = reconciliation.loc[reconciliation["pillar4_rolling12m_return_dd"].idxmin()]
    lines = [
        "# Pillar 5 Stage 5.2 Drawdown & Capital-at-Risk Summary",
        "",
        "## Setup",
        f"- Production sizing from Stage 5.1: target vol {float(choice['sigma_target']):.0%}, gross {float(choice['production_gross']):.2f}x.",
        f"- Returns use the {PRIMARY_COST_BPS} bps primary transaction cost assumption.",
        "",
        "## Top Drawdown Events",
        _markdown_table(events),
        "",
        "## Limit Simulation",
        _markdown_table(limits),
        "",
        "## Drawdown Reconciliation",
        f"- Daily reconciliation saved to `{STAGE52_RECONCILIATION_PATH.as_posix()}`.",
        f"- The lowest Pillar 4 rolling-return drawdown in the 2023-09/11 reconciliation window is {float(recon['pillar4_rolling12m_return_dd']):.1%} on {pd.Timestamp(recon['date']).date()}.",
        f"- On that same date, true Stage 4 V3 2x/10bps capital wealth DD is {float(recon['stage4_v3_2x_wealth_dd_10bps']):.1%}, and Stage 5 sized 1.405x/10bps capital wealth DD is {float(recon['stage5_sized_wealth_dd_10bps']):.1%}.",
        f"- Multiplying the rolling-return DD by k would imply {float(recon['pillar4_rolling12m_return_dd_scaled_by_k']):.1%}, but that is the wrong risk object.",
        "- The Pillar 4 `rolling_drawdown.csv` field is the drawdown of the trailing 252-day return series, not the capital wealth-curve drawdown used for production kill switches.",
        "- Therefore the 2023-10 ~-45% value is not comparable to Stage 5 capital DD and should not be multiplied by k to infer a -31% live capital drawdown.",
        "",
        "## Recommendation",
        _recommendation_text(limits),
        "",
    ]
    return "\n".join(lines)


def _recommendation_text(limits: pd.DataFrame) -> str:
    kill = limits[limits["limit_line"] == "kill_switch"].iloc[0]
    hard = limits[limits["limit_line"] == "hard_stop_derisk_50"].iloc[0]
    soft = limits[limits["limit_line"] == "soft_warning"].iloc[0]
    if int(kill["n_triggers"]) == 0:
        kill_text = "Keep the -20% kill switch; it was not triggered historically at production sizing."
    else:
        kill_text = f"Review the -20% kill switch because it triggered {int(kill['n_triggers'])} historical times."
    return (
        f"Keep the -6% soft warning as an operational early-warning line; it triggered {int(soft['n_triggers'])} times with "
        f"{float(soft['fp_rate']):.0%} positive 60-day reversals. Keep the -12% hard-stop de-risk line as a capital-at-risk control; "
        f"it triggered {int(hard['n_triggers'])} times and the 50% de-risk simulation changed average 60-day return by "
        f"{float(hard['with_derisk_vs_without']):.2%}. {kill_text}"
    )


def _load_or_build_stage51_grid(daily_returns: pd.DataFrame) -> pd.DataFrame:
    if STAGE51_GRID_PATH.exists():
        return pd.read_csv(STAGE51_GRID_PATH)
    grid = build_vol_targeting_grid(daily_returns)
    STAGE51_GRID_PATH.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(STAGE51_GRID_PATH, index=False)
    return grid


def _threshold_crossings(drawdowns: pd.Series, threshold: float) -> list[pd.Timestamp]:
    previous = drawdowns.shift(1).fillna(0.0)
    crossed = (drawdowns <= threshold) & (previous > threshold)
    return [pd.Timestamp(date) for date in drawdowns.index[crossed]]


def _future_compound_return(returns: pd.Series, trigger_date: pd.Timestamp, horizon_days: int, scaler: float) -> float:
    position = returns.index.get_loc(trigger_date)
    if isinstance(position, slice):
        position = position.start
    future = returns.iloc[int(position) + 1 : int(position) + 1 + horizon_days].dropna() * scaler
    if future.empty:
        return float("nan")
    return float((1.0 + future).prod() - 1.0)


def _date_text(value: object) -> str:
    return str(pd.Timestamp(value).date())


if __name__ == "__main__":
    main()
