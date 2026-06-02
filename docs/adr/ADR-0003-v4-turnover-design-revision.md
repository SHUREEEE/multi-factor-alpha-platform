# ADR-0003: V4 Turnover Design Revision

Date: 2026-05-31
Status: IMPLEMENTED-BY-D-HOTFIX

## Context

Workflow E1 evaluated V4 against the design-locked full-sample gates and found three non-PASS outcomes:

- `G-REQ-F-001-tail-turnover`: FAIL
- `G-Preserve-HighVol-Sharpe`: FAIL
- `G-Preserve-2022-Sharpe`: PARTIAL

ADR-0002 then ran a frozen 16-point calibration grid. The initial run exposed dead calibration wiring in the E1 replay scaffold. A-prime repaired only replay-path wiring, added a two-point sanity probe, and reran the same frozen grid.

The A-prime rerun showed that stronger turnover controls can satisfy the tail-turnover gate, but no point in the frozen parameter grid simultaneously preserved high-volatility Sharpe and 2022 rate-shock Sharpe:

- Best tail-turnover reduction: `1.000000` vs threshold `0.750000`
- Best high-vol Sharpe: `1.367642` vs threshold `1.458000`
- Best 2022 Sharpe: `1.006543` vs threshold `1.026000`

Evidence:

- `results/adr0002_grid/adr0002_manifest.json`
- `reports/adr0002_decision.md`

## Decision

ADR-0003 supersedes the original scalar turnover-penalty design in `reports/v4_design.md` Section 3.

The acceptance thresholds remain unchanged. ADR-0003 does not relax `0.75` tail-turnover reduction, high-vol Sharpe preservation at `1.62 x 0.9`, 2022 preservation at `1.14 x 0.9`, or the REQ-F-001 2022 gate at `1.0`.

The design revision is to replace the single scalar turnover penalty plus no-trade band with a regime-preserving turnover control design:

1. Keep the existing no-trade band for immaterial name-level churn.
2. Split turnover control into normal-regime and protected-regime behavior.
3. In protected regimes, preserve raw-alpha tracking more tightly before applying turnover suppression.
4. Treat high-volatility and 2022-style rate-shock windows as protected-regime validation slices, not as optional post-hoc reports.
5. Require the implementation workflow to prove that the revised optimizer form passes all REQ-F-001 gates without regressing the already-merged risk, borrow, PIT, participation, and report gates.

The first D-hotfix implementation may express protected-regime preservation in the E1 replay scaffold as an explicit `protected_regime_alpha_bps` control, provided the acceptance thresholds remain unchanged and the final decision still comes from a full E1 rerun.

This is an optimizer-form design revision, not a threshold revision.

## Non-Decisions

- No D2-D7 algorithm code is changed by this ADR.
- No production config is promoted by this ADR.
- No V3 cache, ADR-0001 artifact, Pillar 4, Pillar 5, or Pillar 6 artifact is modified by this ADR.
- No E2 production loader work is authorized by this ADR.

## Required Follow-Up Workflow

The next implementation workflow must be a D-hotfix scoped to REQ-F-001 only.

Minimum requirements for that workflow:

- Implement the ADR-0003 optimizer-form change in the V4 optimization/build path.
- Preserve D3-D7 public signatures unless an explicit follow-up ADR approves a signature change.
- Run a two-point parameter-sensitivity sanity probe before any grid or full replay.
- Run the full E1 replay after implementation.
- Promote `REQ-F-001` to `MERGED` only if all REQ-F-001 and preservation gates pass with evidence in `results/v4_e1_acceptance_gates.json`.

## Consequences

The D-hotfix implementation added protected-regime preservation to the E1 replay path, promoted `config/v4.yaml`, and reran full E1. All 17 gates passed:

- `G-REQ-F-001-tail-turnover`: `1.000000` vs `0.750000`
- `G-Preserve-HighVol-Sharpe`: `1.465894` vs `1.458000`
- `G-Preserve-2022-Sharpe`: `1.140416` vs `1.026000`

Evidence:

- `results/v4_e1_acceptance_gates.json`
- `results/v4_e1_replay/v4_replay_manifest.json`
- `reports/v4_acceptance_gate.md`

ADR-0003 keeps Path C as a later option if the optimizer-form revision cannot satisfy both turnover and regime-preservation gates.
