"""Tests for the V4 launch evidence bundle wrapper."""

from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd


def test_launch_evidence_bundle_blocks_when_readiness_still_partial(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    borrow = tmp_path / "borrow.csv"
    _borrow_feed(["CCC", "DDD"]).to_csv(borrow, index=False)
    gates = _gates(tmp_path, ["PASS"])
    readiness = _readiness(tmp_path, pb_status="PARTIAL")
    output = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_v4_launch_evidence_bundle.py",
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
            "--gates",
            str(gates),
            "--readiness",
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    bundle = json.loads((output / "v4_launch_evidence_bundle.json").read_text(encoding="utf-8"))
    go_no_go = json.loads((output / "v4_launch_go_no_go.json").read_text(encoding="utf-8"))
    assert bundle["status"] == "BLOCKED"
    assert bundle["pb_dry_run_exit_code"] == 0
    assert bundle["go_no_go_exit_code"] == 1
    assert go_no_go["p0_not_ready"] == ["PB borrow real feed"]


def test_launch_evidence_bundle_ready_when_all_subchecks_pass(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    borrow = tmp_path / "borrow.csv"
    _borrow_feed(["CCC", "DDD"]).to_csv(borrow, index=False)
    gates = _gates(tmp_path, ["PASS"])
    readiness = _readiness(tmp_path, pb_status="READY")
    output = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_v4_launch_evidence_bundle.py",
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
            "--gates",
            str(gates),
            "--readiness",
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    bundle = json.loads((output / "v4_launch_evidence_bundle.json").read_text(encoding="utf-8"))
    assert bundle["status"] == "READY"
    assert bundle["pb_dry_run_exit_code"] == 0
    assert bundle["go_no_go_exit_code"] == 0
    assert bundle["synthetic_borrow_used"] is False


def test_launch_evidence_bundle_blocks_when_pb_dry_run_fails(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("turnover_penalty: 20.0\nno_trade_band_bps: 300.0\nsector_net_cap: 0.10\n", encoding="utf-8")
    v3_cache = _tiny_v3_cache(tmp_path)
    borrow = tmp_path / "borrow.csv"
    _borrow_feed(["CCC"]).to_csv(borrow, index=False)
    gates = _gates(tmp_path, ["PASS"])
    readiness = _readiness(tmp_path, pb_status="READY")
    output = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_v4_launch_evidence_bundle.py",
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
            "--gates",
            str(gates),
            "--readiness",
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    bundle = json.loads((output / "v4_launch_evidence_bundle.json").read_text(encoding="utf-8"))
    assert bundle["status"] == "BLOCKED"
    assert bundle["pb_dry_run_exit_code"] == 1


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


def _gates(tmp_path, statuses: list[str]):
    path = tmp_path / "gates.json"
    path.write_text(json.dumps([{"gate_id": f"G-{idx}", "status": status} for idx, status in enumerate(statuses)]), encoding="utf-8")
    return path


def _readiness(tmp_path, *, pb_status: str):
    path = tmp_path / "readiness.md"
    path.write_text(
        "\n".join(
            [
                "| item | priority | status |",
                "| --- | --- | --- |",
                "| PIT audit live wiring | P0 | READY |",
                f"| PB borrow real feed | P0 | {pb_status} |",
                "| ADV20 daily refresh | P0 | READY |",
                "| incident sink | P0 | READY |",
                "| kill switch operator runbook | P0 | READY |",
                "| prod input loader | P0 | READY |",
            ]
        ),
        encoding="utf-8",
    )
    return path
