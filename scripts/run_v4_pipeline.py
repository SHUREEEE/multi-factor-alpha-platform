"""Minimal V4 pipeline scaffold with cache reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.cache_io import write_v4_cache
from src.portfolio.v4.data_integrity import PitLaunchGateError
from src.portfolio.v4.reconciliation import assert_reconciled, reconcile_cache_to_builder


def build_manifest(config_path: Path, asof: str, output_dir: Path) -> dict[str, object]:
    """Build a reproducibility manifest for a V4 pipeline invocation."""
    return {
        "pipeline": "v4",
        "asof": asof,
        "config_path": str(config_path),
        "config_sha256": _sha256_file(config_path) if config_path.exists() else None,
        "output_dir": str(output_dir),
        "builder_contract": "src.portfolio.v4.builder.build_v4_weights",
        "status": "E2_PROD_LOADER_READY",
    }


def write_manifest(manifest: dict[str, object], output_dir: Path) -> Path:
    """Write a V4 manifest and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "v4_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the D7 V4 pipeline scaffold.")
    parser.add_argument("--asof", required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--inputs-stub", action="store_true")
    parser.add_argument("--inputs-prod", action="store_true")
    parser.add_argument("--v3-cache-dir", type=Path, default=PROJECT_ROOT / "results" / "pillar5_artifacts")
    parser.add_argument("--borrow-feed", type=Path, help="Optional real PB borrow feed CSV for prod dry-run.")
    parser.add_argument("--pit-fail-stub", action="store_true")
    args = parser.parse_args(argv)
    if not args.config.exists():
        parser.error("--config must point to an existing file")
    if args.inputs_stub == args.inputs_prod:
        parser.error("choose exactly one of --inputs-stub or --inputs-prod")

    try:
        if args.inputs_stub:
            inputs, config = _stub_bundle(args.asof, pit_fail=args.pit_fail_stub)
            input_mode = "stub"
        else:
            inputs, config = _prod_bundle(args.asof, args.v3_cache_dir, args.config, borrow_feed_path=args.borrow_feed)
            input_mode = "prod"
        result = build_v4_weights(inputs, config)
        record = write_v4_cache(result, args.output, asof_date=args.asof, overwrite=True)
        rebuilt = build_v4_weights(inputs, config)
        assert_reconciled(reconcile_cache_to_builder(record, rebuilt))
        write_manifest({**build_manifest(args.config, args.asof, args.output), "input_mode": input_mode, **result.manifest}, args.output)
    except (PitLaunchGateError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _stub_bundle(asof: str, *, pit_fail: bool) -> tuple[V4InputBundle, V4Config]:
    dates = pd.DatetimeIndex([pd.Timestamp(asof)], name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    audit_status = "FAIL" if pit_fail else "PASS"
    pit = pd.DataFrame(
        {
            "date": [asof],
            "dataset": ["prices"],
            "max_asof_timestamp_utc": [f"{asof}T20:00:00Z"],
            "missing_symbol_count": [0],
            "future_timestamp_count": [0],
            "stale_field_count": [0],
            "corporate_action_audit_pass": [True],
            "audit_status": [audit_status],
        }
    )
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        pit_audit_records=pit,
        decision_timestamp_utc=f"{asof}T21:00:00Z",
        required_pit_datasets={"prices"},
    )
    config = V4Config(
        sector_net_cap=1.0,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=0.0,
        short_top10_cap=1.0,
        single_short_cap=0.60,
    )
    return inputs, config


def _prod_bundle(
    asof: str,
    v3_cache_dir: Path,
    config_path: Path,
    *,
    borrow_feed_path: Path | None = None,
) -> tuple[V4InputBundle, V4Config]:
    """Load a one-day V4 bundle from canonical V3 artifacts."""
    v3_cache_dir = Path(v3_cache_dir)
    weights_path = v3_cache_dir / "v3_weights.parquet"
    sectors_path = v3_cache_dir / "v3_sector_map.csv"
    if not weights_path.exists():
        raise RuntimeError(f"missing V3 weights: {weights_path}")
    if not sectors_path.exists():
        raise RuntimeError(f"missing V3 sector map: {sectors_path}")
    weights = pd.read_parquet(weights_path).fillna(0.0).astype(float)
    asof_ts = pd.Timestamp(asof)
    if asof_ts not in weights.index:
        raise RuntimeError(f"asof {asof} not found in V3 weights")
    loc = weights.index.get_loc(asof_ts)
    if isinstance(loc, slice):
        loc = loc.start
    prior_idx = max(int(loc) - 1, 0)
    raw = weights.loc[[asof_ts]]
    prior = pd.DataFrame([weights.iloc[prior_idx]], index=raw.index, columns=raw.columns)
    sectors_frame = pd.read_csv(sectors_path)
    symbol_col = "symbol" if "symbol" in sectors_frame.columns else sectors_frame.columns[0]
    sector_col = "sector" if "sector" in sectors_frame.columns else sectors_frame.columns[-1]
    sectors = sectors_frame.set_index(symbol_col)[sector_col].reindex(raw.columns).fillna("Unknown")
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=raw.index, columns=raw.columns),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=raw.index, columns=raw.columns),
        prior_weights=prior,
        borrow_feed=_read_borrow_feed(borrow_feed_path) if borrow_feed_path is not None else None,
        metadata={"asof_date": asof_ts},
    )
    config_values = _read_simple_config(config_path)
    config = V4Config(
        sector_net_cap=float(config_values.get("sector_net_cap", 0.10)),
        gross_target=2.0,
        turnover_penalty=float(config_values.get("turnover_penalty", 20.0)),
        no_trade_band_bps=float(config_values.get("no_trade_band_bps", 300.0)),
        short_top10_cap=1.0,
        single_short_cap=1.0,
    )
    return inputs, config


def _read_borrow_feed(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"missing PB borrow feed: {path}")
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _read_simple_config(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        try:
            values[key.strip()] = float(value.strip())
        except ValueError:
            continue
    return values


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
