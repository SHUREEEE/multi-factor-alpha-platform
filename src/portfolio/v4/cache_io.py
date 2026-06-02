"""V4 cache I/O and canonical hashing utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class V4CacheRecord:
    """Single-date V4 cache record."""

    asof_date: object
    weights: pd.Series
    manifest: dict
    weights_hash: str
    config_hash: str
    inputs_hash: str
    builder_version: str


def write_v4_cache(
    result,
    cache_dir: Path,
    *,
    asof_date,
    overwrite: bool = False,
) -> V4CacheRecord:
    """Write one-date weights, manifest, and record metadata."""
    path = Path(cache_dir) / pd.Timestamp(asof_date).date().isoformat()
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.mkdir(parents=True, exist_ok=True)
    weights = _weights_for_asof(result.weights, asof_date)
    weights_hash = compute_weights_hash(weights)
    record = V4CacheRecord(
        asof_date=pd.Timestamp(asof_date).date().isoformat(),
        weights=weights,
        manifest=dict(result.manifest),
        weights_hash=weights_hash,
        config_hash=str(result.manifest["config_hash"]),
        inputs_hash=str(result.manifest["inputs_hash"]),
        builder_version=str(result.manifest["builder_version"]),
    )
    pd.DataFrame({"symbol": weights.sort_index().index, "weight": weights.sort_index().to_numpy(dtype=float)}).to_parquet(path / "weights.parquet", index=False)
    (path / "manifest.json").write_text(json.dumps(record.manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (path / "record.json").write_text(
        json.dumps(
            {
                "asof_date": record.asof_date,
                "weights_hash": record.weights_hash,
                "config_hash": record.config_hash,
                "inputs_hash": record.inputs_hash,
                "builder_version": record.builder_version,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return record


def read_v4_cache(cache_dir: Path, asof_date) -> V4CacheRecord:
    """Read one-date V4 cache record."""
    path = Path(cache_dir) / pd.Timestamp(asof_date).date().isoformat()
    weights_df = pd.read_parquet(path / "weights.parquet")
    weights = pd.Series(weights_df["weight"].to_numpy(dtype=float), index=weights_df["symbol"].astype(str))
    weights.index.name = None
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    record = json.loads((path / "record.json").read_text(encoding="utf-8"))
    return V4CacheRecord(
        asof_date=record["asof_date"],
        weights=weights,
        manifest=manifest,
        weights_hash=record["weights_hash"],
        config_hash=record["config_hash"],
        inputs_hash=record["inputs_hash"],
        builder_version=record["builder_version"],
    )


def compute_weights_hash(weights: pd.Series) -> str:
    """Canonical sha256 over sorted, fixed-precision signed weights."""
    clean = weights.dropna().astype(float).sort_index()
    payload = "".join(f"{symbol}\t{value:.12e}\n" for symbol, value in clean.items()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_config_hash(config: Any) -> str:
    """Canonical sha256 over dataclass config JSON."""
    payload = _json_bytes(_canonicalize(asdict(config) if is_dataclass(config) else config))
    return hashlib.sha256(payload).hexdigest()


def compute_inputs_digest(inputs: Any) -> dict[str, str]:
    """Hash each input bundle field independently."""
    values = asdict(inputs) if is_dataclass(inputs) else dict(inputs)
    return {key: _hash_input_value(value) for key, value in sorted(values.items())}


def compute_inputs_hash(inputs: Any) -> str:
    """Canonical sha256 over the per-field input digest."""
    return hashlib.sha256(_json_bytes(compute_inputs_digest(inputs))).hexdigest()


def _hash_input_value(value: Any) -> str:
    if value is None:
        return "<NONE>"
    if isinstance(value, pd.DataFrame):
        return hashlib.sha256(value.sort_index(axis=0).sort_index(axis=1).to_csv(float_format="%.12e").encode("utf-8")).hexdigest()
    if isinstance(value, pd.Series):
        return hashlib.sha256(value.sort_index().to_csv(float_format="%.12e").encode("utf-8")).hexdigest()
    return hashlib.sha256(_json_bytes(_canonicalize(value))).hexdigest()


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (set, tuple)):
        return sorted(_canonicalize(item) for item in value)
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonicalize(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if is_dataclass(value):
        return _canonicalize(asdict(value))
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _weights_for_asof(weights: pd.DataFrame | pd.Series, asof_date) -> pd.Series:
    if isinstance(weights, pd.Series):
        result = weights.astype(float)
        result.name = None
        result.index.name = None
        return result
    if pd.Timestamp(asof_date) in weights.index:
        result = weights.loc[pd.Timestamp(asof_date)].astype(float)
        result.name = None
        result.index.name = None
        return result
    if len(weights.index) == 1:
        result = weights.iloc[0].astype(float)
        result.name = None
        result.index.name = None
        return result
    raise KeyError(f"asof_date {asof_date} not found in weights.")
