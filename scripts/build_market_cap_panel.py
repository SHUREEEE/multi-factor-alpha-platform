"""Build and validate a daily market-cap panel from PIT fundamentals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.cleaner import make_daily_fundamentals
from src.data.fundamentals_contract import validate_daily_fundamentals


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    prices = _load_prices(Path(args.prices))
    fundamentals = pd.read_parquet(args.fundamentals)

    if args.input_format == "daily":
        daily = _normalize_daily_fundamentals(fundamentals)
    else:
        daily = make_daily_fundamentals(fundamentals, prices, lag_days=int(args.lag_days))

    report = validate_daily_fundamentals(
        daily,
        price_index=prices.index,
        min_market_cap_coverage=float(args.min_market_cap_coverage),
    )
    _write_outputs(daily, report.to_dict(), Path(args.output), Path(args.report))

    if not report.valid:
        print("Market-cap panel contract failed:")
        for violation in report.violations:
            print(f"- {violation}")
        return 1

    print(
        "Market-cap panel contract passed: "
        f"{report.row_count} rows, {report.ticker_count} tickers, "
        f"min positive coverage={report.market_cap_min_positive_coverage:.2%}."
    )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and validate daily market-cap fundamentals.")
    parser.add_argument("--fundamentals", required=True, help="Input fundamentals parquet.")
    parser.add_argument("--prices", required=True, help="Processed prices parquet with MultiIndex(date, ticker).")
    parser.add_argument("--output", required=True, help="Output daily fundamentals parquet.")
    parser.add_argument("--report", required=True, help="Output JSON contract report.")
    parser.add_argument("--input-format", choices=["long", "daily"], default="long")
    parser.add_argument("--lag-days", type=int, default=45)
    parser.add_argument("--min-market-cap-coverage", type=float, default=0.95)
    return parser.parse_args(argv)


def _load_prices(path: Path) -> pd.DataFrame:
    prices = pd.read_parquet(path)
    if not isinstance(prices.index, pd.MultiIndex):
        if {"date", "ticker"}.issubset(prices.columns):
            prices = prices.set_index(["date", "ticker"])
        else:
            raise ValueError("prices must use MultiIndex(date, ticker) or contain date and ticker columns.")
    prices.index = prices.index.set_names(["date", "ticker"])
    return prices.sort_index()


def _normalize_daily_fundamentals(frame: pd.DataFrame) -> pd.DataFrame:
    daily = frame.copy()
    if isinstance(daily.index, pd.MultiIndex):
        daily.index = daily.index.set_names(["date", "ticker"])
        return daily.sort_index()
    if {"date", "ticker"}.issubset(daily.columns):
        daily["date"] = pd.to_datetime(daily["date"])
        return daily.set_index(["date", "ticker"]).sort_index()
    raise ValueError("daily fundamentals must use MultiIndex(date, ticker) or contain date and ticker columns.")


def _write_outputs(daily: pd.DataFrame, report: dict[str, object], output_path: Path, report_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(output_path, compression="snappy", index=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
