# Stage 4 Drift Triage After ADR-0001

Updated 2026-05-30: V3 metrics realigned to post-ADR-0001 canonical book (Option 1, cache order / single-pass). See `reports/stage4_drift_triage.md`.

## Context

ADR-0001 closed the V3 cache-vs-reconstruction mismatch by accepting Option 1: cache order / single-pass neutralization. Post-ADR reconciliation is exact, so this triage does not reopen Verdict C. It only classifies Stage 4 published metric drift against the post-ADR canonical book.

## Class 1 - Mechanically Expected Under Option 1

| metric | pre_value | post_value | rationale |
| --- | --- | --- | --- |
| average_abs_net_beta | 3.14e-16 | 0.004484 | Double-pass neutralization drove beta to machine zero; single-pass keeps beta controlled but not exactly zero. |
| average_net_beta | 1.16e-17 | 0.002732 | Same mechanism as average_abs_net_beta: single-pass is the accepted canonical semantics. |
| average_sector_concentration_short | 0.255268 | 0.323011 | Single-pass sector cap followed by beta renormalization can increase final short-side sector concentration; this is expected under Option 1. |

## Class 2 - Economically Small But Numerically Material

These metrics crossed the strict `abs_diff > 0.0005` published-precision threshold, but relative changes remain below 5% and are directionally consistent with the ADR diagnosis: the cache-order book is economically close, slightly higher Sharpe, slightly lower turnover, and shallower drawdown.

| metric | pre_value | post_value | rel_diff_pct |
| --- | --- | --- | --- |
| annualized_return | 0.061020 | 0.062651 | 2.67 |
| annualized_sharpe | 0.491133 | 0.497959 | 1.39 |
| net_cumulative_return | 0.889393 | 0.920842 | 3.54 |
| max_drawdown | -0.244215 | -0.238551 | 2.32 |
| average_daily_turnover | 0.171095 | 0.166159 | 2.89 |
| long_turnover | 0.061496 | 0.060526 | 1.58 |
| short_turnover | 0.109771 | 0.105809 | 3.61 |
| realized_beta_to_proxy | 0.215685 | 0.219096 | 1.58 |
| hit_rate | 0.508681 | 0.507204 | 0.29 |

## Class 3 - Unchanged / No Documentation Update Needed

| metric | value |
| --- | --- |
| average_gross_leverage | 1.955925 |
| average_sector_concentration_long | 0.196309 |
| large_beta_exposure_days | 0 |
| max_gross_leverage | 2.000000 |
| n_days | 2707 |

