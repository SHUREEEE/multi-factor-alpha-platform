# Fundamentals And Market-Cap Contract

## Purpose

Publishable Barra-style attribution requires a positive daily market-cap panel.
This document defines the minimum data contract for restoring fundamentals
without weakening the existing fail-closed behavior.

## Long Fundamental Input

Raw or processed long-format fundamentals use these columns:

| column | meaning |
| --- | --- |
| `date` | fiscal statement date or vendor-reported period date |
| `ticker` | platform ticker symbol |
| `field` | normalized field name |
| `value` | numeric fundamental value |
| `available_date` | first date the value may be used after PIT lag |

The currently supported field names include:

- `shares_outstanding`
- `book_value`
- `net_income`
- `revenue`
- `total_assets`
- `gross_profit`
- `operating_cashflow`

## Daily PIT Output

Daily fundamentals must be indexed by `MultiIndex(date, ticker)` and aligned to
the processed prices index. The required attribution column is:

| column | rule |
| --- | --- |
| `market_cap` | positive daily value computed from real shares outstanding and adjusted close |

The default construction is:

```text
market_cap = shares_outstanding * adj_close
```

`shares_outstanding` must come from a real vendor field or curated source. It
must not be invented from price, equal weights, or cross-sectional rank.

## Validation Rules

The reusable validator is `src.data.fundamentals_contract.validate_daily_fundamentals`.
It checks:

1. The input is a pandas DataFrame.
2. The index is exactly `MultiIndex(date, ticker)`.
3. The index is unique.
4. The daily fundamentals index aligns to processed prices when a price index is supplied.
5. Required columns are present.
6. `market_cap` has at least 95% positive coverage on every fitted date by default.

The data pipeline writes a machine-readable contract report to:

```text
data/processed/daily_fundamentals_contract.json
```

## Build Command

Use the standalone builder when a refreshed fundamentals file is available and
you want to validate market-cap readiness without rerunning the full data
download:

```powershell
python scripts\build_market_cap_panel.py `
  --fundamentals data\processed\fundamentals.parquet `
  --prices data\processed\prices.parquet `
  --output data\processed\daily_fundamentals.parquet `
  --report data\processed\daily_fundamentals_contract.json `
  --input-format long `
  --lag-days 45
```

If the input is already a daily PIT panel, use:

```powershell
python scripts\build_market_cap_panel.py `
  --fundamentals data\processed\daily_fundamentals.parquet `
  --prices data\processed\prices.parquet `
  --output data\processed\daily_fundamentals.parquet `
  --report data\processed\daily_fundamentals_contract.json `
  --input-format daily
```

The script writes both the output panel and the JSON report even when the
contract fails. A non-zero exit means the panel should not be used for
publishable attribution.

## Attribution Boundary

`scripts/run_attribution.py` defaults to:

```text
--market-caps data/processed/daily_fundamentals.parquet
--market-cap-contract data/processed/daily_fundamentals_contract.json
```

It still fails closed unless a usable positive `market_cap` panel is supplied.
When the contract JSON exists, it must report `"valid": true` before
publishable attribution can run. Equal-positive fallback remains a smoke-test
override only and must not be used for publishable attribution.

## Restoration Checklist

1. Acquire or curate `shares_outstanding` with dates and tickers.
2. Apply the configured PIT lag before values become available.
3. Build daily as-of fundamentals aligned to processed prices.
4. Compute `market_cap = shares_outstanding * adj_close`.
5. Run the contract validator and inspect positive coverage.
6. Rerun attribution without `--allow-equal-market-cap-fallback`.
7. Update the project brief only after the attribution path passes without fallback.
