"""Information coefficient decay and rolling diagnostics."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from src.research.ic_analysis import compute_ic_timeseries, summarize_ic
from src.research.significance import newey_west_mean_test


DEFAULT_DECAY_PERIODS = [1, 5, 10, 21, 63]


def compute_ic_decay(
    factor_df: pd.DataFrame | pd.Series,
    return_df: pd.DataFrame | pd.Series,
    periods: Iterable[int] = DEFAULT_DECAY_PERIODS,
    *,
    method: str = "spearman",
    already_shifted: bool = True,
    nw_lags: int = 5,
) -> pd.DataFrame:
    """Summarize IC strength across forward-return horizons."""
    ic_table = compute_ic_timeseries(factor_df, return_df, periods=periods, method=method, already_shifted=already_shifted)
    rows = []
    for period in [int(period) for period in periods]:
        column = f"ic_{period}d"
        summary = summarize_ic(ic_table[column])
        hac = newey_west_mean_test(ic_table[column], lags=nw_lags)
        rows.append(
            {
                "horizon": period,
                "ic_mean": summary["mean_ic"],
                "ic_std": summary["ic_std"],
                "ic_ir": summary["ic_ir"],
                "ic_tstat": hac["t_stat"],
                "ic_p_value": hac["p_value"],
                "hit_rate": summary["hit_rate"],
                "n_obs": summary["n_obs"],
            }
        )
    output = pd.DataFrame(rows)
    output["decay_ratio_vs_1d"] = output["ic_mean"] / output.loc[output["horizon"].eq(1), "ic_mean"].replace(0.0, np.nan).iloc[0]
    return output


def rolling_ic_summary(ic_series: pd.Series, windows: Iterable[int] = (63, 126, 252)) -> pd.DataFrame:
    """Compute rolling IC means and hit rates for multiple windows."""
    if not isinstance(ic_series, pd.Series):
        raise TypeError("ic_series must be a pandas Series.")
    clean = ic_series.replace([np.inf, -np.inf], np.nan).astype(float)
    parts = []
    for window in [int(value) for value in windows]:
        if window < 2:
            raise ValueError("rolling windows must be at least 2.")
        parts.append(clean.rolling(window, min_periods=max(3, window // 2)).mean().rename(f"rolling_mean_{window}d"))
        parts.append(clean.rolling(window, min_periods=max(3, window // 2)).apply(lambda values: float((values > 0.0).mean()), raw=True).rename(f"rolling_hit_rate_{window}d"))
    return pd.concat(parts, axis=1)
