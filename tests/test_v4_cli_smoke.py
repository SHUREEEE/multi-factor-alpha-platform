"""Smoke tests for the D7 V4 pipeline scaffold."""

from __future__ import annotations

import subprocess
import sys

import pandas as pd


def test_v4_cli_stub_writes_cache_and_manifest(tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    output = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, "scripts/run_v4_pipeline.py", "--asof", "2024-01-03", "--config", str(config), "--output", str(output), "--inputs-stub"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (output / "2024-01-03" / "weights.parquet").exists()
    assert (output / "2024-01-03" / "manifest.json").exists()
    assert (output / "2024-01-03" / "record.json").exists()
    assert (output / "v4_run_manifest.json").exists()


def test_v4_cli_prod_loader_writes_cache_and_manifest(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    output = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_pipeline.py",
            "--asof",
            "2024-01-03",
            "--config",
            str(config),
            "--output",
            str(output),
            "--inputs-prod",
            "--v3-cache-dir",
            str(v3_cache),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output / "2024-01-03" / "weights.parquet").exists()
    manifest = (output / "v4_run_manifest.json").read_text(encoding="utf-8")
    assert '"input_mode": "prod"' in manifest


def test_v4_cli_prod_loader_accepts_borrow_feed_dry_run(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    borrow = tmp_path / "borrow.csv"
    pd.DataFrame(
        {
            "date": ["2024-01-03", "2024-01-03"],
            "symbol": ["CCC", "DDD"],
            "locate_available_shares": [10_000.0, 10_000.0],
            "borrow_rate_bps": [100.0, 100.0],
            "utilization_pct": [0.20, 0.20],
            "htb_flag": [False, False],
            "feed_timestamp_utc": ["2024-01-03T20:00:00Z", "2024-01-03T20:00:00Z"],
        }
    ).to_csv(borrow, index=False)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_pipeline.py",
            "--asof",
            "2024-01-03",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "out"),
            "--inputs-prod",
            "--v3-cache-dir",
            str(v3_cache),
            "--borrow-feed",
            str(borrow),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest = (tmp_path / "out" / "v4_run_manifest.json").read_text(encoding="utf-8")
    assert '"borrow_feed_present": true' in manifest


def test_v4_cli_auto_reconciliation_failure_exits_one(monkeypatch, tmp_path) -> None:
    from scripts import run_v4_pipeline

    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")

    def fail_reconciled(_result):
        raise RuntimeError("forced reconcile failure")

    monkeypatch.setattr(run_v4_pipeline, "assert_reconciled", fail_reconciled)

    assert run_v4_pipeline.main(["--asof", "2024-01-03", "--config", str(config), "--output", str(tmp_path / "out"), "--inputs-stub"]) == 1


def test_v4_cli_missing_config_exits_two(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_v4_pipeline.py", "--asof", "2024-01-03", "--config", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out"), "--inputs-stub"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def test_v4_cli_requires_exactly_one_input_mode(tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/run_v4_pipeline.py", "--asof", "2024-01-03", "--config", str(config), "--output", str(tmp_path / "out")],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def test_v4_cli_pit_fail_stub_exits_one(tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_pipeline.py",
            "--asof",
            "2024-01-03",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "out"),
            "--inputs-stub",
            "--pit-fail-stub",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1


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
