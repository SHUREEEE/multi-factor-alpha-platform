"""Audit available raw and processed fundamental data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports/fundamentals_data_audit.md"
FUNDAMENTAL_PATHS = [
    PROJECT_ROOT / "data/raw/fundamentals.parquet",
    PROJECT_ROOT / "data/raw/fundamentals_raw.parquet",
    PROJECT_ROOT / "data/processed/fundamentals.parquet",
    PROJECT_ROOT / "data/processed/daily_fundamentals.parquet",
]
REQUIRED_FIELDS = [
    "market_cap",
    "book_value",
    "net_income",
    "revenue",
    "total_assets",
    "gross_profit",
    "operating_cashflow",
]


def main() -> None:
    """Write a fundamentals audit report."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_build_report(), encoding="utf-8")
    print(f"Saved fundamentals audit to {REPORT_PATH.as_posix()}")


def _build_report() -> str:
    sections = ["# Fundamentals Data Audit", ""]
    available_fields: set[str] = set()
    for path in FUNDAMENTAL_PATHS:
        sections.append(_audit_one_path(path))
        if path.exists():
            frame = pd.read_parquet(path)
            available_fields.update(_field_names(frame))
    sections.extend(_required_field_section(available_fields))
    sections.extend(_diagnosis_section(available_fields))
    return "\n".join(sections) + "\n"


def _audit_one_path(path: Path) -> str:
    if not path.exists():
        return f"## {path.relative_to(PROJECT_ROOT).as_posix()}\n\nStatus: missing.\n"
    frame = pd.read_parquet(path)
    lines = [
        f"## {path.relative_to(PROJECT_ROOT).as_posix()}",
        "",
        f"- Shape: {frame.shape}",
        f"- Index type: {type(frame.index).__name__}",
        f"- Index names: {list(frame.index.names)}",
        f"- Columns: {list(frame.columns)}",
        "",
        _column_table(frame),
        "",
        _date_coverage(frame),
        "",
    ]
    return "\n".join(lines)


def _column_table(frame: pd.DataFrame) -> str:
    lines = ["| column | dtype | non_null | pct_non_null |", "| --- | --- | ---: | ---: |"]
    row_count = max(len(frame), 1)
    for column in frame.columns:
        non_null = int(frame[column].notna().sum())
        lines.append(f"| {column} | {frame[column].dtype} | {non_null} | {non_null / row_count:.1%} |")
    return "\n".join(lines)


def _date_coverage(frame: pd.DataFrame) -> str:
    date_values = _date_values(frame)
    if date_values.empty:
        return "Date coverage: no date values."
    return f"Date coverage: {date_values.min().date()} to {date_values.max().date()}."


def _date_values(frame: pd.DataFrame) -> pd.Series:
    if "date" in frame.columns:
        return pd.to_datetime(frame["date"], errors="coerce").dropna()
    if isinstance(frame.index, pd.MultiIndex) and "date" in frame.index.names:
        return pd.Series(pd.to_datetime(frame.index.get_level_values("date"), errors="coerce")).dropna()
    if frame.index.name == "date":
        return pd.Series(pd.to_datetime(frame.index, errors="coerce")).dropna()
    return pd.Series(dtype="datetime64[ns]")


def _field_names(frame: pd.DataFrame) -> set[str]:
    if "field" in frame.columns:
        return set(frame["field"].dropna().astype(str))
    return set(frame.columns.astype(str))


def _required_field_section(available_fields: set[str]) -> list[str]:
    lines = ["## Required Field Availability", "", "| field | available |", "| --- | --- |"]
    for field in REQUIRED_FIELDS:
        lines.append(f"| {field} | {'yes' if field in available_fields else 'no'} |")
    lines.append("")
    return lines


def _diagnosis_section(available_fields: set[str]) -> list[str]:
    if available_fields:
        diagnosis = "Some fields are available; inspect naming before computing factors."
    else:
        diagnosis = "No usable fundamental rows are available. Fundamental factors must be skipped until data download is repaired."
    return [
        "## Diagnosis",
        "",
        f"- {diagnosis}",
        "- Current raw data is not a quarterly snapshot panel and not a daily as-of panel; it is empty.",
        "- Do not invent missing fields such as gross_profit or operating_cashflow.",
        "",
    ]


if __name__ == "__main__":
    main()
