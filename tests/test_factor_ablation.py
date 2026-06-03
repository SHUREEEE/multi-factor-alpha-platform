from __future__ import annotations

import subprocess
import sys

import pandas as pd

from scripts.run_factor_ablation import run_leave_one_out_ablation
from src.combination.baseline import FactorSpec


def test_leave_one_out_ablation_returns_full_and_drop_rows() -> None:
    factors, prices, specs = _fixtures()

    rows = run_leave_one_out_ablation(factors, prices, specs, n_quantiles=2)

    assert [row["scenario"] for row in rows] == ["full", "drop_f1", "drop_f2", "drop_f3"]
    assert rows[0]["delta_sharpe_vs_full"] == 0.0
    assert all("annualized_sharpe" in row for row in rows)


def test_factor_ablation_cli_writes_outputs(tmp_path) -> None:
    factors, prices, _ = _fixtures()
    factors_path = tmp_path / "factors.parquet"
    prices_path = tmp_path / "prices.parquet"
    config_path = tmp_path / "pillar4.yaml"
    output_dir = tmp_path / "ablation"
    factors.to_parquet(factors_path)
    prices.to_parquet(prices_path)
    config_path.write_text(
        f"""
source_factor_file: {factors_path.as_posix()}
price_file: {prices_path.as_posix()}
research_summary_file: unused.csv
include_optional_default: true
candidates:
  - alias: f1
    source_name: f1
    direction: 1
    optional: false
  - alias: f2
    source_name: f2
    direction: 1
    optional: false
  - alias: f3
    source_name: f3
    direction: 1
    optional: false
portfolios:
  baseline_4f_equal_weight:
    factors: [f1, f2, f3]
    weighting: equal
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_factor_ablation.py",
            "--config",
            str(config_path),
            "--output",
            str(output_dir),
            "--n-quantiles",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "factor_ablation.csv").exists()
    assert (output_dir / "factor_ablation_summary.json").exists()
    assert (output_dir / "factor_ablation_report.md").exists()


def _fixtures() -> tuple[pd.DataFrame, pd.DataFrame, list[FactorSpec]]:
    dates = pd.bdate_range("2024-01-02", periods=40, name="date")
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    values = []
    price_rows = []
    for date_idx, date in enumerate(dates):
        for ticker_idx, ticker in enumerate(tickers):
            base = ticker_idx - 1.5
            values.append({"f1": base, "f2": -base, "f3": base * (1 if date_idx % 2 == 0 else -1)})
            return_1d = 0.001 * base if date_idx > 0 else 0.0
            price = 100.0 * (1.0 + return_1d) ** date_idx
            price_rows.append({"adj_close": price, "return_1d": return_1d, "volume": 1000.0})
    factors = pd.DataFrame(values, index=index)
    prices_frame = pd.DataFrame(price_rows, index=index)
    specs = [FactorSpec("f1", 1), FactorSpec("f2", 1), FactorSpec("f3", 1)]
    return factors, prices_frame, specs
