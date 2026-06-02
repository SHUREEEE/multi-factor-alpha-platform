# Pillar 5 Stage 5.5 - Risk Decomposition & Factor Attribution

## Plan

1. Reuse locked Stage 5.1 production sizing and Stage 5.4 findings as fixed inputs; do not re-run or reinterpret 5.4 capacity.
2. Load cached V3 production weights, daily returns, market proxy, and sector map from `results/pillar5_artifacts/`.
3. Inspect Pillar 4 construction scripts to determine whether pre-neutralization weights can be reconstructed safely; if not, document the gap and proceed with post-neutralization analysis.
4. Build a daily attribution that decomposes production-sized V3 P&L into market beta, sector, optional factor, and residual alpha buckets.
5. Save chart-ready exposure time series, including rolling residual beta and sector net exposure before/after neutralization where available.
6. Validate decomposition identity in code and tests: attributed components plus residual must reconcile to total P&L within numerical tolerance.
7. Report return and variance shares by bucket, neutralization effectiveness, and whether the expensive daily neutralization layer identified in Stage 5.4 is effective.

## Executive Summary
1. **Residual alpha remains the dominant bucket**, explaining 112.9% of variance under the market + sector decomposition. The accessible risk buckets do not explain most day-to-day V3 movement.

2. **Neutralization reduces ex-ante beta mechanically, but realized beta is still non-zero.** Total realized beta is 0.154 and residual-alpha beta is 0.269, so beta drift remains a live risk even after neutralization.

3. **The expensive Stage 5.4 neutralization layer is beta-effective but not risk-complete.** Market beta contributes only 0.1% of variance, while sector active exposure has a -13.0% covariance share, meaning it offsets rather than explains total P&L. V4 should keep beta control, but make the neutralization layer turnover-aware and add explicit sector/residual-beta monitoring.

## Setup
- Production sizing: target vol 10%, leverage scaler 0.7025, production gross 1.405x.
- Primary stream includes 10 bps transaction costs, consistent with Stage 5.1.
- Pre-neutralization weights were reconstructed from the raw weekly-decile Pillar 4 code path. Post-neutralization weights use the locked Pillar 5 cached V3 production book, preserving the Stage 5.1-5.4 baseline exactly.
- Factor-return tape for canonical size/value/momentum risk factors is not present; the main attribution therefore uses market beta, sector active exposure, transaction cost, and residual alpha.

## Attribution Summary
| bucket | ann_return_contribution | return_share | variance_share |
| --- | --- | --- | --- |
| Market beta | 0.0003 | 0.0056 | 0.0007 |
| Sector active exposure | -0.0204 | -0.4096 | -0.1296 |
| Size/value/momentum | 0.0 | 0.0 | 0.0 |
| Transaction cost | -0.0294 | -0.5906 | 0.0003 |
| Residual alpha | 0.1004 | 2.017 | 1.1287 |

## Return Contribution
| bucket | ann_return_contribution | return_share |
| --- | --- | --- |
| Market beta | 0.0003 | 0.0056 |
| Sector active exposure | -0.0204 | -0.4096 |
| Size/value/momentum | 0.0 | 0.0 |
| Transaction cost | -0.0294 | -0.5906 |
| Residual alpha | 0.1004 | 2.017 |

## Variance Contribution
Variance shares are computed as covariance(component, total) / variance(total), so additive components sum to about 100%.
| bucket | variance_share |
| --- | --- |
| Market beta | 0.0007 |
| Sector active exposure | -0.1296 |
| Size/value/momentum | 0.0 |
| Transaction cost | 0.0003 |
| Residual alpha | 1.1287 |
| Variance share sum | 1.0 |

## Neutralization Effectiveness Check
| metric | raw_pre_neutralization | post_v3 |
| --- | --- | --- |
| Average ex-ante beta | 0.3135 | 0.0014 |
| Average rolling 60d realized beta | 0.3489 | 0.1561 |
| Average max abs sector net | 0.0751 | 0.141 |
| 95th pct max abs sector net | 0.1144 | 0.3035 |
| Average net exposure | 0.0 | 0.0 |
Post-neutralization residual alpha beta is `0.269`, which is materially non-zero. This is consistent with Pillar 4/5.3: ex-ante beta can be near zero while realized beta drifts during regime changes.

## Connection to Stage 5.4
Stage 5.4 showed that daily beta-neutralization / sector-cap post-processing drives tail rotation days and the <$5M capacity ceiling. Stage 5.5 says that layer is not pointless on beta: ex-ante beta falls from roughly 0.31 pre-neutralization to near zero post-V3. But it is not sufficient either: residual realized beta remains non-zero, sector exposure has a negative covariance share (-13.0%), and most variance is still residual alpha/noise under the available risk model. The V4 hook is therefore not 'remove neutralization'; it is 'redesign neutralization with turnover penalty/no-trade bands, sector exposure checks after the final solve, and explicit residual beta monitoring.'

## OPEN QUESTIONS FOR USER
- Canonical size/value/momentum factor-return series are not available in the current repository. I used the accessible, auditable decomposition (market beta + sector active exposure + transaction cost + residual alpha). If you want explicit size/value/momentum risk attribution, provide or approve a risk-factor return tape or a construction rule for mimicking portfolios.
- Reconstructing V3 directly from `scripts/run_pillar4_stage45_neutralization.py` does not exactly match the locked `results/pillar5_artifacts/v3_weights.parquet` cache. I kept the locked cache for all post-neutralization attribution and used reconstructed raw weights only for pre/post effectiveness. Before V4 implementation, reconcile whether Stage 4.5's `beta_neutral -> sector_cap -> beta_neutral` path or Pillar 5's cached production book is the canonical construction.

## Outputs
- Daily attribution: `results/pillar5_stage55_factor_attribution.csv`.
- Exposure time series: `results/pillar5_stage55_exposure_timeseries.csv`.
