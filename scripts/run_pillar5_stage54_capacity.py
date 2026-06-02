"""Run Pillar 5 Stage 5.4 capacity and live-readiness analysis."""

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
    _markdown_table,
)
from scripts.run_pillar4_stage42 import _load_panel, _project_path  # noqa: E402
from scripts.run_pillar4_stage45_neutralization import CONFIG_PATH  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import (  # noqa: E402
    borrow_feasible_flag,
    compute_participation,
    compute_turnover_impact_cost,
    summarize_return_stream,
    top_short_concentration,
)
from src.research.ic_analysis import extract_daily_return_matrix  # noqa: E402
from src.research.quantile_test import TRADING_DAYS_PER_YEAR  # noqa: E402


AUM_LEVELS = [
    5_000_000,
    10_000_000,
    25_000_000,
    50_000_000,
    100_000_000,
    250_000_000,
    500_000_000,
    1_000_000_000,
    2_000_000_000,
    5_000_000_000,
]
PARTICIPATION_CAPS = [0.01, 0.05, 0.10]
IMPACT_COEFFICIENTS = [0.3, 0.5, 1.0]
PAPER_SHARPE_BASELINE = 0.498
CAPACITY_CURVE_PATH = PROJECT_ROOT / "results/pillar5_stage54_capacity_curve.csv"
PER_NAME_CAPACITY_PATH = PROJECT_ROOT / "results/pillar5_stage54_per_name_capacity.csv"
SHORT_BOOK_PATH = PROJECT_ROOT / "results/pillar5_stage54_short_book_constraints.csv"
IMPACT_AUDIT_PATH = PROJECT_ROOT / "results/pillar5_stage54_impact_formula_audit.csv"
TURNOVER_DISTRIBUTION_PATH = PROJECT_ROOT / "results/pillar5_stage54_turnover_distribution.csv"
TURNOVER_TOP_DAYS_PATH = PROJECT_ROOT / "results/pillar5_stage54_turnover_top_days.csv"
SUMMARY_PATH = PROJECT_ROOT / "reports/pillar5_stage54_capacity_summary.md"


def main() -> None:
    artifacts = load_or_build_baseline_artifacts()
    choice = production_choice(pd.read_csv(STAGE51_GRID_PATH))
    gross = float(choice["production_gross"])
    normalized_weights = artifacts.weights / 2.0
    production_returns = production_scaled_returns(artifacts.daily_returns, float(choice["leverage_scaler"]), PRIMARY_COST_BPS)
    prices = _load_prices()
    adv20_usd = _adv20_usd(prices).reindex(index=normalized_weights.index, columns=normalized_weights.columns)
    daily_vol = _daily_vol(prices).reindex(index=normalized_weights.index, columns=normalized_weights.columns)
    borrow_tiers = _borrow_tiers(adv20_usd)
    capacity_curve = build_capacity_curve(normalized_weights, adv20_usd, daily_vol, production_returns, gross, borrow_tiers)
    impact_audit = build_impact_formula_audit(normalized_weights, adv20_usd, daily_vol, gross)
    turnover_distribution, turnover_top_days = build_turnover_diagnostics(normalized_weights, gross)
    per_name = build_per_name_capacity(normalized_weights, adv20_usd, gross)
    short_book = build_short_book_constraints(normalized_weights, gross, borrow_tiers)
    CAPACITY_CURVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    capacity_curve.to_csv(CAPACITY_CURVE_PATH, index=False)
    impact_audit.to_csv(IMPACT_AUDIT_PATH, index=False)
    turnover_distribution.to_csv(TURNOVER_DISTRIBUTION_PATH, index=False)
    turnover_top_days.to_csv(TURNOVER_TOP_DAYS_PATH, index=False)
    per_name.to_csv(PER_NAME_CAPACITY_PATH, index=False)
    short_book.to_csv(SHORT_BOOK_PATH, index=False)
    SUMMARY_PATH.write_text(
        build_report(capacity_curve, per_name, short_book, impact_audit, turnover_distribution, turnover_top_days, gross),
        encoding="utf-8",
    )
    print(capacity_curve.to_string(index=False))
    print(f"Saved {CAPACITY_CURVE_PATH.as_posix()}")
    print(f"Saved {IMPACT_AUDIT_PATH.as_posix()}")
    print(f"Saved {TURNOVER_DISTRIBUTION_PATH.as_posix()}")
    print(f"Saved {TURNOVER_TOP_DAYS_PATH.as_posix()}")
    print(f"Saved {PER_NAME_CAPACITY_PATH.as_posix()}")
    print(f"Saved {SHORT_BOOK_PATH.as_posix()}")
    print(f"Saved {SUMMARY_PATH.as_posix()}")


