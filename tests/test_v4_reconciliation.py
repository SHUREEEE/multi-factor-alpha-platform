"""Tests for V4 source-of-truth reconciliation.

Covers: REQ-F-014, REQ-N-004.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from src.portfolio.v4.builder import build_v4_weights
from src.portfolio.v4.cache_io import V4CacheRecord, compute_weights_hash, write_v4_cache
from src.portfolio.v4.reconciliation import ReconciliationError, assert_reconciled, reconcile_cache_to_builder
from tests.v4_test_utils import tiny_config, tiny_inputs


def test_reconcile_cache_to_builder_passes_for_same_inputs(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")

    reconciliation = reconcile_cache_to_builder(record, result)

    assert reconciliation.pass_fail
    assert reconciliation.weight_l1 == 0.0
    assert reconciliation.weights_hash_match
    assert reconciliation.config_hash_match
    assert reconciliation.inputs_hash_match
    assert reconciliation.builder_version_match


def test_reconcile_fails_on_weight_drift_by_default(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    drifted_weights = result.weights.copy()
    drifted_weights.iloc[0, 0] += 1e-9
    drifted = dataclasses.replace(result, weights=drifted_weights, manifest={**result.manifest, "weights_hash": compute_weights_hash(drifted_weights.iloc[0])})

    reconciliation = reconcile_cache_to_builder(record, drifted)

    assert not reconciliation.pass_fail
    assert reconciliation.weight_l1 > 0.0
    assert "weight_l1_mismatch" in reconciliation.failures


def test_reconcile_allows_explicit_weight_tolerance(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    drifted_weights = result.weights.copy()
    drifted_weights.iloc[0, 0] += 1e-9
    drifted = dataclasses.replace(result, weights=drifted_weights)

    reconciliation = reconcile_cache_to_builder(record, drifted, tolerance_weight_l1=1e-6, tolerance_weight_max=1e-6)

    assert not reconciliation.pass_fail
    assert "weights_hash_mismatch" in reconciliation.failures
    assert "weight_l1_mismatch" not in reconciliation.failures


def test_reconcile_fails_on_config_hash_drift(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    changed = dataclasses.replace(result, manifest={**result.manifest, "config_hash": "changed"})

    reconciliation = reconcile_cache_to_builder(record, changed)

    assert not reconciliation.pass_fail
    assert not reconciliation.config_hash_match


def test_reconcile_fails_on_extra_cache_symbol_even_zero_weight(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    extra = pd.concat([record.weights, pd.Series({"ZZZ": 0.0})])
    changed_record = dataclasses.replace(record, weights=extra, weights_hash=compute_weights_hash(extra))

    reconciliation = reconcile_cache_to_builder(changed_record, result)

    assert not reconciliation.pass_fail
    assert not reconciliation.symbol_set_match


def test_reconcile_fails_on_builder_version_mismatch(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    changed_record = dataclasses.replace(record, builder_version="v4.0.0-D5")

    reconciliation = reconcile_cache_to_builder(changed_record, result)

    assert not reconciliation.pass_fail
    assert "builder_version_mismatch" in reconciliation.failures


def test_assert_reconciled_raises_with_all_failures(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    changed = dataclasses.replace(result, manifest={**result.manifest, "config_hash": "changed", "inputs_hash": "changed"})
    reconciliation = reconcile_cache_to_builder(record, changed)

    with pytest.raises(ReconciliationError) as exc:
        assert_reconciled(reconciliation)

    assert "config_hash_mismatch" in str(exc.value)
    assert "inputs_hash_mismatch" in str(exc.value)


def test_reconcile_fails_on_inputs_hash_mismatch_with_identical_weights(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    changed = dataclasses.replace(result, manifest={**result.manifest, "inputs_hash": "changed"})

    reconciliation = reconcile_cache_to_builder(record, changed)

    assert not reconciliation.pass_fail
    assert reconciliation.weight_l1 == 0.0
    assert "inputs_hash_mismatch" in reconciliation.failures
