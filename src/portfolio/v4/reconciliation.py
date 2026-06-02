"""V4 cache-to-builder reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.portfolio.v4.cache_io import V4CacheRecord, compute_weights_hash


class ReconciliationError(RuntimeError):
    """Raised when cache and canonical builder output do not reconcile."""


@dataclass(frozen=True)
class ReconciliationResult:
    """Cache-vs-builder reconciliation result."""

    pass_fail: bool
    weight_l1: float
    weight_max_abs_diff: float
    weights_hash_match: bool
    config_hash_match: bool
    inputs_hash_match: bool
    builder_version_match: bool
    symbol_set_match: bool
    tolerance_weight_l1: float
    tolerance_weight_max: float
    failures: list[str]


V4ReconciliationResult = ReconciliationResult


def reconcile_cache_to_builder(
    cache_record: V4CacheRecord,
    rebuild_result,
    *,
    tolerance_weight_l1: float = 0.0,
    tolerance_weight_max: float = 0.0,
) -> ReconciliationResult:
    """Compare a cache record to a canonical builder rebuild result."""
    rebuild_weights = _last_weights(rebuild_result.weights)
    cache_weights = cache_record.weights.astype(float)
    cache_symbols = set(cache_weights.index.astype(str))
    rebuild_symbols = set(rebuild_weights.index.astype(str))
    symbol_set_match = cache_symbols == rebuild_symbols
    failures: list[str] = []
    if not symbol_set_match:
        failures.append("symbol_set_mismatch")

    common = sorted(cache_symbols & rebuild_symbols)
    cache_aligned = cache_weights.reindex(common).fillna(0.0)
    rebuild_aligned = rebuild_weights.reindex(common).fillna(0.0)
    diff = cache_aligned - rebuild_aligned
    weight_l1 = float(diff.abs().sum())
    weight_max = float(diff.abs().max()) if not diff.empty else 0.0
    if weight_l1 > tolerance_weight_l1:
        failures.append("weight_l1_mismatch")
    if weight_max > tolerance_weight_max:
        failures.append("weight_max_abs_mismatch")

    rebuild_weights_hash = compute_weights_hash(rebuild_weights)
    weights_hash_match = cache_record.weights_hash == rebuild_weights_hash
    config_hash_match = cache_record.config_hash == str(rebuild_result.manifest.get("config_hash"))
    inputs_hash_match = cache_record.inputs_hash == str(rebuild_result.manifest.get("inputs_hash"))
    builder_version_match = cache_record.builder_version == str(rebuild_result.manifest.get("builder_version"))
    for flag, reason in [
        (weights_hash_match, "weights_hash_mismatch"),
        (config_hash_match, "config_hash_mismatch"),
        (inputs_hash_match, "inputs_hash_mismatch"),
        (builder_version_match, "builder_version_mismatch"),
    ]:
        if not flag:
            failures.append(reason)

    return ReconciliationResult(
        pass_fail=not failures,
        weight_l1=weight_l1,
        weight_max_abs_diff=weight_max,
        weights_hash_match=weights_hash_match,
        config_hash_match=config_hash_match,
        inputs_hash_match=inputs_hash_match,
        builder_version_match=builder_version_match,
        symbol_set_match=symbol_set_match,
        tolerance_weight_l1=tolerance_weight_l1,
        tolerance_weight_max=tolerance_weight_max,
        failures=failures,
    )


def assert_reconciled(result: ReconciliationResult) -> None:
    """Raise when reconciliation failed."""
    if not result.pass_fail:
        raise ReconciliationError("V4 reconciliation failed: " + ",".join(result.failures))


def _last_weights(weights: pd.DataFrame | pd.Series) -> pd.Series:
    if isinstance(weights, pd.Series):
        return weights.astype(float)
    if weights.empty:
        return pd.Series(dtype=float)
    return weights.iloc[-1].astype(float)
