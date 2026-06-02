"""Build a side-by-side report for sector-neutral price factors."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "results/factor_summary_price_only.csv"
SECTOR_NEUTRAL_PATH = PROJECT_ROOT / "results/factor_summary_price_only_sector_neutral.csv"
REPORT_PATH = PROJECT_ROOT / "reports/pillar3_sector_neutral_comparison.md"


def main() -> None:
    """Create comparison report, or a blocked report if sector data is unavailable."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    baseline = pd.read_csv(BASELINE_PATH) if BASELINE_PATH.exists() else pd.DataFrame()
    if not SECTOR_NEUTRAL_PATH.exists():
        REPORT_PATH.write_text(_blocked_report(baseline), encoding="utf-8")
    else:
        sector_neutral = pd.read_csv(SECTOR_NEUTRAL_PATH)
        REPORT_PATH.write_text(_comparison_report(baseline, sector_neutral), encoding="utf-8")
    print(f"Saved sector-neutral comparison report to {REPORT_PATH.as_posix()}")


def _blocked_report(baseline: pd.DataFrame) -> str:
    lines = [
        "# Pillar 3 Sector-Neutral Comparison",
        "",
        "Status: blocked.",
        "",
        "The sector-neutral factor file was not generated because `data/raw/ticker_sector_map.parquet` currently has insufficient known sector coverage.",
        "Yahoo Finance returned rate-limit / connection errors during the yfinance sector fetch, so all tickers were assigned `Unknown`.",
        "",
        "**No sector-neutral comparison is reported yet, because using an all-Unknown sector map would be fake neutralization.**",
        "",
        "Commands to rerun after rate limits clear:",
        "",
        "```powershell",
        "python scripts/fetch_ticker_sectors.py --force-refresh",
        "python scripts/compute_sector_neutral_price_factors.py",
        "python scripts/run_factor_research.py --stage price --factor-file data/factor_data/factors_sector_neutral.parquet --output-prefix sector_neutral",
        "python scripts/build_sector_neutral_comparison.py",
        "```",
        "",
        "## Baseline Price-Only Metrics",
        "",
        _summary_table(baseline),
    ]
    return "\n".join(lines) + "\n"


def _comparison_report(baseline: pd.DataFrame, sector_neutral: pd.DataFrame) -> str:
    merged = baseline.merge(sector_neutral, on="factor_name", suffixes=("_baseline", "_sector_neutral"))
    columns = [
        "factor_name",
        "ic_mean_1d_baseline",
        "ic_mean_1d_sector_neutral",
        "ic_ir_1d_baseline",
        "ic_ir_1d_sector_neutral",
        "long_short_sharpe_baseline",
        "long_short_sharpe_sector_neutral",
        "monotonicity_baseline",
        "monotonicity_sector_neutral",
    ]
    return "\n".join(["# Pillar 3 Sector-Neutral Comparison", "", _markdown_table(merged[columns])]) + "\n"


def _summary_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Baseline summary is missing."
    columns = ["factor_name", "ic_mean_1d", "ic_ir_1d", "long_short_sharpe", "monotonicity"]
    return _markdown_table(frame[columns])


def _markdown_table(frame: pd.DataFrame) -> str:
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
