# Pillar 3 Stage 1 (Price-Only) — Final Summary

## Pipeline Status: Complete

- 6 price-based factors evaluated on S&P 500 + NASDAQ 100, 2014-2024.
- IC, IR, t-stat, hit rate, quantile spread, long-short Sharpe, monotonicity, IC decay, and Fama-MacBeth all implemented.
- Direction audit completed; no automatic sign flips applied.
- Sector neutralization implemented using Wikipedia GICS sectors with 96.9% coverage.

## Key Findings

### 1. `short_term_reversal` — The Only Robust Price-Only Signal

- IC, long-short return, and monotonicity all align positively across 1d/5d/21d.
- Sector neutralization strengthened the signal: long-short Sharpe improved from 0.47 to 0.60.
- Sector-neutral Fama-MacBeth t-stat increased from 1.30 before neutralization to 1.57 after neutralization.
- This looks more like stock-specific mean reversion than sector rotation.
- Recommended for Pillar 4 multi-factor portfolio construction.

### 2. `momentum_12_1` — Primarily Sector Momentum

- Before neutralization, `momentum_12_1` had weak but statistically positive 1d IC with t-stat around 2.6.
- After sector neutralization, long-short Sharpe collapsed from 0.08 to 0.01.
- Sector-neutral Fama-MacBeth t-stat is only 0.41.
- The signal appears driven mostly by sector rotation, not stock-specific trends.
- Not recommended for Pillar 4 as a standalone price-only factor.

### 3. Low-Volatility Factors — Regime-Specific Reversal

- `idiosyncratic_vol`, `realized_vol`, and `beta_inverse` show negative long-short spreads.
- Sector neutralization did not eliminate the negative spread; for `idiosyncratic_vol` and `realized_vol`, the negative regression evidence remains statistically meaningful.
- Sector-neutral Fama-MacBeth t-stats:
  - `idiosyncratic_vol`: -2.61
  - `realized_vol`: -2.35
  - `beta_inverse`: -1.37
- This suggests a cross-sector high-volatility premium during 2014-2024, likely linked to the tech-led growth regime.
- Documented as a regime-specific research finding, not treated as a sign bug.

### 4. `week_52_high` — Reversal, Not Trend

- `week_52_high` behaves more like a reversal factor than a trend factor in this sample.
- Negative spread persists after sector neutralization.
- Sector-neutral Fama-MacBeth t-stat is -2.11.
- Not recommended for Pillar 4 as currently defined.

## Sector Neutralization Implementation

- Wikipedia GICS sectors cover 500/516 tickers, or 96.9% of the current universe.
- Remaining 16 tickers are marked as `Unknown`: ALNY, ARM, ASML, BK, CCEP, FER, INSM, MELI, MRVL, MSTR, PDD, QQQ, SHOP, SPY, TRI, ZS.
- Neutralization uses cross-sectional OLS residuals per date: `factor_value ~ sector_dummies + log_market_cap if available`.
- yfinance fallback is implemented with batching, retry, and resume, but was rate-limited during this run. Wikipedia coverage was already high enough to proceed.

## Known Limitations

- No market-cap data yet, so size-based controls are absent.
- Universe is large-cap only, where many published factor premia are weaker.
- Sample period 2014-2024 includes a strong tech-led growth regime that may not generalize to other periods.
- The universe uses current S&P 500 + NASDAQ-100 membership, so survivorship bias remains a known limitation.

## Next Steps (Stage 2)

- Repair the fundamentals pipeline to activate Value/Quality/Size factors.
- Re-run fundamental-stage and full-stage research with sector neutralization.
- Proceed to Pillar 4 using `short_term_reversal` as the primary price-only candidate, then add fundamental candidates after Stage 2.
