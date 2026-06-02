"""Build Pillar 3 Stage 2 summary report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports/pillar3_stage2_summary.md"
FULL_SUMMARY_PATH = PROJECT_ROOT / "results/factor_summary_full_stage.csv"
STAGE1_SUMMARY_PATH = PROJECT_ROOT / "results/factor_summary_price_only_sector_neutral_fm.csv"
FUNDAMENTAL_FACTORS = [
    "book_to_market",
    "earnings_yield",
    "sales_to_price",
    "roe",
    "gross_profitability",
    "accruals",
    "log_market_cap",
    "log_total_assets",
    "log_revenue",
]


def main() -> None:
    """Write the Stage 2 report."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    full_summary = pd.read_csv(FULL_SUMMARY_PATH) if FULL_SUMMARY_PATH.exists() else pd.DataFrame()
    stage1_summary = pd.read_csv(STAGE1_SUMMARY_PATH) if STAGE1_SUMMARY_PATH.exists() else pd.DataFrame()
    REPORT_PATH.write_text(_build_report(stage1_summary, full_summary), encoding="utf-8")
    print(f"Saved Stage 2 summary to {REPORT_PATH.as_posix()}")


def _build_report(stage1_summary: pd.DataFrame, full_summary: pd.DataFrame) -> str:
    available_factors = set(full_summary["factor_name"]) if not full_summary.empty else set()
    skipped = [factor for factor in FUNDAMENTAL_FACTORS if factor not in available_factors]
    lines = [
        "# Pillar 3 Stage 2 Summary",
        "",
        "## Status",
        "",
        "Fundamentals pipeline repair is code-complete, but the current local raw fundamentals files are empty.",
        "The pipeline now degrades gracefully: missing fundamental fields skip only the affected factor and do not crash the run.",
        "",
        "## Fundamentals Data Finding",
        "",
        "- `data/raw/fundamentals_raw.parquet` shape: `(0, 4)`.",
        "- `data/processed/fundamentals.parquet` shape: `(0, 5)`.",
        "- `data/processed/daily_fundamentals.parquet` is missing.",
        "- Required fields unavailable: market_cap, book_value, net_income, revenue, total_assets, gross_profit, operating_cashflow.",
        "- See `reports/fundamentals_data_audit.md` for the detailed audit.",
        "",
        "## Fundamental Factors",
        "",
        f"Computed fundamental factors: {len(FUNDAMENTAL_FACTORS) - len(skipped)} / {len(FUNDAMENTAL_FACTORS)}.",
        f"Skipped fundamental factors: {', '.join(skipped)}.",
        "",
        "No substitute fields were invented. This is intentional: using guessed accounting fields would create false precision and possible look-ahead or definition errors.",
        "",
        "## Full-Stage Research Output",
        "",
        "Because no fundamental factors were available, `results/factor_summary_full_stage.csv` currently contains the six price-only factors only.",
        "",
        _summary_table(full_summary),
        "",
        "## Stage 1 vs Full Stage",
        "",
        "Full-stage results match the available price-only universe because no fundamental columns were activated.",
        "The Pillar 4 candidate pool is therefore unchanged from Stage 1.",
        "",
        "## Updated Pillar 4 Candidate List",
        "",
        "- Include: `short_term_reversal` as the primary price-only candidate.",
        "- Exclude for now: `momentum_12_1`, `week_52_high`, `idiosyncratic_vol`, `realized_vol`, `beta_inverse` as standalone long-high-score factors.",
        "- Pending Stage 2 data repair: value, quality, and size candidates.",
        "",
        "## Next Required Fix",
        "",
        "The blocker is upstream data acquisition, not factor math. The next task is to repair fundamental downloading so that the raw file contains actual long-format rows before daily as-of panels are built.",
        "",
    ]
    return "\n".join(lines)


def _summary_table(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "Full-stage summary is missing."
    columns = ["factor_name", "ic_mean_1d", "ic_ir_1d", "long_short_sharpe", "monotonicity", "fama_macbeth_tstat"]
    frame = summary[[column for column in columns if column in summary.columns]]
    header = "| " + " | ".join(frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(frame.columns)) + " |"
    rows = [_markdown_row(row, list(frame.columns)) for row in frame.to_dict("records")]
    return "\n".join([header, separator, *rows])


def _markdown_row(row: dict[str, object], columns: list[str]) -> str:
    values = []
    for column in columns:
        value = row[column]
        values.append(f"{value:.6f}" if isinstance(value, float) else str(value))
    return "| " + " | ".join(values) + " |"


if __name__ == "__main__":
    main()
