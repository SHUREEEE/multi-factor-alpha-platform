# Artifact Commit Policy

## Purpose

The repository should stay reviewable as a portfolio project. Code, configs,
tests, Markdown reports, and small summary artifacts belong in Git. Large
reproducible panels should be regenerated from documented commands rather than
committed directly.

## Commit By Default

- Source code under `src/` and `scripts/`.
- Tests under `tests/`.
- Config files under `config/`.
- Markdown reports under `reports/` and `docs/`.
- Small JSON manifests and contract reports that document reproducibility,
  coverage, and data boundaries.
- Small CSV summaries that are useful for code review and interviews.

## Do Not Commit By Default

- Large Parquet data panels, including price panels, factor panels, daily
  fundamentals panels, and attribution input panels.
- Generated PNG tearsheets and other binary visual outputs.
- Temporary smoke-test outputs under `tmp/`.
- Vendor downloads that can be reproduced by documented scripts.

## Current v2 Evidence Policy

The v2 institutional validation pack may commit:

- `reports/institutional_validation.md`
- `reports/market_cap_attribution_restoration.md`
- `results/institutional_validation/*.csv`
- `results/institutional_validation/*.json`
- `results/market_cap_ready_attribution/**/*.json`

The following should remain generated artifacts:

- `data/raw/sec_shares_outstanding.parquet`
- `data/processed/daily_fundamentals.parquet`
- `results/market_cap_ready_attribution/**/*.parquet`
- `results/market_cap_ready_attribution/**/*.png`

## Reproduction Commands

```powershell
python scripts\run_institutional_validation.py --config config\institutional_validation.yaml
python scripts\download_sec_shares_outstanding.py --tickers data\processed\prices.parquet
python scripts\build_market_cap_panel.py --fundamentals data\raw\sec_shares_outstanding.parquet --prices data\processed\prices.parquet --output data\processed\daily_fundamentals.parquet --report data\processed\daily_fundamentals_contract.json --input-format long --lag-days 45
python scripts\build_market_cap_ready_attribution_inputs.py
python scripts\run_attribution.py --backtest-dir results\market_cap_ready_attribution\backtest --weights results\market_cap_ready_attribution\weights.parquet --factor-data results\market_cap_ready_attribution\factors.parquet --returns results\market_cap_ready_attribution\prices.parquet --market-caps results\market_cap_ready_attribution\daily_fundamentals.parquet --market-cap-contract results\market_cap_ready_attribution\daily_fundamentals_contract.json --output results\market_cap_ready_attribution\strategy_reports
```
