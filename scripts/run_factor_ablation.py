"""Run leave-one-out factor ablation for the Pillar 4 combination layer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.combination import EqualWeightCombiner, build_sign_adjusted_panel
from src.combination.baseline import FactorSpec, backtest_top_bottom_decile
from src.combination.config import load_pillar4_config, specs_for_portfolio


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_pillar4_config(args.config)
    factors = _load_panel(_project_path(config.source_factor_file), "factors")
    prices = _load_panel(_project_path(config.price_file), "prices")
    portfolio = next((item for item in config.portfolios if item.name == args.portfolio), None)
    if portfolio is None:
        raise ValueError(f"Unknown portfolio: {args.portfolio}")
    specs = specs_for_portfolio(config, portfolio)
    rows = run_leave_one_out_ablation(factors, prices, specs, n_quantiles=int(args.n_quantiles))
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "factor_ablation.csv", index=False)
    summary = _summary(frame, args, specs)
    (output_dir / "factor_ablation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "factor_ablation_report.md").write_text(_markdown(summary, frame), encoding="utf-8")
    print(f"Saved factor ablation report to {output_dir}")
    return 0


def run_leave_one_out_ablation(
    factors: pd.DataFrame,
    prices: pd.DataFrame,
    specs: list[FactorSpec],
    *,
    n_quantiles: int = 10,
) -> list[dict[str, object]]:
    """Evaluate full and leave-one-out equal-weight composites."""
    if len(specs) < 3:
        raise ValueError("leave-one-out ablation requires at least three factors.")
    rows = [_evaluate("full", specs, None, factors, prices, n_quantiles)]
    for removed in [spec.name for spec in specs]:
        kept = [spec for spec in specs if spec.name != removed]
        rows.append(_evaluate(f"drop_{removed}", kept, removed, factors, prices, n_quantiles))
    full = rows[0]
    for row in rows:
        row["delta_sharpe_vs_full"] = float(row["annualized_sharpe"]) - float(full["annualized_sharpe"])
        row["delta_return_vs_full"] = float(row["annualized_return"]) - float(full["annualized_return"])
        row["delta_turnover_vs_full"] = float(row["average_daily_turnover"]) - float(full["average_daily_turnover"])
    return rows


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Pillar 4 leave-one-out factor ablation.")
    parser.add_argument("--config", default="config/pillar4_candidate_factors.yaml")
    parser.add_argument("--portfolio", default="baseline_4f_equal_weight")
    parser.add_argument("--output", default="results/factor_ablation")
    parser.add_argument("--n-quantiles", type=int, default=10)
    return parser.parse_args(argv)


def _evaluate(
    scenario: str,
    specs: list[FactorSpec],
    removed_factor: str | None,
    factors: pd.DataFrame,
    prices: pd.DataFrame,
    n_quantiles: int,
) -> dict[str, object]:
    adjusted = build_sign_adjusted_panel(factors, specs)
    composite = EqualWeightCombiner().combine(adjusted)
    result = backtest_top_bottom_decile(composite, prices, n_quantiles=n_quantiles)
    summary = result.summary
    return {
        "scenario": scenario,
        "removed_factor": removed_factor or "",
        "kept_factors": ",".join(spec.name for spec in specs),
        "factor_count": len(specs),
        "start_date": summary["start_date"],
        "end_date": summary["end_date"],
        "n_days": summary["n_days"],
        "annualized_return": summary["annualized_return"],
        "annualized_sharpe": summary["annualized_sharpe"],
        "max_drawdown": summary["max_drawdown"],
        "average_daily_turnover": summary["average_daily_turnover"],
        "hit_rate": summary["hit_rate"],
    }


def _summary(frame: pd.DataFrame, args: argparse.Namespace, specs: list[FactorSpec]) -> dict[str, object]:
    full = frame[frame["scenario"] == "full"].iloc[0]
    drops = frame[frame["scenario"] != "full"].copy()
    best_drop = drops.sort_values("delta_sharpe_vs_full", ascending=False).iloc[0]
    worst_drop = drops.sort_values("delta_sharpe_vs_full", ascending=True).iloc[0]
    return {
        "config": str(args.config),
        "portfolio": str(args.portfolio),
        "factor_names": [spec.name for spec in specs],
        "full_annualized_sharpe": float(full["annualized_sharpe"]),
        "full_annualized_return": float(full["annualized_return"]),
        "full_average_daily_turnover": float(full["average_daily_turnover"]),
        "best_drop_by_sharpe": {
            "removed_factor": str(best_drop["removed_factor"]),
            "delta_sharpe_vs_full": float(best_drop["delta_sharpe_vs_full"]),
            "annualized_sharpe": float(best_drop["annualized_sharpe"]),
        },
        "worst_drop_by_sharpe": {
            "removed_factor": str(worst_drop["removed_factor"]),
            "delta_sharpe_vs_full": float(worst_drop["delta_sharpe_vs_full"]),
            "annualized_sharpe": float(worst_drop["annualized_sharpe"]),
        },
        "interpretation": _interpretation(best_drop, worst_drop),
    }


def _interpretation(best_drop: pd.Series, worst_drop: pd.Series) -> str:
    if float(best_drop["delta_sharpe_vs_full"]) > 0.05:
        return (
            f"Dropping {best_drop['removed_factor']} improves the no-cost combination Sharpe, "
            "so this factor should be reviewed before promotion."
        )
    return (
        f"No leave-one-out removal materially improves Sharpe; {worst_drop['removed_factor']} "
        "appears most important by this no-cost ablation proxy."
    )


def _markdown(summary: dict[str, object], frame: pd.DataFrame) -> str:
    lines = [
        "# Factor Leave-One-Out Ablation",
        "",
        "## Scope",
        "",
        "- This is a Pillar 4 combination-layer diagnostic.",
        "- It uses sign-adjusted equal-weight composites and a no-cost top/bottom decile backtest.",
        "- It is not a replacement for V4 optimizer-level retraining.",
        "",
        "## Summary",
        "",
        f"- Portfolio: `{summary['portfolio']}`",
        f"- Full Sharpe: {summary['full_annualized_sharpe']:.4f}",
        f"- Full annualized return: {summary['full_annualized_return']:.4f}",
        f"- Interpretation: {summary['interpretation']}",
        "",
        "## Ablation Table",
        "",
    ]
    view = frame[
        [
            "scenario",
            "removed_factor",
            "factor_count",
            "annualized_sharpe",
            "delta_sharpe_vs_full",
            "annualized_return",
            "average_daily_turnover",
            "max_drawdown",
        ]
    ]
    lines.extend(_markdown_table(view))
    return "\n".join(lines) + "\n"


def _markdown_table(frame: pd.DataFrame) -> list[str]:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _load_panel(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {name} file: {path}")
    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError(f"{name} must use MultiIndex(date, ticker).")
    frame.index = frame.index.set_names(["date", "ticker"])
    return frame.sort_index()


def _project_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
