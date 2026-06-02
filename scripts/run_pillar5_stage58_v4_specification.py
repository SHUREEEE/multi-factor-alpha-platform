"""Build Pillar 5 Stage 5.8 V4 specification and requirements."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import load_or_build_baseline_artifacts, _markdown_table  # noqa: E402
from scripts.run_pillar4_stage42 import _load_panel, _project_path  # noqa: E402
from scripts.run_pillar4_stage45_neutralization import CONFIG_PATH  # noqa: E402
from scripts.run_pillar5_stage55_risk_decomposition import reconstruct_stage45_weights  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import compute_rolling_betas, portfolio_ex_ante_beta  # noqa: E402
from src.research.ic_analysis import extract_daily_return_matrix  # noqa: E402


RECON_DAILY_PATH = PROJECT_ROOT / "results/pillar5_stage58_v3_reconciliation.csv"
RECON_SUMMARY_PATH = PROJECT_ROOT / "results/pillar5_stage58_v3_reconciliation_summary.csv"
REQ_PATH = PROJECT_ROOT / "results/pillar5_stage58_v4_requirements.csv"
SPEC_PATH = PROJECT_ROOT / "reports/pillar5_stage58_v4_specification.md"
CHECKLIST_PATH = PROJECT_ROOT / "results/pillar5_stage57_checklist_status.csv"


def main() -> None:
    reconciliation, recon_summary = build_v3_reconciliation()
    verdict = classify_reconciliation(recon_summary.iloc[0])
    requirements = build_requirements()
    RECON_DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    reconciliation.to_csv(RECON_DAILY_PATH, index=False)
    recon_summary.assign(verdict=verdict["verdict"], canonical_path=verdict["canonical_path"]).to_csv(RECON_SUMMARY_PATH, index=False)
    requirements.to_csv(REQ_PATH, index=False)
    SPEC_PATH.write_text(build_spec(verdict, recon_summary.iloc[0], requirements), encoding="utf-8")
    print(recon_summary.assign(verdict=verdict["verdict"]).to_string(index=False))
    print(requirements[["req_id", "category", "source_item_id", "priority"]].to_string(index=False))
    print(f"Saved {RECON_DAILY_PATH.as_posix()}")
    print(f"Saved {RECON_SUMMARY_PATH.as_posix()}")
    print(f"Saved {REQ_PATH.as_posix()}")
    print(f"Saved {SPEC_PATH.as_posix()}")


def build_v3_reconciliation() -> tuple[pd.DataFrame, pd.DataFrame]:
    artifacts = load_or_build_baseline_artifacts()
    reconstructed = reconstruct_stage45_weights()["post_v3"].sort_index()
    cached = artifacts.weights.sort_index()
    common_index = reconstructed.index.intersection(cached.index)
    common_columns = reconstructed.columns.intersection(cached.columns)
    recon = reconstructed.reindex(index=common_index, columns=common_columns).astype(float)
    cache = cached.reindex(index=common_index, columns=common_columns).astype(float)
    config = load_pillar4_config(CONFIG_PATH)
    prices = _load_panel(_project_path(config.price_file), "prices")
    returns = extract_daily_return_matrix(prices).reindex(index=common_index, columns=common_columns)
    market = artifacts.market_proxy.reindex(common_index)
    betas = compute_rolling_betas(prices, artifacts.market_proxy, lookback=60).reindex(index=common_index, columns=common_columns)
    recon_return = recon.mul(returns, axis=0).sum(axis=1, min_count=1)
    cache_return = cache.mul(returns, axis=0).sum(axis=1, min_count=1)
    recon_beta = portfolio_ex_ante_beta(recon, betas)
    cache_beta = portfolio_ex_ante_beta(cache, betas)
    diff = pd.DataFrame(
        {
            "date": common_index,
            "weight_l1": (recon - cache).abs().sum(axis=1).to_numpy(),
            "gross_diff": (recon.abs().sum(axis=1) - cache.abs().sum(axis=1)).abs().to_numpy(),
            "return_diff_bps": ((recon_return - cache_return).abs() * 10000.0).to_numpy(),
            "beta_diff": (recon_beta - cache_beta).abs().to_numpy(),
        }
    )
    summary = pd.DataFrame(
        [
            {
                "common_dates": int(len(common_index)),
                "common_symbols": int(len(common_columns)),
                "recon_only_dates": int(len(reconstructed.index.difference(cached.index))),
                "cache_only_dates": int(len(cached.index.difference(reconstructed.index))),
                "recon_only_symbols": int(len(reconstructed.columns.difference(cached.columns))),
                "cache_only_symbols": int(len(cached.columns.difference(reconstructed.columns))),
                "mean_weight_l1": float(diff["weight_l1"].mean(skipna=True)),
                "p50_weight_l1": float(diff["weight_l1"].quantile(0.50)),
                "p95_weight_l1": float(diff["weight_l1"].quantile(0.95)),
                "max_weight_l1": float(diff["weight_l1"].max(skipna=True)),
                "mean_gross_diff": float(diff["gross_diff"].mean(skipna=True)),
                "max_gross_diff": float(diff["gross_diff"].max(skipna=True)),
                "mean_return_diff_bps": float(diff["return_diff_bps"].mean(skipna=True)),
                "p50_return_diff_bps": float(diff["return_diff_bps"].quantile(0.50)),
                "p95_return_diff_bps": float(diff["return_diff_bps"].quantile(0.95)),
                "max_return_diff_bps": float(diff["return_diff_bps"].max(skipna=True)),
                "mean_beta_diff": float(diff["beta_diff"].mean(skipna=True)),
                "max_beta_diff": float(diff["beta_diff"].max(skipna=True)),
            }
        ]
    )
    return diff, summary


def classify_reconciliation(summary: pd.Series) -> dict[str, str]:
    mean_l1 = float(summary["mean_weight_l1"])
    p95_ret = float(summary["p95_return_diff_bps"])
    max_ret = float(summary["max_return_diff_bps"])
    if mean_l1 < 0.01 and p95_ret < 1.0 and max_ret < 5.0:
        return {
            "verdict": "A - TRIVIAL DIFF",
            "launch_posture": "V4 cleared to begin implementation pending Pre-V4 Prerequisites in Section 2.",
            "canonical_path": "results/pillar5_artifacts/v3_weights.parquet",
            "deprecation_notice": "Stage 4.5 reconstruction is deprecated for Pillar 5/V4 handoff; cache is canonical.",
            "blocked": "N",
        }
    if mean_l1 > 0.05 or p95_ret > 10.0 or max_ret > 50.0:
        return {
            "verdict": "C - BLOCKING DIFF",
            "launch_posture": "V4 implementation BLOCKED pending V3 reconciliation resolution; see Section 2.",
            "canonical_path": "unresolved; temporary analysis source remains results/pillar5_artifacts/v3_weights.parquet",
            "deprecation_notice": "No path may be deprecated until reconstruction/cache mismatch is resolved.",
            "blocked": "Y",
        }
    return {
        "verdict": "B - MATERIAL BUT BOUNDED DIFF",
        "launch_posture": "V4 cleared to begin implementation pending Pre-V4 Prerequisites in Section 2.",
        "canonical_path": "results/pillar5_artifacts/v3_weights.parquet",
        "deprecation_notice": "Stage 4.5 reconstruction requires investigation but does not block V4; cache is canonical because Pillar 5 was built on it.",
        "blocked": "N",
    }


def build_requirements() -> pd.DataFrame:
    rows = [
        _req(
            "REQ-F-001",
            "Functional",
            "Turnover-aware neutralization",
            "V4 neutralization must include turnover-aware behavior, such as a no-trade band or turnover penalty, while preserving the daily risk-control objective.",
            "n_days with daily gross turnover > 100% reduced by >=75%; p95 non-rebalance-day turnover < 1.5x p95 rebalance-day turnover; full-sample Sharpe >= 0.9x V3 baseline.",
            "Must not reduce 2022 rate-shock Sharpe below 1.0; must not widen post-solve sector net exposure above V3; must not claim capacity improvement without rerunning 5.4-style capacity.",
            "5.4, 5.5, 5.6, 5.7",
            "PT-003",
            "P0",
            "REQ-F-002, REQ-F-004, REQ-N-004",
        ),
        _req(
            "REQ-F-002",
            "Functional",
            "Sector-net constraint inside optimizer",
            "V4 optimizer must constrain sector net exposure inside the beta-neutral solve rather than relying only on side caps.",
            "Post-solve average max abs sector net <= raw baseline; p95 max abs sector net <=15%; sector exposure covariance share is not negative by more than V3 baseline.",
            "Must not use sector tilts to satisfy beta neutrality; must not lower high-vol regime Sharpe below 0.9x V3 high-vol Sharpe.",
            "5.5, 5.7",
            "PT-005",
            "P0",
            "REQ-F-001",
        ),
        _req(
            "REQ-F-003",
            "Functional",
            "Trend-based regime sizing",
            "V4 must compute SPY 60d trailing-return percentile versus trailing 3y distribution and use trend-down state for sizing decisions.",
            "Bottom-quartile SPY-60d-return regime Sharpe >=0; max DD in that regime improves vs V3; high-vol top-quartile Sharpe >=0.9x V3 high-vol Sharpe.",
            "Must not implement a blunt vol-off filter; must not cut risk simply because SPY 20d volatility is high.",
            "5.6, 5.7",
            "RM-003",
            "P0",
            "",
        ),
        _req(
            "REQ-F-004",
            "Functional",
            "Residual beta 20d monitoring",
            "V4 must monitor rolling 20d realized beta daily to catch fast dislocations missed by 60d beta.",
            "Warn at |beta_20d| >0.30; hard review at |beta_20d| >0.50 for 3 consecutive days; COVID-like fast windows are visible in monitoring output.",
            "Must not rely on 60d beta alone; must not label COVID-style windows effective solely because 60d beta stays below threshold.",
            "5.6, 5.7",
            "RM-002",
            "P0",
            "REQ-F-005",
        ),
        _req(
            "REQ-F-005",
            "Functional",
            "Residual beta 60d monitoring",
            "V4 must monitor rolling 60d realized beta daily for persistent drift.",
            "Warn at |beta_60d| >0.25; hard review at |beta_60d| >0.40 for 5 consecutive days; 2022 rate-shock drift is flagged historically.",
            "Must not force zero realized beta at the cost of collapsing 2022 rate-shock Sharpe below 1.0.",
            "5.5, 5.6, 5.7",
            "RM-001",
            "P0",
            "REQ-F-004",
        ),
        _req(
            "REQ-F-006",
            "Functional",
            "Short top-10 concentration limit",
            "V4 must limit concentration in the short book.",
            "Top-10 short concentration <=25% at launch; stretch goal <=20%; no single short >5% of short book without approval.",
            "Must not improve concentration by replacing easy-borrow names with HTB names; must not reduce short diversification during stress windows.",
            "5.4, 5.7",
            "BF-001",
            "P0",
            "REQ-F-007",
        ),
        _req(
            "REQ-F-007",
            "Functional",
            "HTB cap with PB feed",
            "V4 must replace market-cap/ADV borrow proxy with PB locate/utilization data and enforce HTB cap.",
            "HTB notional <25% of short book using PB feed; unavailable borrow data blocks order generation for affected names.",
            "Must not treat ADV or market cap as sufficient proof of borrow availability after PB feed exists.",
            "5.4, 5.7",
            "BF-002",
            "P0",
            "",
        ),
        _req(
            "REQ-F-008",
            "Functional",
            "Multi-tier drawdown halt",
            "V4 live-readiness policy must implement multi-tier drawdown controls.",
            "-10% rolling 60d DD soft halt; -15% rolling 60d DD hard halt; -8% single-day loss halt; -20% terminal kill switch retained.",
            "Must not rely on -20% as the first review trigger; must not continue ordinary rebalancing after a soft/hard halt without documented review.",
            "5.2, 5.6, 5.7",
            "OP-001;OP-002;OP-003",
            "P0",
            "",
        ),
        _req(
            "REQ-F-009",
            "Functional",
            "Participation cap",
            "V4 pre-trade checks must cap projected participation by name/day.",
            "No order plan exceeds 5% ADV without explicit approval; report p50/p95/max participation as in 5.4.",
            "Must not report capacity using mean participation only; must not scale AUM without multiplying by gross exposure.",
            "5.4, 5.7",
            "PT-004",
            "P0",
            "REQ-F-012, REQ-F-013",
        ),
        _req(
            "REQ-F-010",
            "Functional",
            "VaR / expected shortfall budget",
            "V4 must add rolling historical VaR and expected shortfall limits.",
            "Daily 95/99% VaR and ES produced; breach escalation is documented; VaR/ES report reconciles to realized P&L.",
            "Must not use VaR/ES as a substitute for drawdown halts or residual beta monitoring.",
            "5.7",
            "RM-006",
            "P0",
            "REQ-F-008",
        ),
        _req(
            "REQ-F-011",
            "Functional",
            "Slippage and impact monitoring",
            "V4 must compare realized execution cost to modeled square-root impact daily.",
            "Daily slippage report by name, order, sector, and rotation-day tag; tail rotation-day impact separately reported.",
            "Must not apply impact to gross exposure instead of turnover; must not ignore high-turnover non-rebalance days.",
            "5.4, 5.7",
            "OP-005",
            "P0",
            "REQ-F-001",
        ),
        _req(
            "REQ-F-012",
            "Functional",
            "ADV20 freshness",
            "V4 must refresh ADV20 daily and block stale liquidity estimates.",
            "No order generated if ADV20 is missing/stale; event-day liquidity override is documented.",
            "Must not rely on stationary ADV around earnings or index events.",
            "5.4, 5.7",
            "DI-003",
            "P0",
            "",
        ),
        _req(
            "REQ-F-013",
            "Functional",
            "Point-in-time validation",
            "V4 must run point-in-time checks before signal generation.",
            "Daily data audit passes for prices, returns, and corporate actions before weights are generated.",
            "Must not allow cache/reconstruction mismatches to pass silently; must not use future-adjusted fields in signal construction.",
            "5.7, 5.8",
            "DI-001",
            "P0",
            "REQ-N-001, REQ-N-004",
        ),
        _req(
            "REQ-F-014",
            "Functional",
            "Canonical source-of-truth reconciliation",
            "V4 must define exactly one canonical production book path before implementation.",
            "One documented command regenerates the canonical V4 weights bit-for-bit; cache and reconstruction agree by construction.",
            "Must not repeat the Stage 5.5 cache-vs-reconstruction ambiguity; must not start V4 if Stage 5.8 reconciliation is Verdict C without explicit resolution.",
            "5.5, 5.7, 5.8",
            "OP-006",
            "P0",
            "REQ-N-001, REQ-N-004",
        ),
        _req(
            "REQ-F-015",
            "Functional",
            "PIT data integrity launch gate",
            "V4 launch workflow must block if daily PIT data checks fail.",
            "Daily data audit passes before signal generation; failed audit blocks order files and opens an incident ticket.",
            "Must not treat manual spot checks as sufficient for live launch.",
            "5.7",
            "DI-001",
            "P0",
            "REQ-F-013",
        ),
    ]
    rows.extend(
        [
            _req(
                "REQ-N-001",
                "Non-functional",
                "Reproducibility",
                "One documented command regenerates V4 weights bit-for-bit.",
                "Command, inputs, and output hashes are documented for every V4 run.",
                "Must not depend on hidden notebooks or mutable intermediate files.",
                "5.5, 5.7",
                "OP-006",
                "P0",
                "",
            ),
            _req(
                "REQ-N-002",
                "Non-functional",
                "Testability",
                "Each REQ-F must have at least one automated test in tests/.",
                "Automated test coverage maps every REQ-F id to at least one test or explicit non-automatable exception.",
                "Must not accept manual-only verification for launch-blocking controls.",
                "5.7",
                "ALL_BLOCKING",
                "P0",
                "",
            ),
            _req(
                "REQ-N-003",
                "Non-functional",
                "Documentation parity",
                "V4 must produce attribution, capacity, and stress reports analogous to Pillar 5 Stages 5.4-5.6.",
                "V4 report set includes capacity, risk decomposition, stress/regime, and live-readiness checklist.",
                "Must not claim V4 readiness from Sharpe-only backtests.",
                "5.4, 5.5, 5.6, 5.7",
                "ALL_BLOCKING",
                "P0",
                "REQ-N-002",
            ),
            _req(
                "REQ-N-004",
                "Non-functional",
                "Source-of-truth discipline",
                "V4 weights cache and reconstruction script must agree by construction.",
                "Daily reconciliation has mean weight L1 <0.01, p95 return diff <1bp, max return diff <5bp.",
                "Must not allow an unresolved Verdict C-style mismatch into V4 implementation.",
                "5.5, 5.8",
                "OP-006",
                "P0",
                "REQ-N-001",
            ),
        ]
    )
    return pd.DataFrame(rows)


def build_spec(verdict: dict[str, str], summary: pd.Series, requirements: pd.DataFrame) -> str:
    headline = (
        f"{verdict['verdict']}; mean L1={float(summary['mean_weight_l1']):.4f}, "
        f"p95 return diff={float(summary['p95_return_diff_bps']):.2f} bps, max return diff={float(summary['max_return_diff_bps']):.2f} bps."
    )
    functional = requirements[requirements["category"] == "Functional"]
    nonfunctional = requirements[requirements["category"] == "Non-functional"]
    lines = [
        "# Pillar 5 Stage 5.8 - V4 Specification",
        "",
        "## Section 0 - Launch Posture",
        verdict["launch_posture"],
        f"Part A verdict: {headline}",
        "",
        "## Section 1 - V3 Recap & V4 Mandate",
        "V3 production sizing is 10% target vol with 1.405x gross, Sharpe about 0.498 at 10 bps, max drawdown -17.3%, and no tested Stage 5.6 stress window breached the -20% kill switch. It is still **NO-GO for live capital** because Stage 5.4 capacity is <$5M, driven by tail rotation days and short-book concentration, and Stage 5.7 has 16 launch-blocking checklist items.",
        "",
        "V4 is **not** a Sharpe-maximization project. V4 must resolve launch-blocking live-readiness items while preserving V3's useful regime behavior, especially high-volatility regime Sharpe of 1.62 and 2022 rate-shock window Sharpe of 1.14. The design goal is institutional viability: capacity, turnover, borrow, data integrity, and risk controls must improve without silently removing the exposures that made V3 resilient in some stress regimes.",
        "",
        "## Section 2 - Pre-V4 Prerequisites",
        _reconciliation_text(verdict, summary),
        "",
        "Factor-tape decision: no canonical size/value/momentum factor-return tape exists in the repository. V4 attribution may proceed with market + sector + residual decomposition if no factor tape is sourced, but it inherits the limitation that residual alpha cannot be proven free of hidden factor exposure.",
        "",
        "## Section 3 - V4 Functional Requirements (REQ-F-xxx)",
        *_requirement_sections(functional),
        "## Section 4 - V4 Non-Functional Requirements (REQ-N-xxx)",
        *_requirement_sections(nonfunctional),
        "## Section 5 - V4 Acceptance Gate",
        "- All P0 REQ-F meet acceptance criteria.",
        "- No REQ-F violates any anti-criterion.",
        "- V4 full-sample Sharpe >= 0.9 x V3 baseline.",
        "- V4 capacity ceiling >= $25M under the same live-readiness rules used in Stage 5.4.",
        "- Stage 5.7 checklist is re-evaluated end-to-end: all launch-blocking items pass or are partial with explicit mitigation.",
        "- 2022 rate-shock window Sharpe >= 1.0.",
        "- High-vol regime (SPY 20d vol top quartile) Sharpe >= 0.9 x V3 baseline of 1.62.",
        "",
        "## Section 6 - Out of Scope for V4",
        "- New alpha signals; V4 inherits Pillar 4 alpha unchanged.",
        "- Intraday execution; V4 keeps daily rebalance cadence.",
        "- Live trading infrastructure; this remains a separate ops workstream.",
        "- Multi-asset or non-equity extension.",
        "- Replacing the existing factor-tape limitation; Section 2 documents the limitation.",
        "",
        "## Section 7 - Open Risks & Known Limitations",
        "- 5.5 OQ#1: no canonical size/value/momentum factor tape; residual alpha cannot be proven free of hidden factor exposure.",
        f"- 5.5 OQ#2 / 5.8 Part A: {verdict['verdict']}. {verdict['deprecation_notice']}",
        "- 5.6 measurement limitation: 60d-only beta monitoring is blind to fast events; mitigated by REQ-F-004.",
        "- 5.6 paradox: removing residual beta drift may remove P&L-positive exposure in rate-shock regimes; mitigated by REQ-F-001, REQ-F-005, and the Section 5 acceptance gate.",
        "- 5.4 capacity: V4 must re-run the full Stage 5.4 capacity study; V3's <$5M capacity number is a V3-specific artifact, not a forward-looking V4 estimate.",
        "",
    ]
    return "\n".join(lines)


def _req(
    req_id: str,
    category: str,
    requirement: str,
    body: str,
    acceptance_criteria: str,
    anti_criteria: str,
    source_stage: str,
    source_item_id: str,
    priority: str,
    depends_on: str,
) -> dict[str, str]:
    return {
        "req_id": req_id,
        "category": category,
        "requirement": f"{requirement}: {body}",
        "acceptance_criteria": acceptance_criteria,
        "anti_criteria": anti_criteria,
        "source_stage": source_stage,
        "source_item_id": source_item_id,
        "priority": priority,
        "depends_on": depends_on if depends_on else "none",
    }


def _reconciliation_text(verdict: dict[str, str], summary: pd.Series) -> str:
    table = pd.DataFrame([summary.to_dict()])
    return "\n".join(
        [
            "### V3 Canonical Reconciliation",
            f"- Verdict: **{verdict['verdict']}**.",
            f"- Canonical path: `{verdict['canonical_path']}`.",
            f"- Deprecation notice: {verdict['deprecation_notice']}",
            "- Reconciliation summary:",
            _markdown_table(table),
        ]
    )


def _requirement_sections(frame: pd.DataFrame) -> list[str]:
    sections: list[str] = []
    for _, row in frame.iterrows():
        sections.extend(
            [
                f"### {row['req_id']}: {str(row['requirement']).split(':', 1)[0]}",
                f"Source: {row['source_item_id']}, {row['source_stage']}",
                f"Requirement: {str(row['requirement']).split(':', 1)[1].strip()}",
                "Acceptance criteria:",
                *_bulletize(row["acceptance_criteria"]),
                "Anti-criteria:",
                *_bulletize(row["anti_criteria"]),
                f"Priority: {row['priority']}",
                f"Depends on: {row['depends_on']}",
                "",
            ]
        )
    return sections


def _bulletize(text: str) -> list[str]:
    return [f"- {part.strip()}" for part in str(text).split(";") if part.strip()]


if __name__ == "__main__":
    main()

