"""Create a per-factor coverage report for Pillar 2 outputs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.factor_coverage import summarize_factor_coverage  # noqa: E402

FACTOR_PATH = PROJECT_ROOT / "data/factor_data/factors.parquet"
OUTPUT_PATH = PROJECT_ROOT / "results/factor_coverage.csv"


def main() -> None:
    """Load factors, summarize coverage, and save a CSV report."""
    factors = _load_factors(FACTOR_PATH)
    coverage = summarize_factor_coverage(factors)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(OUTPUT_PATH, index=False)
    logger.info("Saved factor coverage report to {}", OUTPUT_PATH.as_posix())
    logger.info("Factor coverage:\n{}", coverage.to_string(index=False))


def _load_factors(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing factors file: {path.as_posix()}")
    factors = pd.read_parquet(path)
    if not isinstance(factors.index, pd.MultiIndex):
        raise ValueError("factors.parquet must use MultiIndex(date, ticker).")
    factors.index = factors.index.set_names(["date", "ticker"])
    return factors.sort_index()


if __name__ == "__main__":
    main()
