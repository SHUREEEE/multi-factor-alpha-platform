from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from scripts.run_walk_forward_validation import build_walk_forward_rows


def test_build_walk_forward_rows_creates_train_and_test_splits() -> None:
    dates = pd.bdate_range("2014-01-02", "2020-12-31", name="date")
    returns = pd.Series(0.001, index=dates, name="daily_return")

    rows = build_walk_forward_rows(returns, train_years=3, test_years=1, min_train_days=500, min_test_days=200)

    assert rows
    assert {row.split for row in rows} == {"train", "test"}
    first_train = rows[0]
    first_test = rows[1]
    assert first_train.start_date == "2014-01-02"
    assert first_train.end_date == "2016-12-30"
    assert first_test.start_date == "2017-01-02"
    assert first_test.end_date == "2017-12-29"


def test_walk_forward_cli_reads_v4_daily_return_bps(tmp_path) -> None:
    dates = pd.bdate_range("2014-01-02", "2020-12-31", name="date")
    frame = pd.DataFrame({"daily_return_bps": [10.0 if idx % 5 else -5.0 for idx in range(len(dates))]}, index=dates)
    returns_path = tmp_path / "v4_returns_panel.parquet"
    output_dir = tmp_path / "wf"
    frame.to_parquet(returns_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_walk_forward_validation.py",
            "--returns",
            str(returns_path),
            "--output",
            str(output_dir),
            "--train-years",
            "3",
            "--test-years",
            "1",
            "--min-train-days",
            "500",
            "--min-test-days",
            "200",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "walk_forward_windows.csv").exists()
    assert (output_dir / "walk_forward_summary.json").exists()
    assert (output_dir / "walk_forward_report.md").exists()
    summary = json.loads((output_dir / "walk_forward_summary.json").read_text(encoding="utf-8"))
    assert summary["window_count"] > 0
    assert summary["overall"]["sharpe"] > 0.0
    report = (output_dir / "walk_forward_report.md").read_text(encoding="utf-8")
    assert "Walk-Forward Validation" in report
