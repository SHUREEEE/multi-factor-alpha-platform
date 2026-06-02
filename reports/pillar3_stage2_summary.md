# Pillar 3 Stage 2 Summary

## Status

Fundamentals pipeline repair is code-complete, but the current local raw fundamentals files are empty.
The pipeline now degrades gracefully: missing fundamental fields skip only the affected factor and do not crash the run.

## Fundamentals Data Finding

- `data/raw/fundamentals_raw.parquet` shape: `(0, 4)`.
- `data/processed/fundamentals.parquet` shape: `(0, 5)`.
- `data/processed/daily_fundamentals.parquet` is missing.
- Required fields unavailable: market_cap, book_value, net_income, revenue, total_assets, gross_profit, operating_cashflow.
- See `reports/fundamentals_data_audit.md` for the detailed audit.

## Fundamental Factors

Computed fundamental factors: 0 / 9.
Skipped fundamental factors: book_to_market, earnings_yield, sales_to_price, roe, gross_profitability, accruals, log_market_cap, log_total_assets, log_revenue.

No substitute fields were invented. This is intentional: using guessed accounting fields would create false precision and possible look-ahead or definition errors.

## Full-Stage Research Output

Because no fundamental factors were available, `results/factor_summary_full_stage.csv` currently contains the six price-only factors only.

| factor_name | ic_mean_1d | ic_ir_1d | long_short_sharpe | monotonicity | fama_macbeth_tstat |
| --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 0.012438 | 0.052197 | 0.081239 | -0.115152 | 0.451802 |
| short_term_reversal | 0.005302 | 0.027974 | 0.472916 | 0.806061 | 1.297321 |
| week_52_high | 0.004287 | 0.018507 | -0.585161 | -0.927273 | -1.841433 |
| idiosyncratic_vol | 0.001339 | 0.007667 | -0.765555 | -0.890909 | -2.551918 |
| realized_vol | 0.000828 | 0.003322 | -0.545683 | -0.939394 | -2.252282 |
| beta_inverse | 0.000021 | 0.000072 | -0.414802 | -0.769697 | -1.385760 |

## Stage 1 vs Full Stage

Full-stage results match the available price-only universe because no fundamental columns were activated.
The Pillar 4 candidate pool is therefore unchanged from Stage 1.

## Pillar 4 Handoff Update

Path B has now been formally adopted: use the sector-neutral price-factor path as the active Pillar 4 mainline while fundamentals remain unavailable.
The Pillar 4 baseline is complete as `baseline_4f`, with direction-adjusted factors, 1-day-lagged trading, and an annualized Sharpe of about 0.77 before transaction costs.
The volatility factors are now used through a research-approved direction transform in the combination layer, not by rewriting the raw factor definitions.
`idiosyncratic_vol` and `realized_vol` have average rank correlation around 0.9167, so Stage 4.2 will test de-duplication or downweighting before Stage 4.3.

## Updated Pillar 4 Candidate List

- Include: `short_term_reversal` as the primary price-only candidate.
- Exclude for now: `momentum_12_1`, `week_52_high`, `idiosyncratic_vol`, `realized_vol`, `beta_inverse` as standalone long-high-score factors.
- Pending Stage 2 data repair: value, quality, and size candidates.

## Next Required Fix

The blocker is upstream data acquisition, not factor math. The next task is to repair fundamental downloading so that the raw file contains actual long-format rows before daily as-of panels are built.
