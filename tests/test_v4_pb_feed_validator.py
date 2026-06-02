"""Tests for the standalone V4 PB borrow feed validator."""

from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd
import pytest

from scripts.validate_v4_pb_feed import validate_pb_feed_file
from src.portfolio.v4.borrow import validate_pb_borrow_feed_schema


def test_public_pb_schema_validator_normalizes_boolean_and_timestamp() -> None:
    feed = _borrow_feed(["AAA"])
    feed["htb_flag"] = ["yes"]

    normalized = validate_pb_borrow_feed_schema(feed)

    assert bool(normalized.loc[0, "htb_flag"])
    assert str(normalized.loc[0, "feed_timestamp_utc"].tzinfo) == "UTC"


def test_pb_feed_validator_passes_clean_required_symbols(tmp_path) -> None:
    feed_path = tmp_path / "borrow.csv"
    _borrow_feed(["AAA", "BBB"]).to_csv(feed_path, index=False)
    required = tmp_path / "required.csv"
    required.write_text("symbol\nAAA\n", encoding="utf-8")

    report = validate_pb_feed_file(feed_path, asof="2024-01-03", required_symbols_path=required)

    assert report["pass_fail"]
    assert report["reason"] == "PASS"
    assert report["required_symbols_count"] == 1


def test_pb_feed_validator_flags_missing_required_symbol(tmp_path) -> None:
    feed_path = tmp_path / "borrow.csv"
    _borrow_feed(["AAA"]).to_csv(feed_path, index=False)
    required = tmp_path / "required.csv"
    required.write_text("BBB\n", encoding="utf-8")

    report = validate_pb_feed_file(feed_path, asof="2024-01-03", required_symbols_path=required)

    assert not report["pass_fail"]
    assert report["missing_required_symbols"] == ["BBB"]
    assert "MISSING_REQUIRED_SYMBOLS" in report["failures"]


def test_pb_feed_validator_flags_stale_feed(tmp_path) -> None:
    feed = _borrow_feed(["AAA"])
    feed["feed_timestamp_utc"] = ["2024-01-01T20:00:00Z"]
    feed_path = tmp_path / "borrow.csv"
    feed.to_csv(feed_path, index=False)

    report = validate_pb_feed_file(feed_path, asof="2024-01-04", max_age_days=1)

    assert not report["pass_fail"]
    assert report["stale_symbols"] == ["AAA"]
    assert "STALE_FEED" in report["failures"]


def test_pb_feed_validator_flags_zero_locate_for_required_symbol(tmp_path) -> None:
    feed = _borrow_feed(["AAA"])
    feed["locate_available_shares"] = [0.0]
    feed_path = tmp_path / "borrow.csv"
    feed.to_csv(feed_path, index=False)
    required = tmp_path / "required.csv"
    required.write_text("AAA\n", encoding="utf-8")

    report = validate_pb_feed_file(feed_path, asof="2024-01-03", required_symbols_path=required)

    assert not report["pass_fail"]
    assert report["required_zero_locate_symbols"] == ["AAA"]
    assert "ZERO_LOCATES_FOR_REQUIRED_SYMBOLS" in report["failures"]


def test_pb_feed_validator_can_infer_required_shorts_from_v3_cache(tmp_path) -> None:
    feed_path = tmp_path / "borrow.csv"
    _borrow_feed(["CCC"]).to_csv(feed_path, index=False)
    v3_cache = _tiny_v3_cache(tmp_path)

    report = validate_pb_feed_file(feed_path, asof="2024-01-03", v3_cache_dir=v3_cache)

    assert not report["pass_fail"]
    assert report["missing_required_symbols"] == ["DDD"]
    assert report["required_symbols_count"] == 2


def test_pb_feed_validator_cli_writes_json_and_exit_codes(tmp_path) -> None:
    feed_path = tmp_path / "borrow.csv"
    _borrow_feed(["AAA"]).drop(columns=["htb_flag"]).to_csv(feed_path, index=False)
    output = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_v4_pb_feed.py",
            "--borrow-feed",
            str(feed_path),
            "--asof",
            "2024-01-03",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert not payload["pass_fail"]
    assert "htb_flag" in payload["reason"]


def test_pb_feed_validator_rejects_two_required_symbol_sources(tmp_path) -> None:
    feed_path = tmp_path / "borrow.csv"
    _borrow_feed(["AAA"]).to_csv(feed_path, index=False)
    required = tmp_path / "required.csv"
    required.write_text("AAA\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_v4_pb_feed.py",
            "--borrow-feed",
            str(feed_path),
            "--asof",
            "2024-01-03",
            "--required-symbols",
            str(required),
            "--v3-cache-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def _borrow_feed(symbols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-03")] * len(symbols),
            "symbol": symbols,
            "locate_available_shares": [10_000.0] * len(symbols),
            "borrow_rate_bps": [100.0] * len(symbols),
            "utilization_pct": [0.20] * len(symbols),
            "htb_flag": [False] * len(symbols),
            "feed_timestamp_utc": ["2024-01-03T20:00:00Z"] * len(symbols),
        }
    )


def _tiny_v3_cache(tmp_path):
    cache = tmp_path / "v3"
    cache.mkdir()
    dates = pd.bdate_range("2024-01-02", periods=2, name="date")
    weights = pd.DataFrame(
        {
            "AAA": [0.5, 0.6],
            "BBB": [0.5, 0.4],
            "CCC": [-0.5, -0.4],
            "DDD": [-0.5, -0.6],
        },
        index=dates,
    )
    weights.to_parquet(cache / "v3_weights.parquet")
    return cache
