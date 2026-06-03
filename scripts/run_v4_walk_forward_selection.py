"""Run parameter-selection walk-forward validation for the V4 replay scaffold."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v4_full_sample_replay import replay_v4_full_sample
from src.backtest.pnl import compute_metrics


DEFAULT_GRID: list[dict[str, float]] = [
    {"turnover_penalty": 8.0, "no_trade_band_bps": 300.0, "lambda_beta": 10.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 0.0},
    {"turnover_penalty": 20.0, "no_trade_band_bps": 300.0, "lambda_beta": 10.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 1.0},
    {"turnover_penalty": 40.0, "no_trade_band_bps": 300.0, "lambda_beta": 5.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 1.0},
]


@dataclass(frozen=True)
class SelectionRow:
    window_id: str
    split: str
    point_id: str
    selected: bool
    start_date: str
    end_date: str
    n_days: int
    sharpe: float
    annual_return: float
    annual_vol: float
    max_drawdown: float
    avg_turnover: float
    params: dict[str, float]
    output_dir: str


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output)
    if output_dir.exists() and args.overwrite:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    grid = _load_grid(Path(args.grid)) if args.grid else DEFAULT_GRID
    rows = run_v4_walk_forward_selection(
        Path(args.v3_cache_dir),
        grid,
        output_dir,
        train_years=int(args.train_years),
        test_years=int(args.test_years),
        min_train_days=int(args.min_train_days),
        min_test_days=int(args.min_test_days),
    )
    frame = pd.DataFrame([asdict(row) for row in rows])
    frame.to_csv(output_dir / "v4_walk_forward_selection.csv", index=False)
    summary = _summary(frame, args, grid)
    (output_dir / "v4_walk_forward_selection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "v4_walk_forward_selection_report.md").write_text(_markdown(summary, frame), encoding="utf-8")
    print(f"Saved V4 walk-forward selection report to {output_dir}")
    return 0


def run_v4_walk_forward_selection(
    v3_cache_dir: Path,
    grid: list[dict[str, float]],
    output_dir: Path,
    *,
    train_years: int = 5,
    test_years: int = 1,
    min_train_days: int = 252,
    min_test_days: int = 126,
) -> list[SelectionRow]:
    """Select V4 parameters on each train window and evaluate next test window."""
    dates = _load_cache_dates(v3_cache_dir)
    rows: list[SelectionRow] = []
    for train_start, train_end, test_start, test_end in _windows(dates, train_years, test_years, min_train_days, min_test_days):
        window_id = f"{train_start.year}_{train_end.year}_to_{test_start.year}_{test_end.year}"
        candidates: list[SelectionRow] = []
        for point_idx, params in enumerate(grid):
            point_id = f"point_{point_idx:02d}"
            config_path = output_dir / window_id / point_id / "config.yaml"
            _write_config(config_path, params)
            train_dir = output_dir / window_id / point_id / "train"
            replay_v4_full_sample(v3_cache_dir, config_path, train_dir, start_date=train_start, end_date=train_end)
            candidates.append(_row(window_id, "train", point_id, False, train_dir, params))
        selected = _select_candidate(candidates)
        selected_test_dir = output_dir / window_id / selected.point_id / "test"
        selected_config = output_dir / window_id / selected.point_id / "config.yaml"
        replay_v4_full_sample(v3_cache_dir, selected_config, selected_test_dir, start_date=test_start, end_date=test_end)
        rows.extend(candidates)
        rows.append(_row(window_id, "test", selected.point_id, True, selected_test_dir, selected.params))
    return rows


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V4 parameter-selection walk-forward validation.")
    parser.add_argument("--v3-cache-dir", default="results/pillar5_artifacts")
    parser.add_argument("--output", required=True)
    parser.add_argument("--grid", default=None, help="Optional JSON grid list of V4 config dictionaries.")
    parser.add_argument("--train-years", type=int, default=5)
    parser.add_argument("--test-years", type=int, default=1)
    parser.add_argument("--min-train-days", type=int, default=252)
    parser.add_argument("--min-test-days", type=int, default=126)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def _load_grid(path: Path) -> list[dict[str, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("grid JSON must be a non-empty list of parameter dictionaries.")
    return [{str(key): float(value) for key, value in row.items()} for row in payload]


def _load_cache_dates(v3_cache_dir: Path) -> pd.DatetimeIndex:
    weights = pd.read_parquet(Path(v3_cache_dir) / "v3_weights.parquet")
    return pd.DatetimeIndex(pd.to_datetime(weights.index)).sort_values()


def _windows(
    dates: pd.DatetimeIndex,
    train_years: int,
    test_years: int,
    min_train_days: int,
    min_test_days: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    years = sorted(dates.year.unique())
    result = []
    for start_year in years:
        train_start = pd.Timestamp(f"{start_year}-01-01")
        train_end = pd.Timestamp(f"{start_year + train_years - 1}-12-31")
        test_start = pd.Timestamp(f"{start_year + train_years}-01-01")
        test_end = pd.Timestamp(f"{start_year + train_years + test_years - 1}-12-31")
        train_dates = dates[(dates >= train_start) & (dates <= train_end)]
        test_dates = dates[(dates >= test_start) & (dates <= test_end)]
        if len(train_dates) >= min_train_days and len(test_dates) >= min_test_days:
            result.append((train_dates.min(), train_dates.max(), test_dates.min(), test_dates.max()))
    return result


def _write_config(path: Path, params: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{key}: {value}" for key, value in params.items()) + "\n", encoding="utf-8")


def _row(window_id: str, split: str, point_id: str, selected: bool, replay_dir: Path, params: dict[str, float]) -> SelectionRow:
    returns_panel = pd.read_parquet(replay_dir / "v4_returns_panel.parquet")
    diagnostics = pd.read_parquet(replay_dir / "v4_diagnostics_panel.parquet")
    returns = returns_panel["daily_return_bps"].astype(float) / 10000.0
    metrics = compute_metrics(returns)
    return SelectionRow(
        window_id=window_id,
        split=split,
        point_id=point_id,
        selected=selected,
        start_date=str(pd.Timestamp(returns.index.min()).date()),
        end_date=str(pd.Timestamp(returns.index.max()).date()),
        n_days=int(len(returns)),
        sharpe=float(metrics["sharpe"]),
        annual_return=float(metrics["annual_return"]),
        annual_vol=float(metrics["annual_vol"]),
        max_drawdown=float(metrics["max_drawdown"]),
        avg_turnover=float(diagnostics["turnover"].mean()) if "turnover" in diagnostics else 0.0,
        params=dict(params),
        output_dir=str(replay_dir),
    )


def _select_candidate(candidates: list[SelectionRow]) -> SelectionRow:
    if not candidates:
        raise ValueError("No train candidates available for selection.")
    return sorted(candidates, key=lambda row: (-row.sharpe, row.avg_turnover, row.point_id))[0]


def _summary(frame: pd.DataFrame, args: argparse.Namespace, grid: list[dict[str, float]]) -> dict[str, object]:
    tests = frame[frame["split"] == "test"].copy()
    return {
        "v3_cache_dir": str(args.v3_cache_dir),
        "train_years": int(args.train_years),
        "test_years": int(args.test_years),
        "grid_size": int(len(grid)),
        "window_count": int(len(tests)),
        "test_sharpe_mean": float(tests["sharpe"].mean()) if not tests.empty else None,
        "test_sharpe_min": float(tests["sharpe"].min()) if not tests.empty else None,
        "test_positive_sharpe_ratio": float((tests["sharpe"] > 0.0).mean()) if not tests.empty else None,
        "selected_points": tests["point_id"].tolist(),
        "interpretation": _interpretation(tests),
    }


def _interpretation(tests: pd.DataFrame) -> str:
    if tests.empty:
        return "No train/test windows met the minimum sample-size requirements."
    positive_ratio = float((tests["sharpe"] > 0.0).mean())
    min_sharpe = float(tests["sharpe"].min())
    if positive_ratio >= 0.75 and min_sharpe > 0.0:
        return "Parameter-selected test windows are broadly positive, but this remains replay-scaffold evidence rather than live alpha proof."
    if positive_ratio >= 0.5:
        return "Parameter-selected test windows are mixed; inspect weak windows and avoid full-sample claims."
    return "Parameter-selected test windows are weak; do not promote v4 beyond engineering-candidate status."


def _markdown(summary: dict[str, object], frame: pd.DataFrame) -> str:
    lines = [
        "# V4 Walk-Forward Parameter Selection",
        "",
        f"- V3 cache: `{summary['v3_cache_dir']}`",
        f"- Train years: {summary['train_years']}",
        f"- Test years: {summary['test_years']}",
        f"- Grid size: {summary['grid_size']}",
        f"- Windows: {summary['window_count']}",
        f"- Interpretation: {summary['interpretation']}",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| test_sharpe_mean | {_fmt(summary['test_sharpe_mean'])} |",
        f"| test_sharpe_min | {_fmt(summary['test_sharpe_min'])} |",
        f"| test_positive_sharpe_ratio | {_fmt(summary['test_positive_sharpe_ratio'])} |",
        "",
        "## Selected Test Windows",
        "",
    ]
    tests = frame[frame["split"] == "test"].copy()
    if tests.empty:
        lines.append("No test windows available.")
    else:
        view = tests[["window_id", "point_id", "start_date", "end_date", "n_days", "sharpe", "annual_return", "max_drawdown", "avg_turnover"]]
        lines.extend(_markdown_table(view))
    return "\n".join(lines) + "\n"


def _fmt(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.4f}"


def _markdown_table(frame: pd.DataFrame) -> list[str]:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
