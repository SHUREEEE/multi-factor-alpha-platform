"""Normalize external fundamentals CSV into the platform long-format contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.cleaner import apply_pit_lag


REQUIRED_COLUMNS = ["date", "ticker", "field", "value"]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    frame = normalize_fundamentals_csv(Path(args.input))
    if args.apply_lag:
        frame = apply_pit_lag(frame, lag_days=int(args.lag_days))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, compression="snappy", index=False)
    print(f"Saved normalized fundamentals to {output}")
    return 0


def normalize_fundamentals_csv(path: Path) -> pd.DataFrame:
    """Read and validate a long-format external fundamentals CSV."""
    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"fundamentals CSV missing required columns: {missing}")
    output = frame[REQUIRED_COLUMNS].copy()
    output["date"] = pd.to_datetime(output["date"], errors="coerce")
    output["ticker"] = output["ticker"].astype(str).str.strip()
    output["field"] = output["field"].astype(str).str.strip()
    output["value"] = pd.to_numeric(output["value"], errors="coerce")
    output = output.dropna(subset=["date", "ticker", "field", "value"])
    output = output[output["ticker"] != ""]
    output = output[output["field"] != ""]
    return output.sort_values(["date", "ticker", "field"]).reset_index(drop=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import external fundamentals CSV into platform long format.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--apply-lag", action="store_true")
    parser.add_argument("--lag-days", type=int, default=45)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