def build_capacity_curve(
    weights: pd.DataFrame,
    adv20_usd: pd.DataFrame,
    daily_vol: pd.DataFrame,
    production_returns: pd.Series,
    gross: float,
    borrow_tiers: pd.Series,
) -> pd.DataFrame:
    rows = []
    ann_return_gross = float(summarize_return_stream(production_returns)["ann_return"])
    for aum_usd in AUM_LEVELS:
        participation = compute_participation(weights, adv20_usd, aum_usd, gross)
        participation_stats = _participation_stats(participation)
        borrow = _borrow_row(weights, gross, borrow_tiers, aum_usd)
        for cap in PARTICIPATION_CAPS:
            naive = _naive_capacity_stats(weights, adv20_usd, gross, cap)
            for impact_c in IMPACT_COEFFICIENTS:
                impact_cost = compute_turnover_impact_cost(weights, adv20_usd, daily_vol, aum_usd, gross, impact_c)
                net_returns = production_returns.reindex(impact_cost.index) - impact_cost.fillna(0.0)
                summary = summarize_return_stream(net_returns)
                rows.append(
                    {
                        "AUM_usd": aum_usd,
                        "participation_cap": cap,
                        "impact_coefficient": impact_c,
                        "gross": gross,
                        "mean_participation": participation_stats["mean"],
                        "p95_participation": participation_stats["p95"],
                        "p99_participation": participation_stats["p99"],
                        "max_participation": participation_stats["max"],
                        "pct_days_above_participation_cap": _pct_days_above_cap(participation, cap),
                        "naive_capacity_p50_usd": naive["p50"],
                        "naive_capacity_p05_usd": naive["p05"],
                        "naive_capacity_worst_day_usd": naive["worst"],
                        "naive_long_capacity_worst_day_usd": naive["long_worst"],
                        "naive_short_capacity_worst_day_usd": naive["short_worst"],
                        "mean_impact_bps": float(impact_cost.mean(skipna=True) * 10000.0),
                        "total_impact_drag_ann_bps": float(impact_cost.mean(skipna=True) * TRADING_DAYS_PER_YEAR * 10000.0),
                        "ann_return_gross": ann_return_gross,
                        "ann_return_net": summary["ann_return"],
                        "ann_sharpe_net": summary["ann_sharpe"],
                        "sharpe_decay_pct_vs_paper": (PAPER_SHARPE_BASELINE - float(summary["ann_sharpe"])) / PAPER_SHARPE_BASELINE,
                        "htb_share_short": borrow["htb_share"],
                        "top10_short_concentration": borrow["top10_concentration"],
                        "borrow_feasible": borrow["borrow_feasible"],
                    }
                )
    return pd.DataFrame(rows)


def build_per_name_capacity(weights: pd.DataFrame, adv20_usd: pd.DataFrame, gross: float) -> pd.DataFrame:
    mean_abs_weight = weights.abs().mean(skipna=True).sort_values(ascending=False)
    rows = []
    participation_500m = compute_participation(weights, adv20_usd, 500_000_000, gross)
    for ticker in mean_abs_weight.head(30).index:
        mean_weight = float((weights[ticker] * gross).mean(skipna=True))
        mean_abs = float(mean_abs_weight.loc[ticker])
        mean_adv = float(adv20_usd[ticker].mean(skipna=True))
        ceiling = mean_adv * 0.05 / (gross * mean_abs) if mean_abs > 0.0 else float("nan")
        rows.append(
            {
                "ticker": ticker,
                "mean_weight": mean_weight,
                "mean_abs_weight": mean_abs * gross,
                "mean_adv20_usd": mean_adv,
                "implied_individual_ceiling_at_5pct_adv": ceiling,
                "pct_days_above_5pct_participation_at_500M": float((participation_500m[ticker] > 0.05).mean()),
            }
        )
    return pd.DataFrame(rows)


