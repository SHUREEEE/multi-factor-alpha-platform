# ADR-0002 Decision Report

A-prime note: the initial ADR-0002 grid exposed dead calibration wiring in the E1 replay scaffold. This report reflects the rerun after minimal replay-path wiring repair and a passing two-point sanity probe.

Hypothesis reference: `docs/adr/ADR-0002-turnover-optimizer-reparam.md` Section A.

Evidence root: `results\adr0002_grid`.

## Grid Results

## Sanity Probe

Probe status: `PARAMETER_SENSITIVE`.
Probe pass: `True`.
Weight hash differs: `True`.

| point | turnover_penalty | no_trade_band_bps | lambda_beta | sector_net_cap | tail_turnover | highvol_sharpe | shock_2022 | classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| point_00 | 4.00 | 100.00 | 10.00 | 0.10 | 0.766544 | 1.347425 | 1.004045 | REJECTED |
| point_01 | 4.00 | 100.00 | 5.00 | 0.10 | 0.766544 | 1.333615 | 1.006543 | REJECTED |
| point_02 | 4.00 | 300.00 | 10.00 | 0.10 | 0.857143 | 1.347425 | 1.004045 | REJECTED |
| point_03 | 4.00 | 300.00 | 5.00 | 0.10 | 0.857143 | 1.333615 | 1.006543 | REJECTED |
| point_04 | 8.00 | 100.00 | 10.00 | 0.10 | 0.711191 | 1.334408 | 1.000145 | REJECTED |
| point_05 | 8.00 | 100.00 | 5.00 | 0.10 | 0.711191 | 1.347224 | 1.002732 | REJECTED |
| point_06 | 8.00 | 300.00 | 10.00 | 0.10 | 0.919355 | 1.334408 | 1.000145 | REJECTED |
| point_07 | 8.00 | 300.00 | 5.00 | 0.10 | 0.919355 | 1.347224 | 1.002732 | REJECTED |
| point_08 | 20.00 | 100.00 | 10.00 | 0.10 | 0.911290 | 1.367642 | 0.997739 | REJECTED |
| point_09 | 20.00 | 100.00 | 5.00 | 0.10 | 0.911290 | 1.334428 | 1.000381 | REJECTED |
| point_10 | 20.00 | 300.00 | 10.00 | 0.10 | 1.000000 | 1.367642 | 0.997739 | REJECTED |
| point_11 | 20.00 | 300.00 | 5.00 | 0.10 | 1.000000 | 1.334428 | 1.000381 | REJECTED |
| point_12 | 40.00 | 100.00 | 10.00 | 0.10 | 1.000000 | 1.367552 | 0.996925 | REJECTED |
| point_13 | 40.00 | 100.00 | 5.00 | 0.10 | 1.000000 | 1.334360 | 0.999586 | REJECTED |
| point_14 | 40.00 | 300.00 | 10.00 | 0.10 | 1.000000 | 1.367552 | 0.996925 | REJECTED |
| point_15 | 40.00 | 300.00 | 5.00 | 0.10 | 1.000000 | 1.334360 | 0.999586 | REJECTED |

## Decision

Decision: **ESCALATE-B**.

Applied ADR-0002 Section D mechanically: no GO-CANDIDATE points were present, so the decision is ESCALATE-B.

## Best Observed Gaps

- Tail turnover: best `1.000000` vs threshold `0.750000`, gap `0.250000`.
- High-vol Sharpe: best `1.367642` vs threshold `1.458000`, gap `-0.090358`.
- 2022 Sharpe: best `1.006543` vs threshold `1.026000`, gap `-0.019457`.

No threshold relaxation is proposed here. ADR-0002 is a grid evaluation record, not a design revision.
