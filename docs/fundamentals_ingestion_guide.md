# Fundamentals Ingestion Guide

## Purpose

This guide describes how to bring externally sourced fundamentals into the
platform without weakening point-in-time or attribution controls.

The current public workspace does not include a licensed daily market-cap
panel. The code path is ready for one, but publishable Barra-style attribution
remains blocked until real `shares_outstanding` coverage is supplied and the
daily fundamentals contract passes.

## Input Template

External fundamentals should be provided as a long-format CSV:

| column | example | notes |
| --- | --- | --- |
| `date` | `2024-03-29` | fiscal statement date or vendor period date |
| `ticker` | `AAPL` | platform ticker symbol |
| `field` | `shares_outstanding` | normalized field name |
| `value` | `15500000000` | numeric value |

Minimum field for attribution:

- `shares_outstanding`

Useful fields for fundamental factors:

- `book_value`
- `net_income`
- `revenue`
- `total_assets`
- `gross_profit`
- `operating_cashflow`

## Import Command

```powershell
python scripts\import_fundamentals_csv.py `
  --input data\raw\external_fundamentals.csv `
  --output data\processed\fundamentals.parquet `
  --apply-lag `
  --lag-days 45
```

This writes a normalized long-format Parquet file with `available_date`.

## Build Daily Market Cap

```powershell
python scripts\build_market_cap_panel.py `
  --fundamentals data\processed\fundamentals.parquet `
  --prices data\processed\prices.parquet `
  --output data\processed\daily_fundamentals.parquet `
  --report data\processed\daily_fundamentals_contract.json `
  --input-format long `
  --lag-days 45
```

The generated `daily_fundamentals_contract.json` must report `"valid": true`
before publishable attribution can run.

## Attribution Command

```powershell
python scripts\run_attribution.py
```

`run_attribution.py` defaults to the daily fundamentals panel and contract
report. It fails closed if the panel is missing, if market-cap coverage is too
low, or if the contract report is invalid.

## Non-Negotiable Boundaries

- Do not invent `shares_outstanding`.
- Do not use equal-cap fallback for publishable attribution.
- Do not use synthetic market caps from rank, price alone, or uniform constants.
- Do not treat a passing import as sufficient; the daily contract must pass
  after alignment to processed prices.
