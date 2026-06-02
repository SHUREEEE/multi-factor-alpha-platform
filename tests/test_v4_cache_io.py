"""Tests for V4 cache I/O and canonical hashing."""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.builder import build_v4_weights
from src.portfolio.v4.cache_io import compute_inputs_hash, compute_weights_hash, read_v4_cache, write_v4_cache
from tests.v4_test_utils import tiny_config, tiny_inputs


def test_v4_cache_write_read_round_trip(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    record = write_v4_cache(result, tmp_path, asof_date="2024-01-03")
    loaded = read_v4_cache(tmp_path, "2024-01-03")

    pd.testing.assert_series_equal(loaded.weights.sort_index(), record.weights.sort_index())
    assert loaded.manifest == record.manifest
    assert loaded.weights_hash == record.weights_hash


def test_v4_cache_hashes_are_deterministic(tmp_path) -> None:
    inputs = tiny_inputs()
    config = tiny_config()
    first = write_v4_cache(build_v4_weights(inputs, config), tmp_path / "a", asof_date="2024-01-03")
    second = write_v4_cache(build_v4_weights(inputs, config), tmp_path / "b", asof_date="2024-01-03")

    assert first.weights_hash == second.weights_hash
    assert first.config_hash == second.config_hash
    assert first.inputs_hash == second.inputs_hash


def test_v4_weights_hash_changes_on_small_weight_move() -> None:
    weights = pd.Series({"AAA": 0.1, "BBB": -0.1})
    changed = weights.copy()
    changed["AAA"] += 1e-10

    assert compute_weights_hash(weights) != compute_weights_hash(changed)


def test_v4_cache_write_without_overwrite_raises(tmp_path) -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    write_v4_cache(result, tmp_path, asof_date="2024-01-03")

    with pytest.raises(FileExistsError):
        write_v4_cache(result, tmp_path, asof_date="2024-01-03")


def test_v4_weights_hash_ignores_symbol_ordering() -> None:
    ordered = pd.Series({"AAA": 0.1, "BBB": -0.1})
    shuffled = pd.Series({"BBB": -0.1, "AAA": 0.1})

    assert compute_weights_hash(ordered) == compute_weights_hash(shuffled)


def test_v4_inputs_hash_distinguishes_none_from_empty_series() -> None:
    inputs_none = tiny_inputs()
    inputs_empty = tiny_inputs().__class__(**{**tiny_inputs().__dict__, "market_proxy_returns": pd.Series(dtype=float)})

    assert compute_inputs_hash(inputs_none) != compute_inputs_hash(inputs_empty)
