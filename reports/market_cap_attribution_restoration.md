# Market-Cap Attribution Restoration

## Summary

This project now has a real-market-cap attribution path that does not use the
equal-market-cap smoke-test fallback. SEC companyfacts shares outstanding were
downloaded, converted into daily point-in-time `market_cap`, and then filtered
into a market-cap-ready attribution universe.

The full 516-name research universe still fails the 95% daily positive
market-cap coverage contract, with minimum daily coverage of 80.62%. That
failure remains recorded and is not bypassed. The publishable attribution path
uses a 416-name market-cap-ready subset with a passing contract.

## Data Path

1. Download SEC shares outstanding:

```powershell
python scripts\download_sec_shares_outstanding.py --tickers data\processed\prices.parquet
```

2. Build daily market cap:

```powershell
python scripts\build_market_cap_panel.py --fundamentals data\raw\sec_shares_outstanding.parquet --prices data\processed\prices.parquet --output data\processed\daily_fundamentals.parquet --report data\processed\daily_fundamentals_contract.json --input-format long --lag-days 45
```

3. Build market-cap-ready attribution inputs:

```powershell
python scripts\build_market_cap_ready_attribution_inputs.py
```

4. Run attribution without fallback:

```powershell
python scripts\run_attribution.py --backtest-dir results\market_cap_ready_attribution\backtest --weights results\market_cap_ready_attribution\weights.parquet --factor-data results\market_cap_ready_attribution\factors.parquet --returns results\market_cap_ready_attribution\prices.parquet --market-caps results\market_cap_ready_attribution\daily_fundamentals.parquet --market-cap-contract results\market_cap_ready_attribution\daily_fundamentals_contract.json --output results\market_cap_ready_attribution\strategy_reports
```

## Contract Evidence

| universe | tickers | start | end | min positive coverage | valid |
| --- | ---: | --- | --- | ---: | --- |
| Full research universe | 516 | 2014-01-02 | 2024-12-31 | 80.62% | false |
| Market-cap-ready attribution subset | 416 | 2014-01-02 | 2024-12-31 | 100.00% | true |

The subset contract is stored at
`results/market_cap_ready_attribution/daily_fundamentals_contract.json`.

## Attribution Evidence

The attribution run manifest records:

- `market_cap_source`: `daily fundamentals market_cap column`
- `market_cap_contract`: `results\market_cap_ready_attribution\daily_fundamentals_contract.json`
- `n_stocks`: 416
- Equal-market-cap fallback: not used

Summary output:

| metric | value |
| --- | ---: |
| total_return | 0.4752 |
| factor_contribution_total | 0.4024 |
| pure_alpha_total | 0.0728 |
| pure_alpha_pct_of_total | 15.31% |
| factor_risk_pct | 72.75% |
| idiosyncratic_risk_pct | 27.25% |

Primary artifacts:

- `results/market_cap_ready_attribution/strategy_reports/attribution_summary.json`
- `results/market_cap_ready_attribution/strategy_reports/factor_returns.parquet`
- `results/market_cap_ready_attribution/strategy_reports/final_tearsheet.png`
- `results/market_cap_ready_attribution/strategy_reports/run_manifest.json`

## Interpretation Boundary

This restores publishable Barra-style attribution for the market-cap-ready
subset. It does not claim that the full 516-name universe has complete
fundamentals coverage. The full-universe fail-closed behavior remains correct
until a more complete historical fundamentals vendor is added.
