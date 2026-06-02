"""Run the Pillar 6 vectorized backtest from saved weights and adj_close prices."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import VectorizedBacktester
from src.backtest.pnl import compute_metrics
from src.backtest.sanity import perfect_foresight_sharpe, random_alpha_sharpe, reverse_strategy_sharpe

DEFAULT_COST_CONFIG = {"linear_bps": 5.0, "impact_coefficient": 0.1, "use_sqrt_impact": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a vectorized T+1 backtest.")
    parser.add_argument("--weights", required=True, help="Path to target weights parquet/csv.")
    parser.add_argument("--prices", required=True, help="Path to price parquet/csv containing adj_close or a wide adj_close panel.")
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument("--sanity", action="store_true", help="Run backtest sanity checks.")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    prices_path = Path(args.prices)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    weights = _load_weights(weights_path)
    prices = _load_prices(prices_path)
    price_panel = _price_panel(prices)
    weights, price_panel = weights.align(price_panel, join="inner", axis=0)
    weights, price_panel = weights.align(price_panel, join="inner", axis=1)

    result = VectorizedBacktester(weights, price_panel, DEFAULT_COST_CONFIG).run()
    metrics = compute_metrics(result.pnl)
    metrics["turnover_annual_x"] = _annual_turnover(result.trades)
    metrics.pop("turnover_annual", None)
    metrics["final_nav"] = float(result.nav.iloc[-1]) if not result.nav.empty else 1.0

    result.pnl.to_frame("pnl").to_parquet(output_dir / "pnl.parquet")
    result.nav.to_frame("nav").to_parquet(output_dir / "nav.parquet")
    result.trades.to_parquet(output_dir / "trades.parquet", index=False)
    _write_json(output_dir / "metrics.json", metrics)
    _write_json(
        output_dir / "run_manifest.json",
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "weights_path": str(weights_path),
            "prices_path": str(prices_path),
            "weights_sha256": _sha256(weights_path),
            "prices_sha256": _sha256(prices_path),
            "cost_config": DEFAULT_COST_CONFIG,
            "n_dates": int(len(weights.index)),
            "n_symbols": int(len(weights.columns)),
        },
    )

    if args.sanity:
        returns = price_panel.pct_change(fill_method=None).fillna(0.0)
        sanity_report = {
            "random_alpha": random_alpha_sharpe(price_panel, returns),
            "perfect_foresight": perfect_foresight_sharpe(price_panel, returns),
            "reverse_strategy": reverse_strategy_sharpe(price_panel, returns, weights),
        }
        _write_json(output_dir / "sanity_report.json", sanity_report)

    _print_metrics(metrics)
    return 0


def _load_weights(path: Path) -> pd.DataFrame:
    frame = _read_frame(path)
    if isinstance(frame.index, pd.MultiIndex):
        value_column = "weight" if "weight" in frame.columns else frame.columns[0]
        frame = frame[value_column].unstack("ticker")
    elif {"date", "ticker"}.issubset(frame.columns):
        value_column = "weight" if "weight" in frame.columns else [c for c in frame.columns if c not in {"date", "ticker"}][0]
        frame = frame.pivot(index="date", columns="ticker", values=value_column)
    frame.index = pd.to_datetime(frame.index)
    return frame.astype(float).sort_index().sort_index(axis=1)


def _load_prices(path: Path) -> pd.DataFrame:
    return _read_frame(path)


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"unsupported file type: {path.suffix}")


def _price_panel(prices: pd.DataFrame) -> pd.DataFrame:
    if isinstance(prices.index, pd.MultiIndex):
        if "adj_close" not in prices.columns:
            raise ValueError("prices must contain adj_close when supplied in long form.")
        panel = prices["adj_close"].unstack("ticker")
    elif "adj_close" in prices.columns and {"date", "ticker"}.issubset(prices.columns):
        panel = prices.pivot(index="date", columns="ticker", values="adj_close")
    else:
        panel = prices.copy()
    panel.index = pd.to_datetime(panel.index)
    return panel.astype(float).sort_index().sort_index(axis=1)


def _annual_turnover(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    return float(trades.groupby("date")["dw"].apply(lambda values: values.abs().sum()).mean() * 252)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _print_metrics(metrics: dict) -> None:
    for key in sorted(metrics):
        value = metrics[key]
        print(f"{key}: {value:.6f}" if isinstance(value, float) else f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
