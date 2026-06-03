from __future__ import annotations

import subprocess
import sys

import pandas as pd
import pytest

from scripts.import_fundamentals_csv import normalize_fundamentals_csv


def test_normalize_fundamentals_csv_validates_required_columns(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    pd.DataFrame({"date": ["2024-01-01"], "ticker": ["AAA"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        normalize_fundamentals_csv(path)


def test_import_fundamentals_csv_cli_writes_lagged_parquet(tmp_path) -> None:
    input_path = tmp_path / "fundamentals.csv"
    output_path = tmp_path / "fundamentals.parquet"
    pd.DataFrame(
        {
            "date": ["2024-03-29", "2024-03-29"],
            "ticker": ["AAA", "AAA"],
            "field": ["shares_outstanding", "book_value"],
            "value": ["100", "500"],
        }
    ).to_csv(input_path, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/import_fundamentals_csv.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--apply-lag",
            "--lag-days",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    frame = pd.read_parquet(output_path)
    assert "available_date" in frame.columns
    assert frame.loc[0, "available_date"] > frame.loc[0, "date"]
