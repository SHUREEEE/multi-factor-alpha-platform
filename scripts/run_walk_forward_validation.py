"""Generate time-split and walk-forward validation reports for return streams."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.pnl import compute_metrics


@dataclass(frozen=True)
class WindowResult:
    window_id: str
    split: str
    start_date: str
    end_date: str
    n_days: int
    sharpe: float
    annual_return: float
    annual_vol: float
    max_drawdown: float
    hit_rate: float


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    returns = _load_returns(Path(args.returns), args.return_column)
    if returns.empty:
        raise ValueError("return stream is empty after loading.")

    rows = build_walk_forward_rows(
        returns,
        train_years=int(args.train_years),
        test_years=int(args.test_years),
        min_train_days=int(args.min_train_days),
        min_test_days=int(args.min_test_days),
    )
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_frame = pd.DataFrame([asdict(row) for row in rows])
    rows_frame.to_csv(output_dir / "walk_forward_windows.csv", index=False)
    summary = _summary_payload(returns, rows, args)
    (output_dir / "walk_forward_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "walk_forward_report.md").write_text(_markdown_report(summary, rows_frame), encoding="utf-8")
    print(f"Saved walk-forward validation report to {output_dir}")
    return 0


def build_walk_forward_rows(
    returns: pd.Series,
    *,
    train_years: int = 5,
    test_years: int = 1,
    min_train_days: int = 252,
    min_test_days: int = 126,
) -> list[WindowResult]:
    """Build rolling train/test metric rows from a daily return stream."""
    clean = returns.dropna().astype(float).sort_index()
    if clean.empty:
        return []
    if train_years <= 0 or test_years <= 0:
        raise ValueError("train_years and test_years must be positive.")

    rows: list[WindowResult] = []
    years = sorted(clean.index.year.unique())
    for start_year in years:
        train_start = pd.Timestamp(f"{start_year}-01-01")
        train_end = pd.Timestamp(f"{start_year + train_years - 1}-12-31")
        test_start = pd.Timestamp(f"{start_year + train_years}-01-01")
        test_end = pd.Timestamp(f"{start_year + train_years + test_years - 1}-12-31")
        train = clean.loc[(clean.index >= train_start) & (clean.index <= train_end)]
        test = clean.loc[(clean.index >= test_start) & (clean.index <= test_end)]
        if len(train) < min_train_days or len(test) < min_test_days:
            continue
        window_id = f"{start_year}_{start_year + train_years - 1}_to_{start_year + train_years}_{start_year + train_years + test_years - 1}"
        rows.append(_window_result(window_id, "train", train))
        rows.append(_window_result(window_id, "test", test))
    return rows


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run walk-forward validation on a daily return stream.")
    parser.add_argument("--returns", required=True, help="Parquet/CSV return file.")
    parser.add_argument("--return-column", default=None, help="Return column. Auto-detected when omitted.")
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument("--train-years", type=int, default=5)
    parser.add_argument("--test-years", type=int, default=1)
    parser.add_argument("--min-train-days", type=int, default=252)
    parser.add_argument("--min-test-days", type=int, default=126)
    return parser.parse_args(argv)


def _load_returns(path: Path, column: str | None) -> pd.Series:
    frame = _read_frame(path)
    if isinstance(frame, pd.Series):
        series = frame
    else:
        if isinstance(frame.index, pd.MultiIndex):
            raise ValueError("walk-forward validation expects one daily portfolio return stream, not a MultiIndex panel.")
        selected = column or _detect_return_column(frame)
        series = frame[selected]
    series.index = pd.to_datetime(series.index)
    series = series.astype(float).sort_index()
    if series.name == "daily_return_bps" or (column == "daily_return_bps"):
        series = series / 10000.0
    series.name = "daily_return"
    return series


def _read_frame(path: Path) -> pd.DataFrame | pd.Series:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, index_col=0)
    raise ValueError(f"unsupported file type: {path.suffix}")


def _detect_return_column(frame: pd.DataFrame) -> str:
    for candidate in ("daily_return", "pnl", "return", "long_short_return", "daily_return_bps"):
        if candidate in frame.columns:
            return candidate
    numeric = frame.select_dtypes(include="number")
    if len(numeric.columns) == 1:
        return str(numeric.columns[0])
    raise ValueError("Could not auto-detect return column; pass --return-column.")


def _window_result(window_id: str, split: str, returns: pd.Series) -> WindowResult:
    metrics = compute_metrics(returns)
    return WindowResult(
        window_id=window_id,
        split=split,
        start_date=str(pd.Timestamp(returns.index.min()).date()),
        end_date=str(pd.Timestamp(returns.index.max()).date()),
        n_days=int(len(returns)),
        sharpe=float(metrics["sharpe"]),
        annual_return=float(metrics["annual_return"]),
        annual_vol=float(metrics["annual_vol"]),
        max_drawdown=float(metrics["max_drawdown"]),
        hit_rate=float(metrics["hit_rate"]),
    )


def _summary_payload(returns: pd.Series, rows: list[WindowResult], args: argparse.Namespace) -> dict[str, object]:
    test_rows = [row for row in rows if row.split == "test"]
    overall = _window_result("overall", "overall", returns)
    midpoint = returns.index.min() + (returns.index.max() - returns.index.min()) / 2
    first_half = returns.loc[returns.index <= midpoint]
    second_half = returns.loc[returns.index > midpoint]
    payload: dict[str, object] = {
        "input": str(args.returns),
        "return_column": args.return_column,
        "train_years": int(args.train_years),
        "test_years": int(args.test_years),
        "window_count": int(len(test_rows)),
        "overall": asdict(overall),
        "first_half": asdict(_window_result("first_half", "diagnostic", first_half)) if not first_half.empty else None,
        "second_half": asdict(_window_result("second_half", "diagnostic", second_half)) if not second_half.empty else None,
        "test_sharpe_mean": _mean([row.sharpe for row in test_rows]),
        "test_sharpe_min": min((row.sharpe for row in test_rows), default=None),
        "test_positive_sharpe_ratio": _positive_ratio([row.sharpe for row in test_rows]),
        "interpretation": _interpretation(test_rows),
    }
    return payload


def _mean(values: list[float]) -> float | None:
    return float(sum(values) / len(values)) if values else None


def _positive_ratio(values: list[float]) -> float | None:
    return float(sum(value > 0.0 for value in values) / len(values)) if values else None


def _interpretation(test_rows: list[WindowResult]) -> str:
    if not test_rows:
        return "No walk-forward windows met the minimum sample-size requirements."
    positive_ratio = _positive_ratio([row.sharpe for row in test_rows]) or 0.0
    min_sharpe = min(row.sharpe for row in test_rows)
    if positive_ratio >= 0.75 and min_sharpe > 0.0:
        return "Test windows are broadly positive, but this is still a time-split diagnostic rather than proof of live alpha."
    if positive_ratio >= 0.5:
        return "Test windows are mixed; inspect weak regimes before making stronger strategy claims."
    return "Most test windows are weak or negative; do not use full-sample metrics as the primary strategy claim."


def _markdown_report(summary: dict[str, object], rows: pd.DataFrame) -> str:
    lines = [
        "# Walk-Forward Validation",
        "",
        f"- Input: `{summary['input']}`",
        f"- Train years: {summary['train_years']}",
        f"- Test years: {summary['test_years']}",
        f"- Test windows: {summary['window_count']}",
        f"- Interpretation: {summary['interpretation']}",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| overall_sharpe | {_fmt(_nested(summary, 'overall', 'sharpe'))} |",
        f"| first_half_sharpe | {_fmt(_nested(summary, 'first_half', 'sharpe'))} |",
        f"| second_half_sharpe | {_fmt(_nested(summary, 'second_half', 'sharpe'))} |",
        f"| test_sharpe_mean | {_fmt(summary.get('test_sharpe_mean'))} |",
        f"| test_sharpe_min | {_fmt(summary.get('test_sharpe_min'))} |",
        f"| test_positive_sharpe_ratio | {_fmt(summary.get('test_positive_sharpe_ratio'))} |",
        "",
        "## Windows",
        "",
    ]
    if rows.empty:
        lines.append("No windows met the minimum sample-size requirements.")
    else:
        view = rows[["window_id", "split", "start_date", "end_date", "n_days", "sharpe", "annual_return", "max_drawdown"]].copy()
        lines.extend(_markdown_table(view))
    return "\n".join(lines) + "\n"


def _nested(summary: dict[str, object], key: str, metric: str) -> object:
    value = summary.get(key)
    if not isinstance(value, dict):
        return None
    return value.get(metric)


def _fmt(value: object) -> str:
    if value is None:
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
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
