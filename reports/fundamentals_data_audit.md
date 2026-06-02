# Fundamentals Data Audit

## data/raw/fundamentals.parquet

Status: missing.

## data/raw/fundamentals_raw.parquet

- Shape: (0, 4)
- Index type: RangeIndex
- Index names: [None]
- Columns: ['date', 'ticker', 'field', 'value']

| column | dtype | non_null | pct_non_null |
| --- | --- | ---: | ---: |
| date | object | 0 | 0.0% |
| ticker | object | 0 | 0.0% |
| field | object | 0 | 0.0% |
| value | object | 0 | 0.0% |

Date coverage: no date values.

## data/processed/fundamentals.parquet

- Shape: (0, 5)
- Index type: Index
- Index names: [None]
- Columns: ['date', 'ticker', 'field', 'value', 'available_date']

| column | dtype | non_null | pct_non_null |
| --- | --- | ---: | ---: |
| date | datetime64[ms] | 0 | 0.0% |
| ticker | object | 0 | 0.0% |
| field | object | 0 | 0.0% |
| value | object | 0 | 0.0% |
| available_date | datetime64[ms] | 0 | 0.0% |

Date coverage: no date values.

## data/processed/daily_fundamentals.parquet

Status: missing.

## Required Field Availability

| field | available |
| --- | --- |
| market_cap | no |
| book_value | no |
| net_income | no |
| revenue | no |
| total_assets | no |
| gross_profit | no |
| operating_cashflow | no |

## Diagnosis

- No usable fundamental rows are available. Fundamental factors must be skipped until data download is repaired.
- Current raw data is not a quarterly snapshot panel and not a daily as-of panel; it is empty.
- Do not invent missing fields such as gross_profit or operating_cashflow.

