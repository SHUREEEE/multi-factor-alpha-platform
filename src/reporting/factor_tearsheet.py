"""Factor tearsheet generation for Pillar 3 research reports."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.research.fama_macbeth import run_fama_macbeth
from src.research.ic_analysis import compute_ic_timeseries, summarize_ic
from src.research.quantile_test import compute_long_short_return, compute_monotonicity, quantile_portfolio_returns


def generate_tearsheet(
    factor_name: str,
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    output_dir: str | Path,
    already_shifted: bool = True,
    ic_table: pd.DataFrame | None = None,
    quantile_returns: pd.DataFrame | None = None,
    long_short_returns: pd.Series | None = None,
    fama_macbeth: pd.DataFrame | None = None,
) -> Path:
    """Generate and save a six-panel factor tearsheet.

    Parameters
    ----------
    factor_name:
        Human-readable factor name used in the chart title and filename.
    factor_df:
        Single-factor panel indexed by ``(date, ticker)``.
    return_df:
        Daily return panel or price frame containing ``return_1d``.
    output_dir:
        Directory where the PNG report will be saved.
    already_shifted:
        If ``False``, shift factor values before all tests.
    ic_table:
        Optional precomputed IC table used by batch research scripts.
    quantile_returns:
        Optional precomputed quantile returns used by batch research scripts.
    long_short_returns:
        Optional precomputed top-minus-bottom returns.
    fama_macbeth:
        Optional precomputed Fama-MacBeth result.

    Returns
    -------
    pathlib.Path
        Saved PNG path.
    """
    clean_name = _validate_factor_name(factor_name)
    output_path = Path(output_dir) / f"{clean_name}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ic_table = ic_table if ic_table is not None else compute_ic_timeseries(factor_df, return_df, already_shifted=already_shifted)
    quantile_returns = quantile_returns if quantile_returns is not None else quantile_portfolio_returns(factor_df, return_df, already_shifted=already_shifted)
    long_short_returns = long_short_returns if long_short_returns is not None else compute_long_short_return(quantile_returns)
    fama_macbeth = fama_macbeth if fama_macbeth is not None else run_fama_macbeth(factor_df, return_df, already_shifted=already_shifted)
    figure, axes = plt.subplots(3, 2, figsize=(16, 14), constrained_layout=True)
    _plot_cumulative_ic(axes[0, 0], ic_table)
    _plot_ic_histogram(axes[0, 1], ic_table)
    _plot_quantile_cumulative_returns(axes[1, 0], quantile_returns)
    _plot_long_short_returns(axes[1, 1], long_short_returns)
    _plot_ic_decay(axes[2, 0], ic_table)
    _plot_summary_table(axes[2, 1], ic_table, quantile_returns, long_short_returns, fama_macbeth)
    figure.suptitle(f"{factor_name} Single-Factor Research Tearsheet", fontsize=16)
    figure.text(0.5, 0.01, "Bias note: Yahoo/free-data universe may contain survivorship bias; results are for research education.", ha="center", fontsize=9)
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return output_path


def _plot_cumulative_ic(axis: plt.Axes, ic_table: pd.DataFrame) -> None:
    ic_columns = [column for column in ic_table.columns if column.startswith("ic_")]
    primary_ic = ic_table[ic_columns[0]].dropna() if ic_columns else pd.Series(dtype=float)
    primary_ic.cumsum().plot(ax=axis, color="#1f77b4", linewidth=1.5)
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_title("Panel 1: Cumulative 1D IC")
    axis.set_ylabel("Cumulative IC")


def _plot_ic_histogram(axis: plt.Axes, ic_table: pd.DataFrame) -> None:
    primary_ic = ic_table["ic_1d"].dropna() if "ic_1d" in ic_table else pd.Series(dtype=float)
    axis.hist(primary_ic, bins=30, color="#4c78a8", alpha=0.8)
    axis.axvline(primary_ic.mean() if not primary_ic.empty else 0.0, color="#d62728", linewidth=1.5)
    axis.set_title("Panel 2: 1D IC Distribution")
    axis.set_xlabel("IC")


def _plot_quantile_cumulative_returns(axis: plt.Axes, quantile_returns: pd.DataFrame) -> None:
    cumulative_returns = (1.0 + quantile_returns.fillna(0.0)).cumprod() - 1.0
    selected_columns = [quantile_returns.columns[0], quantile_returns.columns[-1]]
    cumulative_returns[selected_columns].plot(ax=axis, linewidth=1.5)
    axis.set_title("Panel 3: Quantile Cumulative Returns")
    axis.set_ylabel("Cumulative return")


def _plot_long_short_returns(axis: plt.Axes, long_short_returns: pd.Series) -> None:
    cumulative_returns = (1.0 + long_short_returns.fillna(0.0)).cumprod() - 1.0
    cumulative_returns.plot(ax=axis, color="#2ca02c", linewidth=1.5)
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_title("Panel 4: Long-Short Cumulative Return")
    axis.set_ylabel("Cumulative return")


def _plot_ic_decay(axis: plt.Axes, ic_table: pd.DataFrame) -> None:
    decay_values = {column.replace("ic_", ""): ic_table[column].mean(skipna=True) for column in ic_table.columns if column.startswith("ic_")}
    pd.Series(decay_values).plot(kind="bar", ax=axis, color="#9467bd")
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_title("Panel 5: IC Decay")
    axis.set_ylabel("Mean IC")


def _plot_summary_table(
    axis: plt.Axes,
    ic_table: pd.DataFrame,
    quantile_returns: pd.DataFrame,
    long_short_returns: pd.Series,
    fama_macbeth: pd.DataFrame,
) -> None:
    axis.axis("off")
    ic_summary = summarize_ic(ic_table["ic_1d"]) if "ic_1d" in ic_table else {}
    fm_t_stat = fama_macbeth.loc["factor", "t_stat"] if "factor" in fama_macbeth.index else np.nan
    summary_rows = [
        ["Mean IC", _format_number(ic_summary.get("mean_ic"))],
        ["IC IR", _format_number(ic_summary.get("ic_ir"))],
        ["IC t-stat", _format_number(ic_summary.get("t_stat"))],
        ["Hit rate", _format_number(ic_summary.get("hit_rate"))],
        ["Monotonicity", _format_number(compute_monotonicity(quantile_returns))],
        ["FM t-stat", _format_number(fm_t_stat)],
        ["LS mean", _format_number(long_short_returns.mean(skipna=True))],
    ]
    axis.table(cellText=summary_rows, colLabels=["Metric", "Value"], loc="center", cellLoc="center")
    axis.set_title("Panel 6: Summary Statistics")


def _format_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "NaN"
    return f"{float(value):.4f}"


def _validate_factor_name(factor_name: str) -> str:
    if not isinstance(factor_name, str) or not factor_name.strip():
        raise ValueError("factor_name must be a non-empty string.")
    return factor_name.strip().replace(" ", "_")
