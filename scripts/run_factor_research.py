"""Run Pillar 3 single-factor research across all saved factors."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.factor_tearsheet import generate_tearsheet  # noqa: E402
from src.research.fama_macbeth import run_fama_macbeth  # noqa: E402
from src.research.ic_analysis import compute_ic_timeseries, summarize_ic  # noqa: E402
from src.research.quantile_test import (  # noqa: E402
    compute_annualized_sharpe,
    compute_long_short_return,
    compute_monotonicity,
    detect_monotonic_direction,
    quantile_portfolio_returns,
)


PRICE_FACTOR_NAMES = [
    "momentum_12_1",
    "short_term_reversal",
    "week_52_high",
    "idiosyncratic_vol",
    "beta_inverse",
    "realized_vol",
]
FUNDAMENTAL_FACTOR_NAMES = [
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
    """Run selected single-factor diagnostics and save a ranked summary."""
    args = _parse_args()
    factors = _load_factors(_resolve_project_path(args.factor_file))
    prices = _load_prices(PROJECT_ROOT / "data/processed/prices.parquet")
    factor_names = _select_factor_names(factors, args.stage)
    output_path = PROJECT_ROOT / _summary_path(args.stage, args.output_prefix)
    tearsheet_dir = PROJECT_ROOT / "results/factor_tearsheets" / _stage_directory(args.stage, args.output_prefix)
    print(f"Stage: {args.stage}")
    print(f"Factors: {', '.join(factor_names)}")
    summary_rows = [_research_one_factor(name, factors[[name]], prices, tearsheet_dir, args.include_fama_macbeth) for name in factor_names]
    summary = pd.DataFrame(summary_rows).sort_values("abs_ic_ir_1d", ascending=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    print(f"Saved factor summary to {output_path.as_posix()}")
    _print_promising_candidates(summary)
    print("\nBias note: Yahoo/free-data universe can contain survivorship bias.")


def _parse_args() -> Namespace:
    parser = ArgumentParser(description="Run Pillar 3 single-factor research.")
    parser.add_argument(
        "--stage",
        choices=["price", "fundamental", "full"],
        default="price",
        help="Research stage to run. Default is price because current fundamentals are not yet reliable.",
    )
    parser.add_argument(
        "--include-fama-macbeth",
        action="store_true",
        help="Also run Fama-MacBeth regressions. Price-stage smoke tests skip this by default for speed.",
    )
    parser.add_argument(
        "--factor-file",
        default="data/factor_data/all_factors.parquet",
        help="Factor parquet path relative to project root, or an absolute path.",
    )
    parser.add_argument(
        "--output-prefix",
        default="",
        help="Optional suffix added to summary filename and tearsheet directory.",
    )
    return parser.parse_args()


def _load_factors(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing factor file: {path.as_posix()}")
    factors = pd.read_parquet(path)
    if not isinstance(factors.index, pd.MultiIndex):
        raise ValueError("all_factors.parquet must use MultiIndex(date, ticker).")
    factors.index = factors.index.set_names(["date", "ticker"])
    return factors.sort_index()


def _load_prices(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing price file: {path.as_posix()}")
    prices = pd.read_parquet(path)
    if not isinstance(prices.index, pd.MultiIndex):
        raise ValueError("prices.parquet must use MultiIndex(date, ticker).")
    if "return_1d" not in prices.columns:
        raise ValueError("prices.parquet must contain return_1d.")
    prices.index = prices.index.set_names(["date", "ticker"])
    return prices.sort_index()


def _select_factor_names(factors: pd.DataFrame, stage: str) -> list[str]:
    if stage == "price":
        requested_names = PRICE_FACTOR_NAMES
    elif stage == "fundamental":
        requested_names = FUNDAMENTAL_FACTOR_NAMES
    elif stage == "full":
        requested_names = list(factors.columns)
    else:
        raise ValueError("stage must be one of: price, fundamental, full.")
    missing_names = sorted(set(requested_names) - set(factors.columns))
    if missing_names:
        raise ValueError(f"Missing factors for stage {stage}: {missing_names}")
    return list(requested_names)


def _resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _summary_path(stage: str, output_prefix: str = "") -> str:
    suffix = f"_{output_prefix.strip('_')}" if output_prefix else ""
    if stage == "price":
        return f"results/factor_summary_price_only{suffix}.csv"
    if stage == "fundamental":
        return f"results/factor_summary_fundamental{suffix}.csv"
    return f"results/factor_summary{suffix}.csv"


def _stage_directory(stage: str, output_prefix: str = "") -> str:
    return f"{stage}_{output_prefix.strip('_')}" if output_prefix else stage


def _research_one_factor(
    factor_name: str,
    factor_frame: pd.DataFrame,
    prices: pd.DataFrame,
    tearsheet_dir: Path,
    include_fama_macbeth: bool,
) -> dict[str, float | str | bool]:
    print(f"Researching {factor_name}")
    ic_table = compute_ic_timeseries(factor_frame, prices, already_shifted=True)
    quantile_returns = quantile_portfolio_returns(factor_frame, prices, already_shifted=True)
    long_short_returns = compute_long_short_return(quantile_returns)
    fama_macbeth = _maybe_run_fama_macbeth(factor_frame, prices, include_fama_macbeth)
    tearsheet_path = generate_tearsheet(
        factor_name,
        factor_frame,
        prices,
        tearsheet_dir,
        already_shifted=True,
        ic_table=ic_table,
        quantile_returns=quantile_returns,
        long_short_returns=long_short_returns,
        fama_macbeth=fama_macbeth,
    )
    print(f"Saved tearsheet to {tearsheet_path.as_posix()}")
    return _build_summary_row(factor_name, ic_table, quantile_returns, long_short_returns, fama_macbeth)


def _maybe_run_fama_macbeth(factor_frame: pd.DataFrame, prices: pd.DataFrame, include_fama_macbeth: bool) -> pd.DataFrame:
    if include_fama_macbeth:
        return run_fama_macbeth(factor_frame, prices, already_shifted=True)
    return pd.DataFrame(
        {"coefficient": [np.nan], "t_stat": [np.nan], "p_value": [np.nan], "n_dates": [0.0]},
        index=pd.Index(["factor"], name="variable"),
    )


def _build_summary_row(
    factor_name: str,
    ic_table: pd.DataFrame,
    quantile_returns: pd.DataFrame,
    long_short_returns: pd.Series,
    fama_macbeth: pd.DataFrame,
) -> dict[str, float | str | bool]:
    ic_1d = summarize_ic(ic_table["ic_1d"])
    ic_5d = summarize_ic(ic_table["ic_5d"])
    ic_21d = summarize_ic(ic_table["ic_21d"])
    long_short_sharpe = compute_annualized_sharpe(long_short_returns)
    monotonic_direction = detect_monotonic_direction(quantile_returns)
    direction_adjusted_sharpe = _direction_adjusted_sharpe(ic_1d["mean_ic"], long_short_sharpe)
    return {
        "factor_name": factor_name,
        "ic_mean_1d": ic_1d["mean_ic"],
        "ic_ir_1d": ic_1d["ic_ir"],
        "ic_tstat_1d": ic_1d["t_stat"],
        "ic_hit_rate_1d": ic_1d["hit_rate"],
        "ic_mean_5d": ic_5d["mean_ic"],
        "ic_ir_5d": ic_5d["ic_ir"],
        "ic_mean_21d": ic_21d["mean_ic"],
        "ic_ir_21d": ic_21d["ic_ir"],
        "abs_ic_ir_1d": abs(float(ic_1d["ic_ir"])) if not pd.isna(ic_1d["ic_ir"]) else np.nan,
        "long_short_sharpe": long_short_sharpe,
        "direction_adjusted_ls_sharpe": direction_adjusted_sharpe,
        "monotonicity": compute_monotonicity(quantile_returns),
        "monotonic_direction": monotonic_direction,
        "fama_macbeth_coef": _fm_value(fama_macbeth, "coefficient"),
        "fama_macbeth_tstat": _fm_value(fama_macbeth, "t_stat"),
        "promising_candidate": _is_promising(ic_1d, direction_adjusted_sharpe, monotonic_direction),
    }


def _direction_adjusted_sharpe(mean_ic: object, long_short_sharpe: float) -> float:
    if pd.isna(mean_ic) or pd.isna(long_short_sharpe):
        return float("nan")
    return float(np.sign(float(mean_ic)) * long_short_sharpe)


def _fm_value(fama_macbeth: pd.DataFrame, column: str) -> float:
    if "factor" not in fama_macbeth.index or column not in fama_macbeth.columns:
        return float("nan")
    return float(fama_macbeth.loc["factor", column])


def _is_promising(ic_summary: dict[str, object], direction_adjusted_sharpe: float, monotonic_direction: str) -> bool:
    mean_ic = float(ic_summary["mean_ic"]) if not pd.isna(ic_summary["mean_ic"]) else np.nan
    ic_ir = float(ic_summary["ic_ir"]) if not pd.isna(ic_summary["ic_ir"]) else np.nan
    return bool(abs(mean_ic) > 0.02 and abs(ic_ir) > 0.3 and direction_adjusted_sharpe > 0.5 and monotonic_direction != "none")


def _print_promising_candidates(summary: pd.DataFrame) -> None:
    promising = summary[summary["promising_candidate"]]
    if promising.empty:
        print("Promising candidates: none")
        return
    columns = ["factor_name", "ic_mean_1d", "ic_ir_1d", "long_short_sharpe"]
    print("Promising candidates:")
    print(promising[columns].to_string(index=False))


if __name__ == "__main__":
    main()