def build_impact_formula_audit(weights: pd.DataFrame, adv20_usd: pd.DataFrame, daily_vol: pd.DataFrame, gross: float) -> pd.DataFrame:
    """Dump single-day impact formula terms for review."""
    target_dates = [pd.Timestamp("2023-06-15")]
    turnover = weights.fillna(0.0).diff().abs().sum(axis=1) * gross
    largest_turnover_date = turnover.loc["2023"].idxmax()
    if largest_turnover_date not in target_dates:
        target_dates.append(pd.Timestamp(largest_turnover_date))
    rows = []
    for date in target_dates:
        rows.extend(_impact_audit_rows_for_day(weights, adv20_usd, daily_vol, gross, date))
    return pd.DataFrame(rows)


def build_short_book_constraints(weights: pd.DataFrame, gross: float, borrow_tiers: pd.Series) -> pd.DataFrame:
    rows = []
    for aum_usd in AUM_LEVELS:
        row = _borrow_row(weights, gross, borrow_tiers, aum_usd)
        rows.append(
            {
                "AUM_usd": aum_usd,
                "n_short_names": row["n_short_names"],
                "short_gross_usd": aum_usd * gross / 2.0,
                "htb_notional_usd": row["htb_share"] * aum_usd * gross / 2.0,
                "htb_share": row["htb_share"],
                "top10_concentration": row["top10_concentration"],
                "borrow_feasible": row["borrow_feasible"],
            }
        )
    return pd.DataFrame(rows)


