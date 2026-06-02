# Data Workspace

This directory is the local data workspace for research inputs and generated
factor panels.

Large binary artifacts such as Parquet panels are intentionally ignored in the
public Git version. See `docs/data_policy.md` for the full data strategy.

Expected local subdirectories include:

- `raw/`: raw price, fundamentals, and sector metadata
- `processed/`: cleaned prices, returns, and fundamentals
- `factor_data/`: generated factor panels
- `market_data/`: market proxy and related panels

The repository documents the current v1 metrics and validation evidence, but a
fresh public clone needs either rebuilt data, sample fixtures, or externally
provided artifacts before the full backtest commands can be rerun.
