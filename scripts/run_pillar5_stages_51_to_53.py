"""Run Pillar 5 Stages 5.1 through 5.3 and write the cross-stage summary."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import (  # noqa: E402
    CROSS_STAGE_SUMMARY_PATH,
    PRIMARY_COST_BPS,
    STAGE51_GRID_PATH,
    STAGE52_LIMITS_PATH,
    STAGE52_RECONCILIATION_PATH,
    STAGE53_ATTRIBUTION_PATH,
    STAGE53_BETA_SHOCKS_PATH,
    STAGE53_BORROW_PATH,
    STAGE53_HISTORICAL_PATH,
    load_or_build_baseline_artifacts,
    production_choice,
)
from scripts.run_pillar5_stage51_vol_targeting import main as run_stage51  # noqa: E402
from scripts.run_pillar5_stage52_drawdown_limits import main as run_stage52  # noqa: E402
from scripts.run_pillar5_stage53_stress_testing import main as run_stage53  # noqa: E402


def main() -> None:
    load_or_build_baseline_artifacts()
    run_stage51()
    run_stage52()
    run_stage53()
    write_cross_stage_summary()
    print(f"Saved {CROSS_STAGE_SUMMARY_PATH.as_posix()}")


def write_cross_stage_summary() -> None:
    grid = pd.read_csv(STAGE51_GRID_PATH)
    limits = pd.read_csv(STAGE52_LIMITS_PATH)
    historical = pd.read_csv(STAGE53_HISTORICAL_PATH)
    beta_shocks = pd.read_csv(STAGE53_BETA_SHOCKS_PATH)
    borrow = pd.read_csv(STAGE53_BORROW_PATH)
    attribution = pd.read_csv(STAGE53_ATTRIBUTION_PATH)
    reconciliation = pd.read_csv(STAGE52_RECONCILIATION_PATH, parse_dates=["date"])
    choice = production_choice(grid)
    worst_window = historical.sort_values("return").iloc[0]
    beta_loss = beta_shocks[(beta_shocks["beta_assumption"] == "post_2020") & (beta_shocks["market_shock"] == -0.20)].iloc[0]
    root_cause = _one_line_root_cause(historical, attribution)
    dd_recon = reconciliation.loc[reconciliation["pillar4_rolling12m_return_dd"].idxmin()]
    soft = _limit_row(limits, "soft_warning")
    hard = _limit_row(limits, "hard_stop_derisk_50")
    kill = _limit_row(limits, "kill_switch")
    lines = [
        "Pillar 5 Stages 5.1-5.3 Summary",
        "================================",
        "",
        "Production Sizing (from 5.1):",
        f"  Target vol         : {float(choice['sigma_target']):.0%}",
        f"  Leverage scaler    : k = {float(choice['leverage_scaler']):.2f}",
        f"  Production gross   : {float(choice['production_gross']):.2f} x",
        f"  Sharpe @ {PRIMARY_COST_BPS} bps    : {float(choice['ann_sharpe']):.3f}",
        f"  Max DD             : {float(choice['max_dd']):.1%}",
        "",
        "Risk Limits (from 5.2):",
        f"  Soft warning       : {float(soft['threshold']):.1%}  (n_triggers = {int(soft['n_triggers'])}, fp_rate = {float(soft['fp_rate']):.0%})",
        f"  Hard stop          : {float(hard['threshold']):.1%}  (n_triggers = {int(hard['n_triggers'])}, fp_rate = {float(hard['fp_rate']):.0%})",
        f"  Kill switch        : {float(kill['threshold']):.1%} (n_triggers = {int(kill['n_triggers'])}, fp_rate = {float(kill['fp_rate']):.0%})",
        "",
        "Stress Results (from 5.3):",
        f"  Worst historical window : {worst_window['window']}, return = {float(worst_window['return']):.1%}, dd = {float(worst_window['max_dd_in_window']):.1%}",
        f"  Beta shock -20%, gross-adjusted loss = {float(beta_loss['expected_portfolio_loss']):.1%}",
        f"  Borrow cost break-even  : {float(borrow['break_even_borrow_cost_bps'].iloc[0]):.0f} bps",
        f"  2023-10 root cause      : {root_cause}",
        f"  2023-10 DD reconciliation: Pillar4 rolling-return DD {float(dd_recon['pillar4_rolling12m_return_dd']):.1%} on {dd_recon['date'].date()} maps to sized capital DD {float(dd_recon['stage5_sized_wealth_dd_10bps']):.1%}, not {float(dd_recon['pillar4_rolling12m_return_dd_scaled_by_k']):.1%}.",
        "",
        "Open items going into 5.4 / 5.5:",
        "  - Add explicit factor-sleeve attribution for 2023-10 if per-factor production books are promoted to first-class artifacts.",
        "  - Decide whether the production gross sanity band should be tied to realized vol or capped by policy.",
        "  - Monitor realized beta under the volume-weighted proxy alongside the original equal-weight proxy.",
        "",
    ]
    CROSS_STAGE_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CROSS_STAGE_SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def _limit_row(limits: pd.DataFrame, name: str) -> pd.Series:
    row = limits[limits["limit_line"] == name]
    if row.empty:
        raise ValueError(f"Missing limit row: {name}")
    return row.iloc[0]


def _one_line_root_cause(historical: pd.DataFrame, attribution: pd.DataFrame) -> str:
    event = historical[historical["window"] == "2023-10 deep DD"]
    sector = attribution[attribution["bucket_type"] == "sector"].sort_values("contribution").head(1)
    sector_name = str(sector.iloc[0]["bucket"]) if not sector.empty else "Unknown"
    beta = float(event.iloc[0]["beta_to_market_in_window"]) if not event.empty else float("nan")
    return f"sector/factor stress led by {sector_name}; window beta {beta:.2f}, not a pure market-beta shock."


if __name__ == "__main__":
    main()
