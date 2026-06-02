"""Audit sign conventions for price-only factors."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_factor_research import PRICE_FACTOR_NAMES  # noqa: E402
from src.research.ic_analysis import compute_ic_timeseries  # noqa: E402
from src.research.quantile_test import compute_long_short_return, compute_monotonicity, quantile_portfolio_returns  # noqa: E402


def main() -> None:
    """Create formal direction-audit artifacts."""
    factors = pd.read_parquet(PROJECT_ROOT / "data/factor_data/all_factors.parquet").sort_index()
    prices = pd.read_parquet(PROJECT_ROOT / "data/processed/prices.parquet").sort_index()
    audit = pd.DataFrame([_audit_one_factor(name, factors[[name]], prices) for name in PRICE_FACTOR_NAMES])
    csv_path = PROJECT_ROOT / "results/price_factor_direction_audit.csv"
    markdown_path = PROJECT_ROOT / "reports/pillar3_direction_audit.md"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False)
    markdown_path.write_text(_build_markdown(audit), encoding="utf-8")
    print(f"Saved direction audit CSV to {csv_path.as_posix()}")
    print(f"Saved direction audit report to {markdown_path.as_posix()}")


def _audit_one_factor(factor_name: str, factor_frame: pd.DataFrame, prices: pd.DataFrame) -> dict[str, object]:
    ic_table = compute_ic_timeseries(factor_frame, prices, periods=[1], already_shifted=True)
    quantile_returns = quantile_portfolio_returns(factor_frame, prices, n_quantiles=10, already_shifted=True)
    long_short_returns = compute_long_short_return(quantile_returns)
    mean_ic = float(ic_table["ic_1d"].mean(skipna=True))
    long_short_mean = float(long_short_returns.mean(skipna=True))
    monotonicity = float(compute_monotonicity(quantile_returns))
    return {
        "factor": factor_name,
        "mean_ic_1d": mean_ic,
        "ic_sign": _sign_label(mean_ic),
        "long_short_mean_return_1d": long_short_mean,
        "long_short_sign": _sign_label(long_short_mean),
        "monotonicity": monotonicity,
        "monotonicity_sign": _sign_label(monotonicity),
        "directions_consistent": _directions_consistent(mean_ic, long_short_mean, monotonicity),
        "plausible_explanation": _plausible_explanation(factor_name, mean_ic, long_short_mean, monotonicity),
        "automatic_sign_flip_applied": "no",
    }


def _sign_label(value: float) -> str:
    if np.isnan(value) or abs(value) < 1e-12:
        return "zero_or_nan"
    return "positive" if value > 0.0 else "negative"


def _directions_consistent(mean_ic: float, long_short_mean: float, monotonicity: float) -> str:
    signs = {_sign_label(value) for value in [mean_ic, long_short_mean, monotonicity]}
    active_signs = signs - {"zero_or_nan"}
    return "yes" if len(active_signs) <= 1 else "no"


def _plausible_explanation(factor_name: str, mean_ic: float, long_short_mean: float, monotonicity: float) -> str:
    if _directions_consistent(mean_ic, long_short_mean, monotonicity) == "yes":
        return "IC, long-short spread, and monotonicity point in the same broad direction."
    if factor_name in {"idiosyncratic_vol", "realized_vol", "beta_inverse"}:
        return "Likely sector/universe/tail effect: low-vol definitions are correct, but sector tilts and top-decile tails dominate the average spread."
    if factor_name == "week_52_high":
        return "Likely regime or tail effect: broad rank IC is mildly positive, while extreme high-score stocks underperform low-score stocks."
    return "Likely weak signal with noisy tails; inspect quantile curve before any sign decision."


def _build_markdown(audit: pd.DataFrame) -> str:
    lines = [
        "# Pillar 3 Price Factor Direction Audit",
        "",
        "This report checks sign conventions for the active price-only factors.",
        "",
        "**No automatic sign flip applied.** All metrics use the saved factor scores as-is.",
        "",
        "Conventions audited:",
        "- Q1 is the lowest factor score and Q10 is the highest factor score.",
        "- Long-short return is Q10 minus Q1.",
        "- IC is corr(factor_score_T, future_return_T+1), with no extra sign flip.",
        "",
        _markdown_table(audit),
        "",
        "## Factors Requiring Review",
        "",
    ]
    inconsistent = audit[audit["directions_consistent"] == "no"]
    if inconsistent.empty:
        lines.append("No factors show direction disagreement.")
    for row in inconsistent.to_dict("records"):
        lines.extend(
            [
                f"### {row['factor']}",
                f"- IC sign: {row['ic_sign']}",
                f"- Long-short sign: {row['long_short_sign']}",
                f"- Monotonicity sign: {row['monotonicity_sign']}",
                f"- Plausible explanation: {row['plausible_explanation']}",
                "- Proposed fix: do not flip sign automatically; first re-test after sector neutralization.",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _markdown_table(audit: pd.DataFrame) -> str:
    columns = [
        "factor",
        "mean_ic_1d",
        "ic_sign",
        "long_short_mean_return_1d",
        "long_short_sign",
        "monotonicity",
        "monotonicity_sign",
        "directions_consistent",
    ]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = [_markdown_row(row, columns) for row in audit[columns].to_dict("records")]
    return "\n".join([header, separator, *rows])


def _markdown_row(row: dict[str, object], columns: list[str]) -> str:
    values = []
    for column in columns:
        value = row[column]
        if isinstance(value, float):
            values.append(f"{value:.8f}")
        else:
            values.append(str(value))
    return "| " + " | ".join(values) + " |"


if __name__ == "__main__":
    main()
