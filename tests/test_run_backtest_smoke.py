from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd


def test_run_backtest_smoke(tmp_path) -> None:
    dates = pd.bdate_range("2024-01-02", periods=12)
    symbols = ["A", "B", "C"]
    weights = pd.DataFrame(
        {
            "A": [0.0, 0.5, 0.5, 0.0, -0.5, -0.5, 0.0, 0.25, 0.25, 0.0, 0.0, 0.0],
            "B": [0.0, -0.5, -0.5, 0.0, 0.5, 0.5, 0.0, -0.25, -0.25, 0.0, 0.0, 0.0],
            "C": [0.0] * 12,
        },
        index=dates,
    )
    returns = pd.DataFrame(np.full((12, 3), 0.001), index=dates, columns=symbols)
    prices = 100.0 * (1.0 + returns).cumprod()
    weights_path = tmp_path / "weights.parquet"
    prices_path = tmp_path / "prices.parquet"
    output_dir = tmp_path / "backtest"
    weights.to_parquet(weights_path)
    prices.to_parquet(prices_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_backtest.py",
            "--weights",
            str(weights_path),
            "--prices",
            str(prices_path),
            "--output",
            str(output_dir),
            "--sanity",
        ],
        check=True,
        cwd=".",
        capture_output=True,
        text=True,
    )

    assert "sharpe:" in completed.stdout
    for name in ["pnl.parquet", "nav.parquet", "trades.parquet", "metrics.json", "run_manifest.json", "sanity_report.json"]:
        assert (output_dir / name).exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "sharpe" in metrics
    assert "turnover_annual_x" in metrics
    assert "turnover_annual" not in metrics
