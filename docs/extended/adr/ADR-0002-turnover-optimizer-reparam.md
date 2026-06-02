# ADR-0002: Turnover-Aware Optimizer Reparameterization

Date: 2026-05-31
Status: PRE-REGISTERED

Pre-registration freeze note: this workspace is not a git repository, so the requested pre-grid git commit cannot be performed. The ADR-0002 grid runner records this document's SHA256 before execution and writes it into `results/adr0002_grid/adr0002_manifest.json` as the freeze evidence.

## A. Hypothesis

D2 turnover-aware optimizer calibration is suboptimal. There exists a parameter set `(turnover_penalty, no_trade_band_bps, lambda_beta, sector_net_cap)` that satisfies the design-locked full-sample gates at the same time:

- `G-REQ-F-001-tail-turnover >= 0.75`
- `G-Preserve-HighVol-Sharpe >= 1.458`
- `G-Preserve-2022-Sharpe >= 1.026`

The hypothesis is evaluated without changing D2-D7 algorithm code, design thresholds, or acceptance-gate definitions.

## B. Parameter Grid

Baseline source: `config/v4.yaml` is absent in this workspace, so ADR-0002 uses the effective E1 replay baseline recorded here.

| param | E1 baseline | grid values | size | rationale |
| --- | ---: | --- | ---: | --- |
| `turnover_penalty` | `4.0` | `{baseline x 1, baseline x 2, baseline x 5, baseline x 10}` | 4 | Tail-turnover reduction was 0.4814 vs 0.75, so stronger turnover penalty is tested within the 16-point timebox. |
| `no_trade_band_bps` | `100.0` | `{baseline x 1, baseline x 3}` | 2 | Suppress immaterial churn without expanding the grid. |
| `lambda_beta` | `10.0` | `{baseline x 1, baseline x 0.5}` | 2 | High-vol Sharpe failure may reflect excess beta penalty pressure. |
| `sector_net_cap` | `0.10` | `{0.10}` | 1 | Sector gates already passed; moving this risks breaking a passing gate and does not directly target the failed gates. |

Total grid size: `4 x 2 x 2 x 1 = 16` points. This grid is frozen for ADR-0002; no points may be added after execution starts.

The materialized values are:

- `turnover_penalty`: `4.0`, `8.0`, `20.0`, `40.0`
- `no_trade_band_bps`: `100.0`, `300.0`
- `lambda_beta`: `10.0`, `5.0`
- `sector_net_cap`: `0.10`

## C. Point-Level Evaluation Criteria

Each grid point runs a full E1 replay and all 17 acceptance gates. Point outcomes are classified independently:

- `GO-CANDIDATE`: all three E1 non-PASS gates pass and the other 14 gates remain PASS.
- `PARTIAL-CANDIDATE`: at least two of the three E1 non-PASS gates pass, and no other gate regresses from PASS to FAIL.
- `REJECTED`: all other outcomes, including TIMEOUT or CRASH.

The three E1 non-PASS gates are:

- `G-REQ-F-001-tail-turnover`
- `G-Preserve-HighVol-Sharpe`
- `G-Preserve-2022-Sharpe`

## D. ADR-0002 Decision Rule

The final decision is applied mechanically:

| grid result | ADR-0002 decision | follow-up |
| --- | --- | --- |
| At least one `GO-CANDIDATE` | `GO-A` | Promote the selected point, rerun E1, refresh reports, and advance `REQ-F-001`. |
| Zero `GO-CANDIDATE` and at least one `PARTIAL-CANDIDATE` | `ESCALATE-B` | Keep config unchanged and dispatch ADR-0003 design revision. |
| Zero `GO-CANDIDATE` and zero `PARTIAL-CANDIDATE` | `ESCALATE-B` | Keep config unchanged, mark stronger structural-tradeoff evidence, and dispatch ADR-0003 design revision. |

## E. Tiebreak And Exit Conditions

If multiple `GO-CANDIDATE` points exist, choose the point with the highest `G-Preserve-HighVol-Sharpe`; if still tied, choose the smallest `turnover_penalty`.

The grid stops after 16 points. No additional points are allowed. TIMEOUT or CRASH points are classified as `REJECTED` and are not retried.
