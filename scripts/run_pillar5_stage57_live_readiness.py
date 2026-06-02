"""Build Pillar 5 Stage 5.7 live-readiness checklist."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import _markdown_table  # noqa: E402


CHECKLIST_PATH = PROJECT_ROOT / "results/pillar5_stage57_checklist_status.csv"
SUMMARY_PATH = PROJECT_ROOT / "reports/pillar5_stage57_live_readiness_checklist.md"


def main() -> None:
    checklist = build_checklist()
    CHECKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    checklist.to_csv(CHECKLIST_PATH, index=False)
    SUMMARY_PATH.write_text(build_report(checklist), encoding="utf-8")
    print(checklist.to_string(index=False))
    print(f"Saved {CHECKLIST_PATH.as_posix()}")
    print(f"Saved {SUMMARY_PATH.as_posix()}")


def build_checklist() -> pd.DataFrame:
    rows = [
        _row(
            "Pre-trade controls",
            "PT-001",
            "Production gross leverage fixed at 1.405x for 10% target vol",
            "5.1 selected 10% vol target, k=0.7025, production gross=1.405x.",
            "pass",
            "Risk / PM",
            "N",
            "Keep static gross cap at 1.405x until V4 dynamic sizing is approved.",
            "Hard gross cap in order generation and daily risk report.",
        ),
        _row(
            "Pre-trade controls",
            "PT-002",
            "Dynamic volatility overlay evaluation",
            "5.1 showed static 10% target can realize ~26% 60d vol in high-vol regimes.",
            "partial",
            "V4 strategy work",
            "N",
            "Evaluate dynamic vol targeting, but do not use a blunt high-vol off switch because 5.6 found high-vol Sharpe is strong.",
            "Backtest dynamic vol overlay without reducing SPY 20d vol top-quartile Sharpe below current baseline.",
        ),
        _row(
            "Pre-trade controls",
            "PT-003",
            "Turnover cap / no-trade band in neutralization optimizer",
            "5.4 capacity ceiling <$5M is driven by tail rotation days; non-rebalance turnover 27.4% vs rebalance 7.0%.",
            "fail",
            "V4 strategy work",
            "Y",
            "Add turnover penalty or no-trade band to daily beta-neutralization / sector-cap solve.",
            "Non-rebalance-day mean turnover < 2x rebalance-day mean turnover; >100% turnover days reduced by at least 75%.",
        ),
        _row(
            "Pre-trade controls",
            "PT-004",
            "Participation cap by name and day",
            "5.4 p95 participation breaches quickly; mid-cap names such as APH/MOS/PTC/OKE bind capacity.",
            "fail",
            "Ops infra work",
            "Y",
            "Enforce projected participation limit before orders are released.",
            "No order plan exceeds 5% ADV participation without explicit PM/risk approval.",
        ),
        _row(
            "Pre-trade controls",
            "PT-005",
            "Sector net constraint after beta-neutral solve",
            "5.5 found post-V3 max abs sector net 14.1% vs raw 7.5%; beta-neutralization widened sector net exposure.",
            "fail",
            "V4 strategy work",
            "Y",
            "Constrain sector net exposure inside the beta-neutral optimizer, not only as a side cap.",
            "Post-solve average max abs sector net <= raw baseline and p95 max abs sector net <= 15%.",
        ),
        _row(
            "Risk monitoring",
            "RM-001",
            "Residual beta 60d monitoring",
            "5.5 residual alpha beta=0.269; 5.6 found 2022 rate shock had |beta|>0.4 on 56.6% of days.",
            "partial",
            "Ops infra work",
            "Y",
            "Compute rolling 60d realized beta daily and alert on drift.",
            "Warn at |beta_60d| > 0.25; hard review at |beta_60d| > 0.40 for 5 consecutive days.",
        ),
        _row(
            "Risk monitoring",
            "RM-002",
            "Residual beta 20d fast-event monitoring",
            "5.6 COVID crash shows zero high-beta days under 60d threshold, likely because 60d beta smooths fast events.",
            "fail",
            "Ops infra work",
            "Y",
            "Add 20d realized beta monitor alongside 60d to catch fast dislocations.",
            "Warn at |beta_20d| > 0.30; hard review at |beta_20d| > 0.50 for 3 consecutive days.",
        ),
        _row(
            "Risk monitoring",
            "RM-003",
            "Trend-based regime sizing monitor",
            "5.6 refuted high-vol weakness; weak regime is SPY 60d return bottom quartile, Sharpe=-0.074 over 677 days.",
            "fail",
            "V4 strategy work",
            "Y",
            "Compute daily SPY 60d trailing return percentile vs trailing 3y distribution and reduce sizing in bottom quartile.",
            "When SPY 60d trend percentile is bottom quartile, V4 regime-conditioned Sharpe >= 0 and drawdown improves vs V3.",
        ),
        _row(
            "Risk monitoring",
            "RM-004",
            "Do not use blunt high-vol kill filter",
            "5.6 found SPY 20d vol top-quartile Sharpe=1.624 vs bottom-quartile Sharpe=0.500.",
            "pass",
            "Risk / PM",
            "N",
            "High vol alone is not a de-risk trigger; use trend and realized risk jointly.",
            "Risk policy states vol-only filter is informational, not automatic sizing reduction.",
        ),
        _row(
            "Risk monitoring",
            "RM-005",
            "Factor tape for size/value/momentum attribution",
            "5.5 could not prove residual alpha is not hidden size/value/momentum exposure because canonical factor returns are unavailable.",
            "partial",
            "Ops infra work",
            "N",
            "Source or build approved factor-return tape for institutional attribution.",
            "Daily size/value/momentum factor returns available and reconciled to attribution engine.",
        ),
        _row(
            "Risk monitoring",
            "RM-006",
            "VaR / expected shortfall budget",
            "Pillar 5 covered DD and stress windows but did not implement formal VaR/ES limits.",
            "fail",
            "Ops infra work",
            "Y",
            "Add rolling historical VaR/ES risk budget before live launch.",
            "Daily 95/99% VaR and ES produced, with breach escalation and PM signoff.",
        ),
        _row(
            "Borrow / financing",
            "BF-001",
            "Short top-10 concentration limit",
            "5.4 found top-10 short concentration=48.7%, structurally independent of AUM.",
            "fail",
            "V4 strategy work",
            "Y",
            "Add explicit short-side concentration constraint.",
            "Top-10 short concentration <= 25%; no single short > 5% of short book absent approval.",
        ),
        _row(
            "Borrow / financing",
            "BF-002",
            "HTB exposure cap",
            "5.4 HTB-proxy share=25.5%, near the 30% borrow-feasible threshold.",
            "partial",
            "Ops infra work",
            "Y",
            "Replace market-cap/ADV proxy with PB borrow feed and enforce HTB cap.",
            "HTB notional < 25% of short book using PB locate/utilization data.",
        ),
        _row(
            "Borrow / financing",
            "BF-003",
            "Borrow cost stress monitor",
            "5.3 break-even borrow cost is ~700 bps, robust but analytic and not PB-confirmed.",
            "partial",
            "Ops infra work",
            "N",
            "Track realized borrow fees and rerun borrow stress weekly.",
            "Daily borrow fee file available; projected fee drag included in pre-trade P&L.",
        ),
        _row(
            "Operational",
            "OP-001",
            "Soft halt at -10% rolling 60d drawdown",
            "5.6 worst requested window return=-9.1%; institutional review should occur before -20% kill switch.",
            "fail",
            "Ops infra work",
            "Y",
            "Add soft halt requiring PM/risk review at -10% rolling 60d drawdown.",
            "Automated alert and documented review before next rebalance after breach.",
        ),
        _row(
            "Operational",
            "OP-002",
            "Hard halt at -15% rolling 60d drawdown",
            "5.2 hard stop was -12% de-risk and kill switch -20%; 5.7 adds institutional hard halt tier.",
            "partial",
            "Risk / PM",
            "Y",
            "Define hard halt action: freeze new risk or cut gross by at least 50%.",
            "Policy implemented and historically simulated before paper trading.",
        ),
        _row(
            "Operational",
            "OP-003",
            "Single-day loss halt at -8%",
            "Single-day operational loss limit was not defined in 5.1-5.6.",
            "fail",
            "Ops infra work",
            "Y",
            "Add -8% single-day loss halt with immediate order freeze and risk review.",
            "Intraday/close-to-close loss monitor triggers order block and incident ticket.",
        ),
        _row(
            "Operational",
            "OP-004",
            "Existing -20% kill switch retained as capital-preservation backstop",
            "5.2 and 5.6 found no tested window breaches -20%; still useful as terminal kill switch.",
            "pass",
            "Risk / PM",
            "N",
            "Keep -20% kill switch but do not rely on it as first review point.",
            "Policy includes -10%, -15%, and -20% tiers with explicit actions.",
        ),
        _row(
            "Operational",
            "OP-005",
            "Slippage and impact monitoring",
            "5.4 shows impact is capacity-binding because of tail rotation days.",
            "fail",
            "Ops infra work",
            "Y",
            "Compare realized execution cost to modeled square-root impact daily.",
            "Daily slippage report by name, order, sector, and rotation-day tag.",
        ),
        _row(
            "Operational",
            "OP-006",
            "Canonical V3 source-of-truth reconciliation",
            "5.5 found reconstructed Stage 4.5 V3 does not exactly match locked Pillar 5 cache.",
            "fail",
            "V4 strategy work",
            "Y",
            "Decide and document canonical production book path; deprecate the other path.",
            "One reproducible command regenerates locked V3 weights bit-for-bit or documents intentional versioning.",
        ),
        _row(
            "Data integrity",
            "DI-001",
            "Point-in-time prices and returns checks",
            "Pillar 5 uses existing processed prices; live launch needs automated PIT validation.",
            "partial",
            "Ops infra work",
            "Y",
            "Add PIT validation checks for prices, returns, and corporate-action adjustments.",
            "Daily data audit passes before signal generation.",
        ),
        _row(
            "Data integrity",
            "DI-002",
            "Survivorship and universe audit",
            "Pillar 4/5 universe construction uses available processed data; launch needs explicit survivorship audit.",
            "partial",
            "Ops infra work",
            "N",
            "Document universe membership and delisting treatment.",
            "Universe audit report generated for backtest and paper-trading periods.",
        ),
        _row(
            "Data integrity",
            "DI-003",
            "ADV20 real-time refresh",
            "5.4 capacity relies on ADV20; live capacity should re-evaluate ADV around earnings/events.",
            "fail",
            "Ops infra work",
            "Y",
            "Refresh ADV20 daily and block stale liquidity estimates.",
            "No order generated if ADV20 missing/stale; event-day liquidity override documented.",
        ),
    ]
    return pd.DataFrame(rows)


def build_report(checklist: pd.DataFrame) -> str:
    blocking_count = int((checklist["blocking_for_launch"] == "Y").sum())
    fail_blocking = int(((checklist["blocking_for_launch"] == "Y") & (checklist["status"].str.contains("fail"))).sum())
    partial_blocking = int(((checklist["blocking_for_launch"] == "Y") & (checklist["status"].str.contains("partial"))).sum())
    lines = [
        "# Pillar 5 Stage 5.7 - Live-Readiness Operational Checklist",
        "",
        "## Plan",
        "",
        "1. Synthesize locked Pillar 5 findings from Stages 5.1 through 5.6 without running new backtests.",
        "2. Convert each finding into an institutional pre-launch checklist item with status, owner, and launch-blocking flag.",
        "3. Carry forward Stage 5.4 capacity/turnover/borrow findings as pre-trade and financing controls.",
        "4. Carry forward Stage 5.5 sector-net widening and residual-beta findings as risk-monitoring controls.",
        "5. Carry forward Stage 5.6 regime results: trend-down weakness, 2022 rate-shock residual-beta paradox, and 20d/60d beta monitoring requirements.",
        "6. Add multi-tier drawdown halt controls: -10% soft halt, -15%/-20% hard halt, and -8% single-day loss.",
        "7. Add a separate warning section for findings that complicate the V4 fix path, outside the pass/fail checklist grid.",
        "",
        "## Executive Summary",
        f"- Launch readiness: **NO-GO for live capital** until blocking fails are resolved. There are {blocking_count} launch-blocking items: {fail_blocking} fail and {partial_blocking} partial.",
        "- The biggest V4 blockers are turnover-aware neutralization, sector-net constraints, short concentration, participation caps, residual beta monitoring, and canonical source-of-truth reconciliation.",
        "- Stage 5.6 changes the regime-control design: V3 is weak in negative 60d market trend, not high vol. V4 should use trend-conditioned sizing, not a blunt vol filter.",
        "",
        "## Status Legend",
        "- pass = current V3 / current process is acceptable for this control.",
        "- partial = concept exists or evidence is favorable, but live-ready implementation is incomplete.",
        "- fail = missing or materially insufficient for launch.",
        "- N/A = not applicable.",
        "",
        "## Go / No-Go",
        _go_no_go_table(checklist),
        "",
        "## Findings That Complicate The V4 Fix Path",
        _warning_section(),
        "",
        "## Checklist By Category",
        *_category_sections(checklist),
        "",
        "## Output",
        f"- Machine-readable checklist: `results/{CHECKLIST_PATH.name}`.",
        "",
        "## 5.8 Handoff Note",
        "Do not start Stage 5.8 until this checklist, especially the warning section above, has been reviewed. The V4 spec must trace every launch-blocking item and every warning to an explicit requirement.",
        "",
    ]
    return "\n".join(lines)


def _row(
    category: str,
    item_id: str,
    control: str,
    pillar5_evidence: str,
    status_key: str,
    owner: str,
    blocking: str,
    current_v3_status: str,
    v4_requirement: str,
) -> dict[str, str]:
    status_map = {
        "pass": "pass",
        "partial": "partial",
        "fail": "fail",
        "na": "N/A",
    }
    return {
        "category": category,
        "item_id": item_id,
        "control": control,
        "pillar5_evidence": pillar5_evidence,
        "status": status_map[status_key],
        "owner": owner,
        "blocking_for_launch": blocking,
        "current_v3_status": current_v3_status,
        "v4_requirement": v4_requirement,
    }


def _go_no_go_table(checklist: pd.DataFrame) -> str:
    grouped = checklist.groupby(["status", "blocking_for_launch"], as_index=False).size()
    return _markdown_table(grouped)


def _warning_section() -> str:
    warnings = pd.DataFrame(
        [
            {
                "warning": "Sector net widening (5.5)",
                "why_it_matters": "Beta neutralization reduced ex-ante beta but widened sector net exposure from 7.5% raw to 14.1% post-V3.",
                "V4_watch_out": "Do not optimize beta in isolation; add sector net constraints inside the neutralization objective.",
            },
            {
                "warning": "2022 rate-shock paradox (5.6)",
                "why_it_matters": "Residual beta drifted on 56.6% of days, yet V3 returned +11.9% with Sharpe 1.14.",
                "V4_watch_out": "A cleaner neutralization layer may remove P&L-positive exposure; require counterfactual replay before approving the fix.",
            },
            {
                "warning": "Capacity-driven AUM ceiling (5.4)",
                "why_it_matters": "Capacity is <$5M under current live-readiness rules due to tail turnover and borrow concentration.",
                "V4_watch_out": "Do not evaluate V4 at institutional AUM until turnover, participation, and short-book constraints are solved.",
            },
            {
                "warning": "Fast-event beta measurement blind spot (5.6)",
                "why_it_matters": "COVID crash shows 0 high residual-beta days under 60d beta, likely because the window is too slow.",
                "V4_watch_out": "Use 20d and 60d beta monitors together; do not treat 60d-only calm as proof of risk control.",
            },
        ]
    )
    return _markdown_table(warnings)


def _category_sections(checklist: pd.DataFrame) -> list[str]:
    sections: list[str] = []
    for category, frame in checklist.groupby("category", sort=False):
        columns = [
            "item_id",
            "control",
            "status",
            "owner",
            "blocking_for_launch",
            "pillar5_evidence",
            "current_v3_status",
            "v4_requirement",
        ]
        sections.extend([f"### {category}", _markdown_table(frame[columns]), ""])
    return sections


if __name__ == "__main__":
    main()

