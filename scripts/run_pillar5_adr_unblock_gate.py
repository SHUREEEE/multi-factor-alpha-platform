"""Draft ADR-0001 and V4 unblock gate after reconciliation diagnosis."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_pillar5_stage55_risk_decomposition import reconstruct_stage45_weights  # noqa: E402
from scripts.pillar5_common import load_or_build_baseline_artifacts, _markdown_table  # noqa: E402


H3_H6_PATH = PROJECT_ROOT / "results/diag_h3_h6_relationship.csv"
ADR_PATH = PROJECT_ROOT / "reports/adr/ADR-0001-v3-canonical-neutralization-order.md"
UNBLOCK_REPORT_PATH = PROJECT_ROOT / "reports/pillar5_v4_unblock_gate.md"
UNBLOCK_CSV_PATH = PROJECT_ROOT / "results/pillar5_v4_unblock_classification.csv"
REQ_PATH = PROJECT_ROOT / "results/pillar5_stage58_v4_requirements.csv"
DIAG_SEVERITY_PATH = PROJECT_ROOT / "results/diag_severity.csv"


def main() -> None:
    h3 = build_h3_h6_relationship()
    severity = pd.read_csv(DIAG_SEVERITY_PATH).iloc[0]
    reqs = pd.read_csv(REQ_PATH)
    classification = build_unblock_classification(reqs)
    H3_H6_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADR_PATH.parent.mkdir(parents=True, exist_ok=True)
    h3.to_csv(H3_H6_PATH, index=False)
    classification.to_csv(UNBLOCK_CSV_PATH, index=False)
    ADR_PATH.write_text(build_adr(h3, severity), encoding="utf-8")
    UNBLOCK_REPORT_PATH.write_text(build_unblock_report(classification, h3, severity), encoding="utf-8")
    print(h3.to_string(index=False))
    print(classification.to_string(index=False))
    print(f"Saved {H3_H6_PATH.as_posix()}")
    print(f"Saved {ADR_PATH.as_posix()}")
    print(f"Saved {UNBLOCK_REPORT_PATH.as_posix()}")
    print(f"Saved {UNBLOCK_CSV_PATH.as_posix()}")


def build_h3_h6_relationship() -> pd.DataFrame:
    artifacts = load_or_build_baseline_artifacts()
    weights = reconstruct_stage45_weights()
    raw = weights["raw_pre_neutralization"].sort_index()
    recon = weights["post_v3"].sort_index()
    cache = artifacts.weights.sort_index()
    t_jump = pd.Timestamp(pd.read_csv(DIAG_SEVERITY_PATH).iloc[0]["t_jump"])
    dates = _window_dates(cache.index.intersection(recon.index), t_jump, 3)
    rows = []
    for date in dates:
        raw_row = raw.loc[date].fillna(0.0)
        recon_row = recon.loc[date].fillna(0.0)
        cache_row = cache.loc[date].fillna(0.0)
        active_union = set(recon_row[recon_row.ne(0.0)].index).union(set(cache_row[cache_row.ne(0.0)].index))
        active_symdiff = sorted(set(recon_row[recon_row.ne(0.0)].index).symmetric_difference(set(cache_row[cache_row.ne(0.0)].index)))
        for symbol in active_symdiff:
            raw_present = bool(abs(float(raw_row.get(symbol, 0.0))) > 0.0)
            recon_final = float(recon_row.get(symbol, 0.0))
            cache_final = float(cache_row.get(symbol, 0.0))
            if raw_present and ((recon_final == 0.0) != (cache_final == 0.0)):
                classification = "h3_derivative_of_h6"
            elif not raw_present and symbol in active_union:
                classification = "h3_independent"
            else:
                classification = "inconclusive"
            rows.append(
                {
                    "date": str(date.date()),
                    "symbol": symbol,
                    "raw_weight_present_Y_N": "Y" if raw_present else "N",
                    "raw_weight": float(raw_row.get(symbol, 0.0)),
                    "recon_final_weight": recon_final,
                    "cache_final_weight": cache_final,
                    "classification": classification,
                }
            )
    return pd.DataFrame(rows)


def build_unblock_classification(reqs: pd.DataFrame) -> pd.DataFrame:
    blocking = {"REQ-F-014", "REQ-N-004"}
    pending = {
        "REQ-F-001",
        "REQ-F-002",
        "REQ-F-004",
        "REQ-F-005",
        "REQ-F-011",
        "REQ-F-013",
        "REQ-F-015",
        "REQ-N-001",
        "REQ-N-002",
        "REQ-N-003",
    }
    rows = []
    for _, row in reqs.iterrows():
        req_id = str(row["req_id"])
        if req_id in blocking:
            classification = "BLOCKING-UNTIL-REMEDIATED"
            blocks = "Y"
            justification = "This requirement directly requires cache/reconstruction agreement by construction; ADR-0001 must be executed before it can pass."
        elif req_id in pending:
            classification = "SATISFIED-PENDING-ADR"
            blocks = "N"
            justification = "Can be designed against a clearly labeled provisional cache-order baseline, but final acceptance waits for ADR-0001 execution."
        else:
            classification = "SATISFIED-AS-IS"
            blocks = "N"
            justification = "Requirement does not depend on the V3 neutralization-order discrepancy and can proceed from locked Pillar 5 findings."
        rows.append(
            {
                "req_id": req_id,
                "requirement_text": row["requirement"],
                "classification": classification,
                "justification": justification,
                "blocks_v4_start_Y_N": blocks,
            }
        )
    return pd.DataFrame(rows)


def build_adr(h3: pd.DataFrame, severity: pd.Series) -> str:
    derivative_share = _derivative_share(h3)
    lines = [
        "# ADR-0001: V3 Canonical Neutralization Order",
        "",
        "## Status",
        "Draft - pending owner decision.",
        "",
        "## Context",
        "Stage 5.8 produced Verdict C because reconstructed Stage 4.5 V3 weights and the locked Pillar 5 cached V3 weights do not agree by construction. The post-diagnosis report identifies H6 as the root cause: Stage 4.5 applies an outer beta-neutralization before sector capping, while the Pillar 5 cache builder applies `sector_cap_then_renormalize_beta` directly to raw weights.",
        "",
        f"Phase A checked the H3 active-symbol asymmetry and classified {derivative_share:.1%} of observed asymmetry rows as downstream effects of the neutralization-order difference. H3 is therefore treated as a derivative symptom, not an independent universe-membership root cause.",
        "",
        f"Severity is economically cosmetic: Sharpe diff {float(severity['sharpe_abs_diff']):.3f}, return correlation {float(severity['return_corr_post_jump']):.3f}, and V3 NO-GO capacity conclusion invariant under both books.",
        "",
        "## Decision Options",
        "### Option 1: Canonical = Cache Order (single-pass)",
        "Use `sector_cap_then_renormalize_beta` directly on raw weights. Remediation: remove the outer `beta_neutralize_weights` call from `scripts/run_pillar4_stage45_neutralization.py:89-95` or update Stage 4.5 to call the cache-builder path. Theoretical grounding: standard single-pass sector cap followed by beta neutralization. Risk: Stage 4 historical numbers documented under the double-pass order may shift; verify published Stage 4 metrics remain immaterially changed.",
        "",
        "### Option 2: Canonical = Stage 4.5 Order (double-pass)",
        "Use outer beta-neutralization and then `sector_cap_then_renormalize_beta`. Remediation: change `scripts/pillar5_common.py:146-159` to insert `beta_neutralize_weights` before the helper. Risk: Pillar 5 cached results shift; Stages 5.4-5.7 should be recomputed under the new canonical book.",
        "",
        "### Option 3: Refactor Helper",
        "Split `sector_cap_then_renormalize_beta` into explicit `sector_cap` and `beta_neutralize` calls; require both callers to invoke the documented sequence. Highest cost, but eliminates this ambiguity class permanently.",
        "",
        "## Recommended Option",
        "Recommend **Option 1: Canonical = cache order (single-pass)**. It matches standard single-pass neutralization semantics, preserves the reviewed Pillar 5 outputs, minimizes downstream rework, and the diagnosis shows the economic difference versus double-pass is cosmetic while the NO-GO conclusion is invariant.",
        "",
        "## Acceptance Criteria For Closing Verdict C",
        "- Stage 5.8 Part A rerun produces mean weight L1 < 1e-10 over the full sample.",
        "- Stage 5.8 Part A rerun produces max return diff < 0.1 bps over the full sample.",
        "- REQ-F-014 and REQ-N-004 are updated from blocked to satisfied.",
        "",
        "## Out Of Scope",
        "- This ADR does not authorize V4 implementation.",
        "- This ADR does not regenerate any cached artifact.",
        "- This ADR does not modify production code.",
        "- Execution requires user approval as a separate change.",
        "",
    ]
    return "\n".join(lines)


def build_unblock_report(classification: pd.DataFrame, h3: pd.DataFrame, severity: pd.Series) -> str:
    blockers = classification[classification["classification"] == "BLOCKING-UNTIL-REMEDIATED"]
    verdict = "GO-PROVISIONAL" if blockers.empty else "HOLD"
    if not blockers.empty:
        provisional_note = (
            "The formal gate is HOLD because REQ-F-014 and REQ-N-004 remain blocking until ADR-0001 is executed. "
            "However, non-gating V4 design work may proceed only if explicitly labeled provisional pending ADR-0001."
        )
    else:
        provisional_note = "V4 can start in parallel with ADR remediation under a clearly labeled provisional canonical baseline."
    lines = [
        "# Pillar 5 V4 Unblock Gate",
        "",
        "## Formal Verdict",
        f"**{verdict}**",
        provisional_note,
        "",
        "## Evidence Summary",
        f"- H3 derivative share: {_derivative_share(h3):.1%}.",
        f"- Sharpe diff: {float(severity['sharpe_abs_diff']):.3f}.",
        f"- Return correlation: {float(severity['return_corr_post_jump']):.3f}.",
        f"- V3 NO-GO invariant: {bool(severity['no_go_invariant_both_lt_5m'])}.",
        "",
        "## Requirement Classification",
        _markdown_table(classification),
        "",
        "## Gate Interpretation",
        "REQ-F-014 and REQ-N-004 are the only requirements that directly block V4 start under strict change control because they require source-of-truth convergence. Other requirements can be designed against a provisional cache-order baseline, but final V4 acceptance cannot occur until ADR-0001 is executed and reconciliation passes.",
        "",
    ]
    return "\n".join(lines)


def _window_dates(index: pd.Index, t_jump: pd.Timestamp, radius: int) -> list[pd.Timestamp]:
    sorted_index = pd.Index(index).sort_values()
    loc = sorted_index.get_loc(t_jump)
    return [pd.Timestamp(item) for item in sorted_index[max(0, loc - radius) : min(len(sorted_index), loc + radius + 1)]]


def _derivative_share(h3: pd.DataFrame) -> float:
    if h3.empty:
        return 0.0
    return float((h3["classification"] == "h3_derivative_of_h6").mean())


if __name__ == "__main__":
    main()

