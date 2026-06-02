# Pillar 6/7 Attribution Quarantine

## Verdict

The existing `results/strategy_reports/attribution_summary.json` and
`results/strategy_reports/final_tearsheet.png` are quarantined. They should not
be copied into `README.md`, a resume, or interview talking points.

## Blocking Issues

| issue | status | action |
| --- | --- | --- |
| Market-cap fallback | Blocking | `scripts/run_attribution.py` now fails closed unless a positive market-cap panel is supplied. Equal-positive fallback is available only through the explicit `--allow-equal-market-cap-fallback` smoke-test flag. |
| Gross/net attribution mismatch | Fixed in code | Attribution now reconciles to Pillar 6 net PnL by carrying `gross_total_return`, `transaction_cost_total`, and net `total_return` separately. |
| Turnover unit ambiguity | Fixed in code | Backtest metrics now emit `turnover_annual_x`; tearsheet summary renders turnover as `x/year`, not as a double-multiplied percent. |
| Strategy quality | Open | Current net Sharpe is below the sanity range and the old fallback attribution showed negative pure alpha. This is a strategy/portfolio-construction problem, not a README wording problem. |

## Current Data Finding

`data/processed/fundamentals.parquet` is empty in this workspace, so no
auditable `market_cap` panel exists for Barra-style sqrt(market_cap) WLS. The
default attribution command now stops with:

```text
ValueError: No usable market_cap panel found. Barra-style attribution requires positive market caps for sqrt(market_cap) WLS weights.
```

## Accounting Finding

The old attribution summary used gross stock-return PnL:

| metric | value |
| --- | ---: |
| gross PnL sum | 1.054979 |
| net Pillar 6 PnL sum | 0.595249 |
| implementation drag | -0.459730 |
| gross Sharpe | 0.686 |
| net Sharpe | 0.387 |

This means any attribution report must explicitly separate gross factor model
return, transaction cost, and net strategy return.

## Next Gate

Pillar 7 can be unquarantined only after:

1. A positive daily market-cap panel covers at least 95% of the fitted universe
   per day after alignment.
2. `python scripts/run_attribution.py --market-caps <valid-panel>` completes
   without the fallback override.
3. The resulting attribution summary reports net `total_return` equal to
   `results/backtest/pnl.parquet` sum within numerical tolerance.
4. Net Sharpe and pure-alpha diagnostics are reviewed as strategy outcomes, not
   hidden behind factor or reporting bugs.
