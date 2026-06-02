"""Build Pillar 4 sign-adjusted factors and equal-weight baseline portfolio."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.combination import EqualWeightCombiner, FactorSpec, build_factor_correlation_report, build_sign_adjusted_panel  # noqa: E402
from src.combination.baseline import BaselineBacktestResult, backtest_top_bottom_decile  # noqa: E402
from src.combination.config import Pillar4Config, load_pillar4_config, specs_from_config  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config/pillar4_candidate_factors.yaml"
PILLAR4_INPUT_PATH = PROJECT_ROOT / "data/factor_data/factors_pillar4_inputs.parquet"
CORRELATION_REPORT_PATH = PROJECT_ROOT / "reports/pillar4_factor_correlations.csv"
BACKTEST_OUTPUT_PATH = PROJECT_ROOT / "results/pillar4_equal_weight_backtest.csv"
SUMMARY_REPORT_PATH = PROJECT_ROOT / "reports/pillar4_baseline_summary.md"


def main() -> None:
    """Run the complete Pillar 4 baseline workflow."""
    config = load_pillar4_config(CONFIG_PATH)
    factor_specs = specs_from_config(config, include_optional=config.include_optional_default)
    factors = _load_factors(_project_path(config.source_factor_file), factor_specs)
    prices = _load_prices(_project_path(config.price_file))
    adjusted_factors = build_sign_adjusted_panel(factors, factor_specs)
    _save_parquet(adjusted_factors, PILLAR4_INPUT_PATH)
    correlations = build_factor_correlation_report(adjusted_factors)
    _save_csv(correlations, CORRELATION_REPORT_PATH)
    composite = EqualWeightCombiner().combine(adjusted_factors)
    backtest = backtest_top_bottom_decile(composite, prices, n_quantiles=10)
    _save_csv(backtest.daily_returns, BACKTEST_OUTPUT_PATH, include_index=True)
    SUMMARY_REPORT_PATH.write_text(_build_summary_report(config, factor_specs, adjusted_factors, correlations, backtest), encoding="utf-8")
    _print_outputs(backtest)


def _load_factors(path: Path, factor_specs: list[FactorSpec]) -> pd.DataFrame:
    """Load sector-neutral factors and verify required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Missing sector-neutral factor file: {path.as_posix()}")
    factors = pd.read_parquet(path)
    _validate_multiindex(factors, "factors")
    missing_names = sorted(set(_factor_names(factor_specs)) - set(factors.columns))
    if missing_names:
        raise ValueError(f"Missing Pillar 4 factors: {missing_names}")
    return factors.sort_index()


def _load_prices(path: Path) -> pd.DataFrame:
    """Load daily returns used by the baseline portfolio backtest."""
    if not path.exists():
        raise FileNotFoundError(f"Missing processed price file: {path.as_posix()}")
    prices = pd.read_parquet(path)
    _validate_multiindex(prices, "prices")
    if "return_1d" not in prices.columns:
        raise ValueError("prices must contain return_1d.")
    return prices.sort_index()


def _validate_multiindex(frame: pd.DataFrame, name: str) -> None:
    """Validate the standard project panel index contract."""
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError(f"{name} must use MultiIndex(date, ticker).")
    frame.index = frame.index.set_names(["date", "ticker"])
    if frame.index.has_duplicates:
        raise ValueError(f"{name} contains duplicate (date, ticker) rows.")


def _save_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Save a parquet file after creating its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, compression="snappy", index=True)
    print(f"Saved {path.as_posix()}")


def _save_csv(frame: pd.DataFrame, path: Path, include_index: bool = False) -> None:
    """Save a CSV file after creating its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=include_index)
    print(f"Saved {path.as_posix()}")


def _project_path(path_text: str) -> Path:
    """Resolve a config path relative to the project root."""
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _factor_names(factor_specs: list[FactorSpec]) -> list[str]:
    """Return the fixed Stage 4.1 factor universe."""
    return [spec.name for spec in factor_specs]


def _build_summary_report(
    config: Pillar4Config,
    factor_specs: list[FactorSpec],
    adjusted_factors: pd.DataFrame,
    correlations: pd.DataFrame,
    backtest: BaselineBacktestResult,
) -> str:
    """Render a compact Markdown report for the baseline portfolio."""
    coverage = adjusted_factors.notna().mean().rename("non_null_ratio")
    flagged = correlations[correlations["deduplication_flag"]]
    lines = [
        "# Pillar 4 Baseline Equal-Weight Composite",
        "",
        "## Design",
        f"- Inputs come from `{config.source_factor_file}`.",
        f"- Baseline version is `baseline_4f`; `include_optional_default` is `{config.include_optional_default}`.",
        "- Negative-signal factors are multiplied by `-1`, then each factor is re-zscored by date.",
        "- Composite signal is the equal-weight mean of the four adjusted factors, then re-zscored by date.",
        "- Portfolio is long top decile and short bottom decile, equal-weighted, rebalanced daily.",
        "- Trading uses a 1-day lag: holdings on date T use the composite signal from T-1.",
        "- No transaction costs and no optimized weights are included in this baseline.",
        "",
        "## Factor Universe",
        _factor_table(factor_specs),
        "",
        "## Coverage",
        _markdown_table(coverage.to_frame().reset_index(names="factor")),
        "",
        "## Correlation Flags",
        _format_flags(flagged),
        "",
        "## Backtest Summary",
        _summary_table(backtest.summary),
        "",
        "## Data Limitation",
        "Yahoo/free-data universes can contain survivorship bias; treat this baseline as research infrastructure, not live-trading evidence.",
        "",
    ]
    return "\n".join(lines)


def _factor_table(factor_specs: list[FactorSpec]) -> str:
    """Create a Markdown table documenting factor signs."""
    rows = [{"factor": spec.name, "sign": spec.sign, "interpretation": "higher score = expected higher return"} for spec in factor_specs]
    return _markdown_table(pd.DataFrame(rows))


def _format_flags(flagged: pd.DataFrame) -> str:
    """Render de-duplication warnings for highly correlated factor pairs."""
    if flagged.empty:
        return "No pair has absolute average rank correlation above 0.70."
    return _markdown_table(flagged)


def _summary_table(summary: dict[str, float | int | str]) -> str:
    """Render summary metrics as a two-column Markdown table."""
    rows = [{"metric": key, "value": value} for key, value in summary.items()]
    return _markdown_table(pd.DataFrame(rows))


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small Markdown table without optional dependencies."""
    text_frame = frame.astype(str)
    header = "| " + " | ".join(text_frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_frame.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text_frame.to_numpy()]
    return "\n".join([header, separator, *rows])


def _print_outputs(backtest: BaselineBacktestResult) -> None:
    """Print the key metrics needed for a quick terminal check."""
    print("\nPillar 4 baseline complete.")
    for key, value in backtest.summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
