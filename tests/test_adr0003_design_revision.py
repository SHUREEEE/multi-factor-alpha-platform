"""Tests for ADR-0003 design revision guardrails."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_adr0003_exists_and_supersedes_design_section_3() -> None:
    adr = (PROJECT_ROOT / "docs" / "adr" / "ADR-0003-v4-turnover-design-revision.md").read_text(encoding="utf-8")
    design = (PROJECT_ROOT / "reports" / "v4_design.md").read_text(encoding="utf-8")

    assert "ADR-0003 supersedes" in adr
    assert "ADR-0003 supersedes the original scalar turnover-penalty design" in design


def test_adr0003_does_not_relax_locked_thresholds() -> None:
    adr = (PROJECT_ROOT / "docs" / "adr" / "ADR-0003-v4-turnover-design-revision.md").read_text(encoding="utf-8")

    assert "`0.75` tail-turnover reduction" in adr
    assert "`1.62 x 0.9`" in adr
    assert "`1.14 x 0.9`" in adr
    assert "This is an optimizer-form design revision, not a threshold revision." in adr


def test_adr0003_keeps_req_f_001_in_progress_until_e1_passes() -> None:
    design = (PROJECT_ROOT / "reports" / "v4_design.md").read_text(encoding="utf-8")

    assert "| REQ-F-001 | MERGED |" in design
    assert "ADR-0003 design revision accepted" in design
    assert "REQ-F-001 MERGED 2026-05-31 via ADR-0003 D-hotfix E1 rerun" in design
