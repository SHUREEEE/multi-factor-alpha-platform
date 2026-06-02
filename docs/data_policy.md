# Data Policy

This repository is intended to be a public, interview-friendly version of the
multi-factor alpha platform. Code, configuration, tests, documentation, and
small curated JSON/CSV/Markdown evidence can live in Git. Large generated data
panels and binary research artifacts should not.

## Tracked by Default

- Source code under `src/`
- Reproducible command-line workflows under `scripts/`
- Tests under `tests/`
- Config files under `config/`
- Documentation, ADRs, and runbooks under `docs/` and `reports/`
- Small JSON/CSV summaries that are useful for review

## Not Tracked by Default

- `*.parquet`, `*.feather`, `*.h5`, `*.pkl`, and other binary panels
- Generated tearsheet images
- Python caches and pytest caches
- Temporary test-output directories such as `test_acceptance_gate*`

## Reproducibility Boundary

The current local workspace contains generated research artifacts used to
reproduce the v1 backtest and V4 acceptance-gate evidence. Those artifacts are
useful locally, but they are not all suitable for a normal public Git history.

For public release, use one of these approaches:

1. Keep only small sample fixtures in Git and document the commands needed to
   rebuild larger panels.
2. Store larger artifacts with Git LFS, DVC, or an external object store.
3. If data licensing is unclear, keep the raw data private and publish only
   synthetic fixtures plus generated summary metrics.

## Current Research Limitation

The formal Barra-style attribution path requires a positive daily market-cap
panel. The current public narrative keeps this limitation explicit: attribution
fails closed unless a valid `market_cap` panel is supplied, and equal-market-cap
fallback is reserved for smoke tests only.
