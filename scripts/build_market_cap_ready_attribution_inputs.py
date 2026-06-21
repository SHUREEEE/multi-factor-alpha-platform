"""Build attribution inputs restricted to a market-cap-ready universe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.pnl import compute_pnl  # noqa: E402
from src.data.fundamentals_contract import validate_daily_fundamentals  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prices = pd.read_parquet(args.prices).sort_index()
    weights = pd.read_parquet(args.weights).sort_index()
    factors = pd.read_parquet(args.factors).sort_index()
    daily_fundamentals = pd.read_parquet(args.daily_fundamentals).sort_index()
    eligible = select_market_cap_ready_tickers(daily_fundamentals, weights.columns, float(args.min_ticker_coverage))
    if len(eligible) < int(args.min_tickers):
        raise ValueError(f"Only {len(eligible)} tickers meet market-cap coverage; required {args.min_tickers}.")
    filtered_prices = prices.loc[(slice(None), eligible), :].sort_index()
    filtered_fundamentals = daily_fundamentals.loc[filtered_prices.index].sort_index()
    report = validate_daily_fundamentals(filtered_fundamentals, price_index=filtered_prices.index, min_market_cap_coverage=float(args.min_daily_coverage))
    _write_contract(report.to_dict(), output_dir / "daily_fundamentals_contract.json")
    if not report.valid:
        report.raise_for_errors()
    filtered_weights = weights.reindex(columns=eligible).fillna(0.0)
    filtered_weights = filtered_weights.div(filtered_weights.abs().sum(axis=1).replace(0.0, pd.NA), axis=0).fillna(0.0)
    returns = filtered_prices["return_1d"].unstack("ticker").reindex(index=filtered_weights.index, columns=filtered_weights.columns)
    pnl = compute_pnl(filtered_weights, returns)
    nav = (1.0 + pnl.fillna(0.0)).cumprod()
    filtered_factors = factors.loc[(slice(None), eligible), :].sort_index()
    backtest_dir = output_dir / "backtest"
    backtest_dir.mkdir(parents=True, exist_ok=True)
    filtered_prices.to_parquet(output_dir / "prices.parquet", compression="snappy")
    filtered_fundamentals.to_parquet(output_dir / "daily_fundamentals.parquet", compression="snappy")
    filtered_weights.to_parquet(output_dir / "weights.parquet", compression="snappy")
    filtered_factors.to_parquet(output_dir / "factors.parquet", compression="snappy")
    pnl.to_frame("pnl").to_parquet(backtest_dir / "pnl.parquet", compression="snappy")
    nav.to_frame("nav").to_parquet(backtest_dir / "nav.parquet", compression="snappy")
    manifest = {
        "source_weights": str(args.weights),
        "source_prices": str(args.prices),
        "source_factors": str(args.factors),
        "source_daily_fundamentals": str(args.daily_fundamentals),
        "eligible_ticker_count": len(eligible),
        "dropped_ticker_count": int(len(weights.columns) - len(eligible)),
        "min_ticker_coverage": float(args.min_ticker_coverage),
        "min_daily_coverage": float(args.min_daily_coverage),
        "contract": report.to_dict(),
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Built market-cap-ready attribution inputs for {len(eligible)} tickers in {output_dir}")
    print(f"Contract min positive coverage: {report.market_cap_min_positive_coverage:.2%}")
    return 0


def select_market_cap_ready_tickers(daily_fundamentals: pd.DataFrame, candidate_tickers: pd.Index, min_ticker_coverage: float) -> list[str]:
    if "market_cap" not in daily_fundamentals.columns:
        raise ValueError("daily_fundamentals must contain market_cap.")
    market_cap = daily_fundamentals["market_cap"].unstack("ticker").reindex(columns=candidate_tickers)
    coverage = market_cap.where(market_cap > 0.0).notna().mean(axis=0)
    return sorted(coverage[coverage >= min_ticker_coverage].index.astype(str).tolist())


def _write_contract(report: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build market-cap-ready attribution input subset.")
    parser.add_argument("--weights", default="results/pillar5_artifacts/v3_weights.parquet")
    parser.add_argument("--prices", default="data/processed/prices.parquet")
    parser.add_argument("--factors", default="data/factor_data/factors.parquet")
    parser.add_argument("--daily-fundamentals", default="data/processed/daily_fundamentals.parquet")
    parser.add_argument("--output-dir", default="results/market_cap_ready_attribution")
    parser.add_argument("--min-ticker-coverage", type=float, default=0.99)
    parser.add_argument("--min-daily-coverage", type=float, default=0.95)
    parser.add_argument("--min-tickers", type=int, default=300)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
