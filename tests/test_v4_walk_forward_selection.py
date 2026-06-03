from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from scripts.run_v4_walk_forward_selection import run_v4_walk_forward_selection


def test_v4_walk_forward_selection_writes_train_and_test_rows(tmp_path) -> None:
    cache = _cache(tmp_path)
    grid = [
        {"turnover_penalty": 4.0, "no_trade_band_bps": 100.0, "lambda_beta": 10.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 0.0},
        {"turnover_penalty": 4.0, "no_trade_band_bps": 100.0, "lambda_beta": 10.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 1.0},
    ]

    rows = run_v4_walk_forward_selection(
        cache,
        grid,
        tmp_path / "out",
        train_years=2,
        test_years=1,
        min_train_days=400,
        min_test_days=200,
    )

    assert rows
    assert any(row.split == "train" for row in rows)
    assert any(row.split == "test" and row.selected for row in rows)
    test_row = next(row for row in rows if row.split == "test")
    train_rows = [row for row in rows if row.window_id == test_row.window_id and row.split == "train"]
    best_train = sorted(train_rows, key=lambda row: (-row.sharpe, row.avg_turnover, row.point_id))[0]
    assert test_row.point_id == best_train.point_id


def test_v4_walk_forward_selection_cli_outputs_report(tmp_path) -> None:
    cache = _cache(tmp_path)
    grid_path = tmp_path / "grid.json"
    grid_path.write_text(
        json.dumps(
            [
                {"turnover_penalty": 4.0, "no_trade_band_bps": 100.0, "lambda_beta": 10.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 0.0},
                {"turnover_penalty": 4.0, "no_trade_band_bps": 100.0, "lambda_beta": 10.0, "sector_net_cap": 0.10, "protected_regime_alpha_bps": 1.0},
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "wf"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_walk_forward_selection.py",
            "--v3-cache-dir",
            str(cache),
            "--grid",
            str(grid_path),
            "--output",
            str(output),
            "--train-years",
            "2",
            "--test-years",
            "1",
            "--min-train-days",
            "400",
            "--min-test-days",
            "200",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output / "v4_walk_forward_selection.csv").exists()
    assert (output / "v4_walk_forward_selection_summary.json").exists()
    assert (output / "v4_walk_forward_selection_report.md").exists()
    summary = json.loads((output / "v4_walk_forward_selection_summary.json").read_text(encoding="utf-8"))
    assert summary["window_count"] >= 1
    assert "replay-scaffold evidence" in summary["interpretation"]


def _cache(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    dates = pd.bdate_range("2019-01-02", "2022-12-30", name="date")
    weights = pd.DataFrame({"AAA": 0.5, "BBB": -0.5}, index=dates)
    returns = pd.DataFrame({"long_short_return": [0.001 if idx % 3 else -0.0005 for idx in range(len(dates))]}, index=dates)
    weights.to_parquet(cache / "v3_weights.parquet")
    returns.to_parquet(cache / "v3_daily_returns.parquet")
    return cache