def build_turnover_diagnostics(weights: pd.DataFrame, gross: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    turnover_1x = weights.fillna(0.0).diff().abs().sum(axis=1)
    turnover_gross = turnover_1x * gross
    if not turnover_gross.empty:
        turnover_1x.iloc[0] = np.nan
        turnover_gross.iloc[0] = np.nan
    turnover_frame = pd.DataFrame({"turnover_1x": turnover_1x, "production_gross_turnover": turnover_gross}).dropna()
    turnover_frame["is_rebalance_day"] = _is_weekly_rebalance_day(turnover_frame.index)
    turnover_frame["weekday"] = turnover_frame.index.day_name()
    turnover_frame["month"] = turnover_frame.index.month
    summary = _turnover_summary_rows(turnover_frame)
    top_days = _top_turnover_days(turnover_frame, weights, gross)
    return summary, top_days


def build_report(
    capacity_curve: pd.DataFrame,
    per_name: pd.DataFrame,
    short_book: pd.DataFrame,
    impact_audit: pd.DataFrame,
    turnover_distribution: pd.DataFrame,
    turnover_top_days: pd.DataFrame,
    gross: float,
) -> str:
    base = capacity_curve[(capacity_curve["participation_cap"] == 0.05) & (capacity_curve["impact_coefficient"] == 0.5)].copy()
    capacity_ceiling = _capacity_ceiling(base)
    recommended_low, recommended_high = _recommended_range(capacity_ceiling)
    borrow_ceiling = _borrow_hard_ceiling(short_book)
    first_constraint = _binding_constraint(capacity_curve, short_book)
    sensitivity = _sensitivity_table(capacity_curve)
    curve_table = base[
        [
            "AUM_usd",
            "ann_sharpe_net",
            "sharpe_decay_pct_vs_paper",
            "p95_participation",
            "max_participation",
            "pct_days_above_participation_cap",
            "naive_capacity_p50_usd",
            "naive_capacity_p05_usd",
            "naive_capacity_worst_day_usd",
            "htb_share_short",
            "top10_short_concentration",
            "borrow_feasible",
        ]
    ]
    lines = [
        "# Pillar 5 Stage 5.4 Capacity & Live-Readiness Summary",
        "",
        "## Executive Summary",
        "Stage 5.4 surfaced three independent findings:",
        "",
        "1. **Capacity ceiling <$5M** under live-readiness rules (Sharpe decay <20%, participation cap, borrow feasibility). Binding constraints are impact drag and short-book borrow feasibility.",
        "",
        "2. **Impact drag is driven by tail rotation days, not normal-day trading.** Median daily turnover is 5.4%, but p95 is 106% and 181 days exceed 100% gross turnover. The turnover diagnostic isolates the source: non-rebalance-day mean turnover is about 4x rebalance-day mean turnover, indicating the daily beta-neutralization / sector-cap re-solve, not the weekly signal reshuffle, is the dominant turnover source. This is a V3 portfolio-construction issue addressable in V4 via a turnover penalty or no-trade band in the neutralization optimizer.",
        "",
        "3. **Short book has structural concentration.** Top-10 short concentration is 48.7% and HTB-proxy share is 25.5%, independent of AUM. This fails prime-broker neutrality regardless of capacity sizing and should be addressed in V4 via an explicit short-side concentration constraint.",
        "",
        "The capacity number in item 1 is conditional on item 2: if V4 fixes neutralization-layer turnover, the impact-based ceiling should revise materially upward. The structural short concentration in item 3 is unconditional.",
        "",
        "## Headline",
        f"- Capacity ceiling (Sharpe decay < 20%): `{_fmt_usd(capacity_ceiling)}` under the base c=0.5, 5% participation-cap scenario.",
        f"- Recommended AUM range: `{_fmt_usd(recommended_low)} - {_fmt_usd(recommended_high)}`.",
        f"- Hard ceiling (borrow infeasible): `{_fmt_usd(borrow_ceiling)}`.",
        f"- Binding constraint: `{first_constraint}`.",
        "- Interim interpretation: under the specified live-readiness rules, V3 is not institution-ready as-is. The impact finding is driven by tail rotation days and is conditional on the turnover diagnostic below; the short-book concentration finding is unconditional.",
        "",
        "## Capacity Curve",
        f"Paper Sharpe baseline is {PAPER_SHARPE_BASELINE:.3f}; the 20% decay line is {PAPER_SHARPE_BASELINE * 0.8:.3f}. Production gross is {gross:.3f}x.",
        _markdown_table(curve_table),
        "",
        "## Constraint Trigger Points",
        _constraint_text(capacity_curve, short_book),
        "",
        "## Impact Formula Audit",
        "Single-day audit rows decompose participation, impact bps, `|Delta w|`, and NAV-bps cost for AUM=$100M, c=0.5. `delta_weight_gross` sums to portfolio gross turnover; `cost_bps_of_nav` sums to that day's impact drag.",
        _markdown_table(impact_audit.head(40)),
        "",
        "## Turnover Distribution Diagnostic",
        "This separates normal-day impact from tail rotation-day impact. Production gross turnover is computed from normalized 1x weights multiplied by 1.405x production gross.",
        _turnover_diagnostic_text(turnover_distribution, turnover_top_days),
        _markdown_table(turnover_distribution),
        "",
        "### Top Rotation Days",
        _markdown_table(turnover_top_days),
        "",
        "## Structural Short-Book Concentration Constraint",
        _short_concentration_text(short_book),
        "",
        "## Impact Coefficient Sensitivity",
        _markdown_table(sensitivity),
        "",
        "## Top Per-Name Capacity Bottlenecks",
        _markdown_table(per_name.head(10)),
        "",
        "## Short Book Constraints",
        _markdown_table(short_book),
        "",
        "## Caveats",
        "- Square-root impact is a first-order approximation; live impact depends on order schedule (VWAP/TWAP/POV), intraday liquidity, spread, and crowding.",
        "- Borrow availability is proxied by average dollar-volume quintiles because live float, utilization, and rebate data are unavailable; live capacity is subject to prime-broker confirmation.",
        "- ADV20 is treated as a stationary liquidity estimate; live capacity should re-evaluate ADV in real time, especially around earnings and index events.",
        "- Impact is applied to `|Delta weight|` turnover, not gross exposure. Participation is computed as `(AUM x gross x |w|) / ADV20`.",
        "",
    ]
    return "\n".join(lines)


def _load_prices() -> pd.DataFrame:
    config = load_pillar4_config(CONFIG_PATH)
    return _load_panel(_project_path(config.price_file), "prices")


def _adv20_usd(prices: pd.DataFrame) -> pd.DataFrame:
    dollar_volume = (prices["adj_close"] * prices["volume"]).unstack("ticker").astype(float).sort_index()
    return dollar_volume.rolling(20, min_periods=20).mean()


def _daily_vol(prices: pd.DataFrame) -> pd.DataFrame:
    returns = extract_daily_return_matrix(prices).astype(float).sort_index()
    return returns.rolling(60, min_periods=20).std().shift(1)


def _borrow_tiers(adv20_usd: pd.DataFrame) -> pd.Series:
    mean_adv = adv20_usd.mean(skipna=True).replace([np.inf, -np.inf], np.nan).dropna()
    quintile = pd.qcut(mean_adv.rank(method="first"), 5, labels=False) + 1
    tiers = pd.Series("normal", index=mean_adv.index, dtype=object)
    tiers.loc[quintile <= 2] = "htb"
    tiers.loc[quintile >= 4] = "easy"
    return tiers


def _impact_audit_rows_for_day(
    weights: pd.DataFrame,
    adv20_usd: pd.DataFrame,
    daily_vol: pd.DataFrame,
    gross: float,
    date: pd.Timestamp,
) -> list[dict[str, float | str]]:
    aum_usd = 100_000_000.0
    impact_c = 0.5
    participation = compute_participation(weights, adv20_usd, aum_usd, gross).loc[date]
    vol = daily_vol.reindex(index=weights.index, columns=weights.columns).loc[date]
    delta_weight = weights.fillna(0.0).diff().abs().loc[date]
    delta_weight_gross = delta_weight * gross
    impact_bps = impact_c * vol * np.sqrt(participation.clip(lower=0.0)) * 10000.0
    cost_bps = impact_bps * delta_weight_gross
    active = pd.DataFrame(
        {
            "participation": participation,
            "daily_vol": vol,
            "delta_weight": delta_weight,
            "delta_weight_gross": delta_weight_gross,
            "impact_bps_i": impact_bps,
            "cost_bps_of_nav": cost_bps,
        }
    ).replace([np.inf, -np.inf], np.nan)
    summary = {
        "audit_date": str(date.date()),
        "ticker": "__TOTAL__",
        "participation": float(active["participation"].mean(skipna=True)),
        "daily_vol": float(active["daily_vol"].mean(skipna=True)),
        "delta_weight": float(active["delta_weight"].sum(skipna=True)),
        "delta_weight_gross": float(active["delta_weight_gross"].sum(skipna=True)),
        "impact_bps_i": float(active["impact_bps_i"].mean(skipna=True)),
        "cost_bps_of_nav": float(active["cost_bps_of_nav"].sum(skipna=True)),
        "annualized_cost_bps": float(active["cost_bps_of_nav"].sum(skipna=True) * TRADING_DAYS_PER_YEAR),
    }
    top = active.sort_values("cost_bps_of_nav", ascending=False).head(20).reset_index().rename(columns={"index": "ticker"})
    rows = [summary]
    for _, row in top.iterrows():
        rows.append(
            {
                "audit_date": str(date.date()),
                "ticker": str(row["ticker"]),
                "participation": float(row["participation"]),
                "daily_vol": float(row["daily_vol"]),
                "delta_weight": float(row["delta_weight"]),
                "delta_weight_gross": float(row["delta_weight_gross"]),
                "impact_bps_i": float(row["impact_bps_i"]),
                "cost_bps_of_nav": float(row["cost_bps_of_nav"]),
                "annualized_cost_bps": float(row["cost_bps_of_nav"] * TRADING_DAYS_PER_YEAR),
            }
        )
    return rows


def _turnover_summary_rows(turnover_frame: pd.DataFrame) -> pd.DataFrame:
    turnover = turnover_frame["production_gross_turnover"].dropna()
    rebalance = turnover_frame[turnover_frame["is_rebalance_day"]]["production_gross_turnover"].dropna()
    non_rebalance = turnover_frame[~turnover_frame["is_rebalance_day"]]["production_gross_turnover"].dropna()
    bins = [0.0, 0.05, 0.10, 0.25, 0.50, 1.00, np.inf]
    labels = ["0-5%", "5-10%", "10-25%", "25-50%", "50-100%", ">100%"]
    hist = pd.cut(turnover, bins=bins, labels=labels, include_lowest=True, right=True).value_counts().reindex(labels).fillna(0)
    rows: list[dict[str, float | int | str]] = [
        {"metric": "mean", "value": float(turnover.mean())},
        {"metric": "median", "value": float(turnover.median())},
        {"metric": "p75", "value": float(turnover.quantile(0.75))},
        {"metric": "p95", "value": float(turnover.quantile(0.95))},
        {"metric": "p99", "value": float(turnover.quantile(0.99))},
        {"metric": "max", "value": float(turnover.max())},
        {"metric": "rotation_days_gt_50pct", "value": int((turnover > 0.50).sum())},
        {"metric": "rotation_days_gt_100pct", "value": int((turnover > 1.00).sum())},
        {"metric": "rebalance_day_mean", "value": float(rebalance.mean())},
        {"metric": "non_rebalance_day_mean", "value": float(non_rebalance.mean())},
        {"metric": "non_rebalance_day_p95", "value": float(non_rebalance.quantile(0.95))},
    ]
    for label, count in hist.items():
        rows.append({"metric": f"hist_{label}", "value": int(count)})
    return pd.DataFrame(rows)


def _top_turnover_days(turnover_frame: pd.DataFrame, weights: pd.DataFrame, gross: float) -> pd.DataFrame:
    rows = []
    top = turnover_frame.sort_values("production_gross_turnover", ascending=False).head(10)
    for date, row in top.iterrows():
        delta = weights.fillna(0.0).diff().loc[date]
        abs_delta = delta.abs().sort_values(ascending=False)
        rows.append(
            {
                "date": str(pd.Timestamp(date).date()),
                "production_gross_turnover": float(row["production_gross_turnover"]),
                "turnover_1x": float(row["turnover_1x"]),
                "is_rebalance_day": bool(row["is_rebalance_day"]),
                "weekday": row["weekday"],
                "month": int(row["month"]),
                "calendar_context": _calendar_context(pd.Timestamp(date)),
                "top_delta_names": "; ".join(f"{ticker}:{value * gross:.2%}" for ticker, value in abs_delta.head(5).items()),
                "n_names_changed_gt_1pct_gross": int((abs_delta * gross > 0.01).sum()),
            }
        )
    return pd.DataFrame(rows)


def _is_weekly_rebalance_day(index: pd.Index) -> pd.Series:
    positions = pd.Series(np.arange(len(index)), index=index)
    return (positions % 5 == 0).rename("is_rebalance_day")


def _calendar_context(date: pd.Timestamp) -> str:
    labels = []
    if date.month in {1, 4, 7, 10} and 15 <= date.day <= 31:
        labels.append("earnings-season")
    if date.weekday() == 3:
        labels.append("Thursday")
    if date.day <= 5:
        labels.append("month-start")
    if date.day >= 25:
        labels.append("month-end")
    return ", ".join(labels) if labels else "ordinary-calendar-day"


def _participation_stats(participation: pd.DataFrame) -> dict[str, float]:
    daily_max = participation.max(axis=1, skipna=True).dropna()
    stacked = participation.stack().replace([np.inf, -np.inf], np.nan).dropna()
    return {
        "mean": float(stacked.mean()) if not stacked.empty else float("nan"),
        "p95": float(daily_max.quantile(0.95)) if not daily_max.empty else float("nan"),
        "p99": float(daily_max.quantile(0.99)) if not daily_max.empty else float("nan"),
        "max": float(daily_max.max()) if not daily_max.empty else float("nan"),
    }


def _naive_capacity_stats(weights: pd.DataFrame, adv20_usd: pd.DataFrame, gross: float, cap: float) -> dict[str, float]:
    denominator = weights.abs().mul(gross).replace(0.0, np.nan)
    ceiling = adv20_usd.mul(cap).div(denominator)
    daily_min = ceiling.min(axis=1, skipna=True).dropna()
    long_ceiling = adv20_usd.mul(cap).div(weights.where(weights > 0.0, np.nan).mul(gross)).min(axis=1, skipna=True).dropna()
    short_ceiling = adv20_usd.mul(cap).div((-weights.where(weights < 0.0, np.nan)).mul(gross)).min(axis=1, skipna=True).dropna()
    return {
        "p50": float(daily_min.quantile(0.50)) if not daily_min.empty else float("nan"),
        "p05": float(daily_min.quantile(0.05)) if not daily_min.empty else float("nan"),
        "worst": float(daily_min.min()) if not daily_min.empty else float("nan"),
        "long_worst": float(long_ceiling.min()) if not long_ceiling.empty else float("nan"),
        "short_worst": float(short_ceiling.min()) if not short_ceiling.empty else float("nan"),
    }


def _pct_days_above_cap(participation: pd.DataFrame, cap: float) -> float:
    daily_has_breach = participation.gt(cap).any(axis=1)
    return float(daily_has_breach.mean())


def _borrow_row(weights: pd.DataFrame, gross: float, borrow_tiers: pd.Series, aum_usd: float) -> dict[str, float | bool | int]:
    short_abs = (-weights.where(weights < 0.0, 0.0)).fillna(0.0)
    htb_mask = borrow_tiers.reindex(short_abs.columns).eq("htb").fillna(True)
    daily_short_total = short_abs.sum(axis=1).replace(0.0, np.nan)
    htb_share_daily = short_abs.loc[:, htb_mask.to_numpy()].sum(axis=1).div(daily_short_total)
    top10_daily = weights.apply(top_short_concentration, axis=1)
    htb_share = float(htb_share_daily.mean(skipna=True))
    top10 = float(top10_daily.mean(skipna=True))
    return {
        "n_short_names": int((short_abs > 0.0).sum(axis=1).replace(0, np.nan).mean(skipna=True)),
        "htb_share": htb_share,
        "top10_concentration": top10,
        "borrow_feasible": borrow_feasible_flag(htb_share, top10),
    }


def _capacity_ceiling(base: pd.DataFrame) -> float:
    passing = base[(base["sharpe_decay_pct_vs_paper"] <= 0.20) & (base["borrow_feasible"])]
    if passing.empty:
        return 0.0
    return float(passing["AUM_usd"].max())


def _impact_only_capacity_ceiling(base: pd.DataFrame) -> float:
    passing = base[base["sharpe_decay_pct_vs_paper"] <= 0.20]
    if passing.empty:
        return 0.0
    return float(passing["AUM_usd"].max())


def _recommended_range(capacity_ceiling: float) -> tuple[float, float]:
    if pd.isna(capacity_ceiling) or capacity_ceiling <= 0.0:
        return (float("nan"), float("nan"))
    return (min(5_000_000.0, capacity_ceiling), 0.75 * capacity_ceiling)


def _borrow_hard_ceiling(short_book: pd.DataFrame) -> float:
    infeasible = short_book[~short_book["borrow_feasible"]]
    if infeasible.empty:
        return float(short_book["AUM_usd"].max())
    if int(infeasible["AUM_usd"].min()) == int(short_book["AUM_usd"].min()):
        return 0.0
    return float(infeasible["AUM_usd"].min())


def _binding_constraint(curve: pd.DataFrame, short_book: pd.DataFrame) -> str:
    triggers = {
        "participation": _first_aum(curve[(curve["participation_cap"] == 0.05) & (curve["pct_days_above_participation_cap"] > 0.05)]),
        "impact": _first_aum(curve[(curve["participation_cap"] == 0.05) & (curve["impact_coefficient"] == 0.5) & (curve["sharpe_decay_pct_vs_paper"] > 0.20)]),
        "borrow": _first_aum(short_book[~short_book["borrow_feasible"]]),
    }
    valid = {key: value for key, value in triggers.items() if not pd.isna(value)}
    if not valid:
        return "none within tested AUM grid"
    first_aum = min(valid.values())
    first_constraints = [key for key, value in valid.items() if value == first_aum]
    return " / ".join(first_constraints)


def _constraint_text(curve: pd.DataFrame, short_book: pd.DataFrame) -> str:
    participation_trigger = _first_aum(curve[(curve["participation_cap"] == 0.05) & (curve["pct_days_above_participation_cap"] > 0.05)])
    impact_trigger = _first_aum(
        curve[(curve["participation_cap"] == 0.05) & (curve["impact_coefficient"] == 0.5) & (curve["sharpe_decay_pct_vs_paper"] > 0.20)]
    )
    borrow_trigger = _first_aum(short_book[~short_book["borrow_feasible"]])
    rows = pd.DataFrame(
        [
            {"constraint": "Participation > 5% on >5% of days", "trigger_AUM_usd": participation_trigger},
            {"constraint": "Net Sharpe decay > 20%", "trigger_AUM_usd": impact_trigger},
            {"constraint": "Borrow infeasible", "trigger_AUM_usd": borrow_trigger},
        ]
    )
    return _markdown_table(rows)


def _short_concentration_text(short_book: pd.DataFrame) -> str:
    row = short_book.iloc[0]
    return (
        f"Independent of AUM scaling, the short book exhibits structural concentration: "
        f"{float(row['top10_concentration']):.1%} of short notional sits in the top-10 short names, and "
        f"{float(row['htb_share']):.1%} sits in the HTB-proxy tier. This is a portfolio-construction issue, not merely a capacity issue. "
        "Even at sub-$10M AUM, the rule flags V3 as prime-broker dependent rather than broker-neutral."
    )


def _turnover_diagnostic_text(turnover_distribution: pd.DataFrame, turnover_top_days: pd.DataFrame) -> str:
    metric = turnover_distribution.set_index("metric")["value"]
    top_non_rebalance_share = 1.0 - float(turnover_top_days["is_rebalance_day"].mean()) if not turnover_top_days.empty else float("nan")
    return (
        f"Turnover is highly right-tailed: median production gross turnover is {float(metric['median']):.1%}, "
        f"but p95 is {float(metric['p95']):.1%}, p99 is {float(metric['p99']):.1%}, and "
        f"{int(metric['rotation_days_gt_100pct'])} days exceed 100% gross turnover. "
        f"Among the top-10 turnover days, {top_non_rebalance_share:.0%} are not weekly signal rebalance days, "
        "which points to the daily beta-neutralization / sector-cap re-solve as the likely source of final-weight rotation rather than the raw weekly ranking schedule alone. "
        f"Crucially, non-rebalance-day mean turnover ({float(metric['non_rebalance_day_mean']):.1%}) exceeds rebalance-day mean turnover "
        f"({float(metric['rebalance_day_mean']):.1%}) by about {float(metric['non_rebalance_day_mean']) / float(metric['rebalance_day_mean']):.1f}x. "
        "This inverts the expected ordering for a weekly-rebalanced strategy and isolates the source of turnover to the daily post-processing layer. "
        "The single-name top-delta footprints on rotation days are consistent with the neutralization optimizer wholesale-flipping individual positions when beta/sector drift crosses a constraint boundary."
    )


def _sensitivity_table(curve: pd.DataFrame) -> pd.DataFrame:
    rows = []
    subset = curve[curve["participation_cap"] == 0.05]
    for impact_c, frame in subset.groupby("impact_coefficient"):
        rows.append(
            {
                "impact_coefficient": impact_c,
                "impact_only_capacity_ceiling_usd": _impact_only_capacity_ceiling(frame),
                "borrow_adjusted_capacity_ceiling_usd": _capacity_ceiling(frame),
            }
        )
    return pd.DataFrame(rows)


def _first_aum(frame: pd.DataFrame) -> float:
    if frame.empty:
        return float("nan")
    return float(frame["AUM_usd"].min())


def _fmt_usd(value: float) -> str:
    if pd.isna(value):
        return "not reached"
    if value == 0.0:
        return f"<${min(AUM_LEVELS) / 1_000_000:.0f}M"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    return f"${value / 1_000_000:.0f}M"


if __name__ == "__main__":
    main()
