"""Meta-tests for V4 requirement coverage.

Covers: REQ-N-002.
"""

from __future__ import annotations

import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = PROJECT_ROOT / "reports" / "v4_design.md"
ALLOWED_STATUSES = {"NOT-STARTED", "IN-PROGRESS", "MERGED"}


def test_every_req_f_has_test_file() -> None:
    planned = _planned_test_coverage()

    for req_id, row in planned.items():
        assert req_id.startswith("REQ-F-")
        assert (PROJECT_ROOT / row["test_path"]).exists(), req_id


def test_every_test_file_references_its_req_id() -> None:
    planned = _planned_test_coverage()

    for req_id, row in planned.items():
        source = (PROJECT_ROOT / row["test_path"]).read_text(encoding="utf-8")
        assert req_id in source, f"{row['test_path']} must reference {req_id}"


def test_status_tracker_consistency() -> None:
    planned = _planned_test_coverage()
    tracker = _status_tracker()

    for req_id, row in tracker.items():
        assert row["status"] in ALLOWED_STATUSES, req_id
        if req_id in planned:
            assert row["test_ref"] == planned[req_id]["test_path"], req_id
    assert tracker["REQ-N-002"]["status"] != "NOT-STARTED"


def test_all_req_f_rows_are_merged_after_e1_acceptance() -> None:
    tracker = _status_tracker()

    for req_id, row in tracker.items():
        if req_id.startswith("REQ-F-"):
            assert row["status"] == "MERGED", req_id


def test_module_namespace_reserved() -> None:
    mapping = _requirement_mapping()

    for req_id, row in mapping.items():
        module_path = row["module"]
        function_name = row["function"]
        if "*" in module_path:
            continue
        path = PROJECT_ROOT / module_path
        if not path.exists():
            continue
        module_name = module_path.removesuffix(".py").replace("/", ".")
        module = importlib.import_module(module_name)
        if function_name.endswith("contract"):
            continue
        assert hasattr(module, function_name), req_id


def _requirement_mapping() -> dict[str, dict[str, str]]:
    rows = _extract_table("## 2. Requirement To Design Mapping")
    return {
        row["req_id"]: {
            "module": _strip_code(row["design module"]),
            "function": _strip_code(row["primary function or artifact"]),
        }
        for row in rows
    }


def _planned_test_coverage() -> dict[str, dict[str, str]]:
    rows = _extract_table("## 11. REQ-N-002: Planned Test Coverage")
    return {
        row["req_id"]: {
            "test_path": _strip_code(row["planned test path"]),
            "assertion": row["main assertion"],
        }
        for row in rows
    }


def _status_tracker() -> dict[str, dict[str, str]]:
    rows = _extract_table("## 15. Implementation Status Tracker")
    return {
        row["REQ-ID"]: {
            "status": row["status"],
            "pr_ref": row["PR-ref"],
            "test_ref": _strip_code(row["test-ref"]),
        }
        for row in rows
    }


def _extract_table(section_heading: str) -> list[dict[str, str]]:
    lines = DESIGN_PATH.read_text(encoding="utf-8").splitlines()
    start = lines.index(section_heading)
    table_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## ") and table_lines:
            break
        if line.startswith("|"):
            table_lines.append(line)
    header = [_clean_cell(cell) for cell in table_lines[0].strip("|").split("|")]
    rows = []
    for line in table_lines[2:]:
        values = [_clean_cell(cell) for cell in line.strip("|").split("|")]
        if len(values) == len(header):
            rows.append(dict(zip(header, values, strict=True)))
    return rows


def _clean_cell(value: str) -> str:
    return value.strip()


def _strip_code(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value
