"""Validate a V4 PB borrow feed before pipeline dry-run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.v4.borrow import BorrowFeedSchemaError, validate_pb_borrow_feed_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a V4 PB borrow feed.")
    parser.add_argument("--borrow-feed", required=True, type=Path)
    parser.add_argument("--asof", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--required-symbols", type=Path, help="Optional text/CSV file with one required symbol per row.")
    parser.add_argument("--v3-cache-dir", type=Path, help="Optional V3 cache dir used to infer active shorts for --asof.")
    parser.add_argument("--max-age-days", type=int, default=1)
    args = parser.parse_args(argv)
    if args.max_age_days < 0:
        parser.error("--max-age-days must be non-negative")
    if args.required_symbols is not None and args.v3_cache_dir is not None:
        parser.error("choose at most one of --required-symbols or --v3-cache-dir")

    try:
        report = validate_pb_feed_file(
            args.borrow_feed,
            asof=args.asof,
            required_symbols_path=args.required_symbols,
            v3_cache_dir=args.v3_cache_dir,
            max_age_days=args.max_age_days,
        )
    except (BorrowFeedSchemaError, RuntimeError, ValueError) as exc:
        report = {
            "pass_fail": False,
            "reason": str(exc),
            "borrow_feed": str(args.borrow_feed),
            "asof": args.asof,
        }

    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if bool(report.get("pass_fail")) else 1


def validate_pb_feed_file(
    borrow_feed_path: Path,
    *,
    asof: str,
    required_symbols_path: Path | None = None,
    v3_cache_dir: Path | None = None,
    max_age_days: int = 1,
) -> dict[str, object]:
    """Return a JSON-serializable validation report for one PB feed file."""
    feed_path = Path(borrow_feed_path)
    if not feed_path.exists():
        raise RuntimeError(f"missing PB borrow feed: {feed_path}")
    feed = validate_pb_borrow_feed_schema(_read_table(feed_path))
    required_symbols = _load_required_symbols(required_symbols_path, v3_cache_dir, asof)
    feed_by_symbol = feed.drop_duplicates("symbol", keep="last").set_index("symbol")
    asof_ts = pd.Timestamp(asof).normalize()

    missing_required = sorted(set(required_symbols) - set(feed_by_symbol.index.astype(str)))
    stale_symbols = _stale_symbols(feed_by_symbol, asof_ts, max_age_days)
    zero_locate_symbols = sorted(
        feed_by_symbol.index[feed_by_symbol["locate_available_shares"].astype(float) <= 0.0].astype(str).tolist()
    )
    required_zero_locates = sorted(set(required_symbols).intersection(zero_locate_symbols))
    duplicate_symbols = sorted(feed["symbol"][feed["symbol"].duplicated()].astype(str).unique().tolist())

    failures: list[str] = []
    if missing_required:
        failures.append("MISSING_REQUIRED_SYMBOLS")
    if stale_symbols:
        failures.append("STALE_FEED")
    if required_zero_locates:
        failures.append("ZERO_LOCATES_FOR_REQUIRED_SYMBOLS")

    return {
        "pass_fail": not failures,
        "failures": failures,
        "borrow_feed": str(feed_path),
        "asof": str(asof_ts.date()),
        "rows": int(len(feed)),
        "symbols_count": int(feed["symbol"].nunique()),
        "required_symbols_count": int(len(required_symbols)),
        "missing_required_symbols": missing_required,
        "stale_symbols": stale_symbols,
        "zero_locate_symbols": zero_locate_symbols,
        "required_zero_locate_symbols": required_zero_locates,
        "duplicate_symbols": duplicate_symbols,
        "max_age_days": int(max_age_days),
        "feed_timestamp_min_utc": _iso_or_none(feed["feed_timestamp_utc"].min()),
        "feed_timestamp_max_utc": _iso_or_none(feed["feed_timestamp_utc"].max()),
        "reason": "PASS" if not failures else ",".join(failures),
    }


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _load_required_symbols(required_symbols_path: Path | None, v3_cache_dir: Path | None, asof: str) -> list[str]:
    if required_symbols_path is not None:
        if not required_symbols_path.exists():
            raise RuntimeError(f"missing required symbols file: {required_symbols_path}")
        frame = pd.read_csv(required_symbols_path, header=None)
        values = frame.iloc[:, 0].dropna().astype(str).str.strip()
        values = values[(values != "") & (values.str.lower() != "symbol")]
        return sorted(values.unique().tolist())
    if v3_cache_dir is None:
        return []
    weights_path = Path(v3_cache_dir) / "v3_weights.parquet"
    if not weights_path.exists():
        raise RuntimeError(f"missing V3 weights: {weights_path}")
    weights = pd.read_parquet(weights_path).fillna(0.0).astype(float)
    asof_ts = pd.Timestamp(asof)
    if asof_ts not in weights.index:
        raise RuntimeError(f"asof {asof} not found in V3 weights")
    row = weights.loc[asof_ts]
    return sorted(row[row < 0.0].index.astype(str).tolist())


def _stale_symbols(feed_by_symbol: pd.DataFrame, asof_ts: pd.Timestamp, max_age_days: int) -> list[str]:
    stale = []
    for symbol, timestamp in feed_by_symbol["feed_timestamp_utc"].items():
        feed_date = pd.Timestamp(timestamp).tz_convert(None).normalize()
        age = len(pd.bdate_range(feed_date, asof_ts)) - 1 if feed_date <= asof_ts else 0
        if age > max_age_days:
            stale.append(str(symbol))
    return sorted(stale)


def _iso_or_none(value: object) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
