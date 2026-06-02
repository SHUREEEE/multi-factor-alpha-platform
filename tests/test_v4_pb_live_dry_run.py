"""Smoke tests for the PB-gated V4 prod dry-run wrapper."""

from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd


def test_pb_live_dry_run_validates_feed_then_runs_pipeline(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    borrow = tmp_path / "borrow.csv"
    _borrow_feed(["CCC", "DDD"]).to_csv(borrow, index=False)
    output = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_pb_live_dry_run.py",
            "--asof",
            "2024-01-03",
            "--config",
            str(config),
            "--output",
            str(output),
            "--borrow-feed",
            str(borrow),
            "--v3-cache-dir",
            str(v3_cache),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    validation = json.loads((output / "pb_borrow_validation.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "v4_pb_live_dry_run_manifest.json").read_text(encoding="utf-8"))
    assert validation["pass_fail"]
    assert manifest["status"] == "PASS"
    assert manifest["synthetic_borrow_used"] is False
    assert (output / "2024-01-03" / "weights.parquet").exists()


def test_pb_live_dry_run_stops_before_pipeline_when_feed_fails(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    borrow = tmp_path / "borrow.csv"
    _borrow_feed(["CCC"]).to_csv(borrow, index=False)
    output = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_pb_live_dry_run.py",
            "--asof",
            "2024-01-03",
            "--config",
            str(config),
            "--output",
            str(output),
            "--borrow-feed",
            str(borrow),
            "--v3-cache-dir",
            str(v3_cache),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    validation = json.loads((output / "pb_borrow_validation.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "v4_pb_live_dry_run_manifest.json").read_text(encoding="utf-8"))
    assert validation["missing_required_symbols"] == ["DDD"]
    assert manifest["status"] == "PB_FEED_VALIDATION_FAIL"
    assert not (output / "2024-01-03" / "weights.parquet").exists()


def test_pb_live_dry_run_missing_config_exits_two(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_pb_live_dry_run.py",
            "--asof",
            "2024-01-03",
            "--config",
            str(tmp_path / "missing.yaml"),
            "--output",
            str(tmp_path / "out"),
            "--borrow-feed",
            str(tmp_path / "borrow.csv"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def _borrow_feed(symbols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-03"] * len(symbols),
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
    sectors = pd.DataFrame({"symbol": ["AAA", "BBB", "CCC", "DDD"], "sector": ["Tech", "Health", "Tech", "Health"]})
    weights.to_parquet(cache / "v3_weights.parquet")
    sectors.to_csv(cache / "v3_sector_map.csv", index=False)
    return cache
