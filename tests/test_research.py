"""Unit tests for Pillar 3 single-factor research tools."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.research.fama_macbeth import run_fama_macbeth
from src.research.ic_analysis import compute_ic, compute_ic_timeseries, make_forward_returns
from src.research.quantile_test import (
    compute_long_short_return,
    compute_monotonicity,
    quantile_portfolio_returns,
)
from scripts.run_factor_research import PRICE_FACTOR_NAMES, _select_factor_names, _summary_path


def test_ic_timeseries_positive_normal_case() -> None:
    factor_frame, return_frame = _synthetic_aligned_data()
    ic_table = compute_ic_timeseries(factor_frame, return_frame, periods=[1], already_shifted=True)
    assert ic_table["ic_1d"].dropna().mean() > 0.9
    assert ic_table["n_obs_1d"].max() == 5


def test_quantile_returns_rank_high_factor_above_low_factor() -> None:
    factor_frame, return_frame = _synthetic_aligned_data()
    quantile_returns = quantile_portfolio_returns(factor_frame, return_frame, n_quantiles=5, already_shifted=True)
    long_short = compute_long_short_return(quantile_returns)
    assert long_short.dropna().mean() > 0.0
    assert compute_monotonicity(quantile_returns) > 0.9


def test_fama_macbeth_beta_positive_normal_case() -> None:
    factor_frame, return_frame = _synthetic_aligned_data()
    result = run_fama_macbeth(factor_frame, return_frame, already_shifted=True, nw_lags=1)
    assert result.loc["factor", "coefficient"] > 0.0
    assert result.loc["factor", "n_dates"] > 3


def test_missing_pairs_counted_edge_case() -> None:
    factor_frame, return_frame = _synthetic_aligned_data()
    factor_frame.iloc[0, 0] = np.nan
    return_frame.iloc[1, 0] = np.nan
    ic_table = compute_ic_timeseries(factor_frame, return_frame, periods=[1], already_shifted=True)
    assert ic_table["n_dropped_1d"].max() >= 1


def test_small_cross_section_returns_nan_edge_case() -> None:
    index = pd.MultiIndex.from_product([pd.bdate_range("2024-01-02", periods=4), ["AAA", "BBB"]], names=["date", "ticker"])
    factor_frame = pd.DataFrame({"factor": np.arange(len(index), dtype=float)}, index=index)
    return_frame = pd.DataFrame({"return_1d": np.linspace(0.0, 0.07, len(index))}, index=index)
    ic_table = compute_ic_timeseries(factor_frame, return_frame, periods=[1], already_shifted=True)
    assert ic_table["ic_1d"].isna().all()


def test_failure_cases_raise_clear_errors() -> None:
    factor_frame, return_frame = _synthetic_aligned_data()
    with pytest.raises(ValueError, match="spearman"):
        compute_ic(factor_frame["factor"], return_frame["return_1d"], method="kendall")
    with pytest.raises(TypeError, match="MultiIndex"):
        compute_ic_timeseries(pd.DataFrame({"factor": [1.0, 2.0]}), return_frame)
    with pytest.raises(ValueError, match="return_1d"):
        compute_ic_timeseries(factor_frame, return_frame.drop(columns=["return_1d"]))
    with pytest.raises(ValueError, match="n_quantiles"):
        quantile_portfolio_returns(factor_frame, return_frame, n_quantiles=1)


def test_already_shifted_false_shifts_factor_to_avoid_lookahead() -> None:
    index = pd.MultiIndex.from_product([pd.bdate_range("2024-01-02", periods=4), ["AAA"]], names=["date", "ticker"])
    raw_factor = pd.DataFrame({"factor": [1.0, 2.0, 3.0, 4.0]}, index=index)
    shifted_forward_returns = make_forward_returns(pd.DataFrame({"return_1d": [0.01, 0.02, 0.03, 0.04]}, index=index), period=1)
    shifted_ic_input = compute_ic_timeseries(raw_factor, pd.DataFrame({"return_1d": shifted_forward_returns}, index=index), periods=[1], already_shifted=False)
    unshifted_ic_input = compute_ic_timeseries(raw_factor, pd.DataFrame({"return_1d": shifted_forward_returns}, index=index), periods=[1], already_shifted=True)
    assert shifted_ic_input["n_obs_1d"].iloc[0] < unshifted_ic_input["n_obs_1d"].iloc[0]


def test_price_stage_selects_only_price_based_factors() -> None:
    factor_columns = PRICE_FACTOR_NAMES + ["book_to_market", "roe"]
    factor_frame = pd.DataFrame(columns=factor_columns)
    selected_names = _select_factor_names(factor_frame, stage="price")
    assert selected_names == PRICE_FACTOR_NAMES
    assert _summary_path("price").endswith("factor_summary_price_only.csv")


def _synthetic_aligned_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=8)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    factor_values = np.tile(np.arange(1.0, 6.0), len(dates))
    factor_frame = pd.DataFrame({"factor": factor_values}, index=index)
    return_values = []
    for date_position in range(len(dates)):
        cross_section = np.arange(1.0, 6.0) * 0.01 + date_position * 0.001
        return_values.extend(cross_section)
    return_frame = pd.DataFrame({"return_1d": return_values}, index=index)
    return factor_frame, return_frame
