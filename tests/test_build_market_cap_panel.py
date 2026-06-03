from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd


def test_build_market_cap_panel_from_long_fundamentals(tmp_path) -> None:
    prices = _prices()
    fundamentals = pd.DataFrame(
        {
            "date": ["2023-10-31", "2023-10-31", "2023-10-31", "2023-10-31"],
            "ticker": ["AAA", "AAA", "BBB", "BBB"],
            "field": ["shares_outstanding", "book_value", "shares_outstanding", "book_value"],
            "value": [100.0, 500.0, 200.0, 800.0],
        }
    )
    prices_path = tmp_path / "prices.parquet"
    fundamentals_path = tmp_path / "fundamentals.parquet"
    output_path = tmp_path / "daily_fundamentals.parquet"
    report_path = tmp_path / "contract.json"
    prices.to_parquet(prices_path)
    fundamentals.to_parquet(fundamentals_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_market_cap_panel.py",
            "--fundamentals",
            str(fundamentals_path),
            "--prices",
            str(prices_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--lag-days",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    daily = pd.read_parquet(output_path)
    assert daily.loc[(pd.Timestamp("2024-01-02"), "AAA"), "market_cap"] == 1000.0
    assert daily.loc[(pd.Timestamp("2024-01-03"), "BBB"), "market_cap"] == 4400.0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert report["market_cap_min_positive_coverage"] == 1.0


def test_build_market_cap_panel_writes_failure_report_when_shares_missing(tmp_path) -> None:
    prices = _prices()
    fundamentals = pd.DataFrame(
        {
            "date": ["2023-10-31", "2023-10-31"],
            "ticker": ["AAA", "BBB"],
            "field": ["book_value", "book_value"],
            "value": [500.0, 800.0],
        }
    )
    prices_path = tmp_path / "prices.parquet"
    fundamentals_path = tmp_path / "fundamentals.parquet"
    output_path = tmp_path / "daily_fundamentals.parquet"
    report_path = tmp_path / "contract.json"
    prices.to_parquet(prices_path)
    fundamentals.to_parquet(fundamentals_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_market_cap_panel.py",
            "--fundamentals",
            str(fundamentals_path),
            "--prices",
            str(prices_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--lag-days",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "market_cap positive coverage below contract" in result.stdout
    assert output_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["valid"] is False


def _prices() -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [pd.bdate_range("2024-01-02", periods=2), ["AAA", "BBB"]],
        names=["date", "ticker"],
    )
    return pd.DataFrame(
        {
            "adj_close": [10.0, 20.0, 11.0, 22.0],
            "return_1d": [0.0, 0.0, 0.1, 0.1],
        },
        index=index,
    )
