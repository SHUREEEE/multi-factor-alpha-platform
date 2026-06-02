"""Tests for V4 builder source-of-truth manifest contract."""

from __future__ import annotations

import copy
import dataclasses
from datetime import datetime, timezone

from src.portfolio.v4.builder import build_v4_weights
from tests.v4_test_utils import tiny_config, tiny_inputs


def test_builder_weights_hash_is_deterministic_across_runs() -> None:
    inputs = tiny_inputs()
    config = tiny_config()

    first = build_v4_weights(inputs, config)
    second = build_v4_weights(inputs, config)

    assert first.manifest["weights_hash"] == second.manifest["weights_hash"]


def test_builder_manifest_contains_required_source_of_truth_fields() -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())
    required = {
        "inputs_digest",
        "config_hash",
        "weights_hash",
        "builder_version",
        "build_timestamp_utc",
        "validation_state",
        "validation_substatuses",
    }

    assert required.issubset(result.manifest)


def test_builder_does_not_mutate_input_bundle() -> None:
    inputs = tiny_inputs()
    before = copy.deepcopy(inputs)

    build_v4_weights(inputs, tiny_config())

    assert inputs.raw_weights.equals(before.raw_weights)
    assert inputs.sectors.equals(before.sectors)
    assert inputs.betas.equals(before.betas)


def test_builder_weights_hash_changes_when_config_changes() -> None:
    inputs = tiny_inputs()
    first = build_v4_weights(inputs, tiny_config(turnover_penalty=0.0))
    second = build_v4_weights(inputs, tiny_config(turnover_penalty=0.5))

    assert first.manifest["weights_hash"] != second.manifest["weights_hash"]


def test_builder_version_is_d7() -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())

    assert result.manifest["builder_version"] == "v4.0.0-D7"


def test_build_timestamp_is_utc_iso8601() -> None:
    result = build_v4_weights(tiny_inputs(), tiny_config())

    parsed = datetime.fromisoformat(result.manifest["build_timestamp_utc"].replace("Z", "+00:00"))
    assert parsed.tzinfo == timezone.utc
