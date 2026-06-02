# ADR-0001: V3 Canonical Neutralization Order

## Status
Accepted - Option 1 (cache order / single-pass)

## Context
Stage 5.8 produced Verdict C because reconstructed Stage 4.5 V3 weights and the locked Pillar 5 cached V3 weights do not agree by construction. The post-diagnosis report identifies H6 as the root cause: Stage 4.5 applies an outer beta-neutralization before sector capping, while the Pillar 5 cache builder applies `sector_cap_then_renormalize_beta` directly to raw weights.

Phase A checked the H3 active-symbol asymmetry and classified 100.0% of observed asymmetry rows as downstream effects of the neutralization-order difference. H3 is therefore treated as a derivative symptom, not an independent universe-membership root cause.

Severity is economically cosmetic: Sharpe diff 0.007, return correlation 0.993, and V3 NO-GO capacity conclusion invariant under both books.

## Decision Options
### Option 1: Canonical = Cache Order (single-pass)
Use `sector_cap_then_renormalize_beta` directly on raw weights. Remediation: remove the outer `beta_neutralize_weights` call from `scripts/run_pillar4_stage45_neutralization.py:89-95` or update Stage 4.5 to call the cache-builder path. Theoretical grounding: standard single-pass sector cap followed by beta neutralization. Risk: Stage 4 historical numbers documented under the double-pass order may shift; verify published Stage 4 metrics remain immaterially changed.

### Option 2: Canonical = Stage 4.5 Order (double-pass)
Use outer beta-neutralization and then `sector_cap_then_renormalize_beta`. Remediation: change `scripts/pillar5_common.py:146-159` to insert `beta_neutralize_weights` before the helper. Risk: Pillar 5 cached results shift; Stages 5.4-5.7 should be recomputed under the new canonical book.

### Option 3: Refactor Helper
Split `sector_cap_then_renormalize_beta` into explicit `sector_cap` and `beta_neutralize` calls; require both callers to invoke the documented sequence. Highest cost, but eliminates this ambiguity class permanently.

## Recommended Option
Recommend **Option 1: Canonical = cache order (single-pass)**. It matches standard single-pass neutralization semantics, preserves the reviewed Pillar 5 outputs, minimizes downstream rework, and the diagnosis shows the economic difference versus double-pass is cosmetic while the NO-GO conclusion is invariant.

## Acceptance Criteria For Closing Verdict C
- Stage 5.8 Part A rerun produces mean weight L1 < 1e-10 over the full sample.
- Stage 5.8 Part A rerun produces max return diff < 0.1 bps over the full sample.
- REQ-F-014 and REQ-N-004 are updated from blocked to satisfied.

## Out Of Scope
- This ADR does not authorize V4 implementation.
- This ADR does not regenerate any cached artifact.
- This ADR does not modify production code.
- Execution requires user approval as a separate change.

## Approval
Approver: repo owner

Approval date: 2026-05-30

Approved option: Option 1 (cache order / single-pass)

Basis: Phase A confirmed H3 100% derivative of H6; Phase 3 confirmed economic severity cosmetic and NO-GO invariant; Option 1 minimizes Pillar 5 downstream rework.
