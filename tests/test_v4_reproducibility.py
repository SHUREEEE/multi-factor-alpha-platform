"""Tests for V4 reproducibility CLI contract.

Covers: REQ-N-001.
"""

from __future__ import annotations

import json

from scripts.run_v4_pipeline import build_manifest, write_manifest


def test_v4_pipeline_manifest_records_config_hash(tmp_path) -> None:
    config = tmp_path / "v4.yaml"
    config.write_text("run_label: test\n", encoding="utf-8")
    output = tmp_path / "artifacts"

    manifest = build_manifest(config, "2026-05-31", output)
    path = write_manifest(manifest, output)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["pipeline"] == "v4"
    assert saved["asof"] == "2026-05-31"
    assert saved["config_sha256"]
    assert saved["builder_contract"] == "src.portfolio.v4.builder.build_v4_weights"
    assert saved["status"] == "E2_PROD_LOADER_READY"
