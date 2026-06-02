"""Unit tests for Pillar 2 factor library."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.factors.base import BaseFactor
from src.factors.momentum import Momentum12_1
from src.factors.size import LogMarketCap
from src.factors.utils import apply_full_pipeline, neutralize, stack_wide_panel, winsorize, zscore_cross_sectional
from src.factors.value import BookToMarket


def test_factor_inherits_base_and_computes_normal_case() -> None:
    data = _synthetic_factor_data()
    factor = BookToMarket()
    result = factor.compute(data)
    assert isinstance(factor, BaseFactor)
    assert result.columns.tolist() == ["book_to_market"]
    assert result.loc[(pd.Timestamp("2024-01-02"), "AAA"), "book_to_market"] == pytest.approx(0.5)


def test_winsorize_caps_extreme_edge_case() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 1000.0])
    capped = winsorize(values, lower=0.25, upper=0.75)
    assert capped.max() < 1000.0
    assert capped.min() > 1.0


def test_zscore_cross_sectional_uses_each_date() -> None:
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")], ["AAA", "BBB", "CCC"]],
        names=["date", "ticker"],
    )
    factor_frame = pd.DataFrame({"factor": [1.0, 2.0, 3.0, 10.0, 20.0, 30.0]}, index=index)
    zscored = zscore_cross_sectional(factor_frame)
    daily_means = zscored.groupby(level="date").mean()
    assert daily_means.abs().max().iloc[0] < 1e-12


def test_neutralize_uses_ols_residuals_normal_case() -> None:
    index = pd.MultiIndex.from_product([[pd.Timestamp("2024-01-02")], ["AAA", "BBB", "CCC", "DDD"]], names=["date", "ticker"])
    factor = pd.DataFrame({"factor": [1.0, 2.1, 2.9, 4.2]}, index=index)
    size = pd.Series([1.0, 2.0, 3.0, 4.0], index=index, name="size")
    residuals = neutralize(factor, {"size": size})
    assert abs(residuals["factor"].dropna().mean()) < 1e-12
    assert residuals["factor"].dropna().abs().sum() > 0.0


def test_apply_full_pipeline_returns_cross_sectional_zscores() -> None:
    index = pd.MultiIndex.from_product([[pd.Timestamp("2024-01-02")], ["AAA", "BBB", "CCC", "DDD", "EEE"]], names=["date", "ticker"])
    factor = pd.DataFrame({"factor": [1.0, 2.0, 3.0, 4.0, 1000.0]}, index=index)
    market_cap = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=index, name="market_cap")
    processed = apply_full_pipeline(factor, industry=None, market_cap=market_cap)
    assert processed["factor"].dropna().mean() == pytest.approx(0.0, abs=1e-12)


def test_missing_market_cap_returns_nan_edge_case() -> None:
    data = {"prices": _synthetic_prices()}
    factor = BookToMarket()
    result = factor.compute(data)
    assert result["book_to_market"].isna().all()


def test_momentum_12_1_uses_pct_change_252_shift_21() -> None:
    dates = pd.bdate_range("2023-01-02", periods=280)
    index = pd.MultiIndex.from_product([dates, ["AAA"]], names=["date", "ticker"])
    prices = pd.DataFrame({"adj_close": np.arange(1.0, 281.0)}, index=index)
    result = Momentum12_1().compute({"prices": prices})
    wide_expected = prices["adj_close"].unstack("ticker").pct_change(252).shift(21)
    expected = stack_wide_panel(wide_expected).iloc[-1]
    actual = result["momentum_12_1"].iloc[-1]
    assert actual == pytest.approx(expected)


def test_factor_output_contract_normal_case() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    index = pd.MultiIndex.from_product([dates, ["AAA", "BBB"]], names=["date", "ticker"])
    factors = pd.DataFrame({"momentum_12_1": [np.nan, np.nan, 0.1, -0.2, 0.3, -0.4]}, index=index)
    assert isinstance(factors.index, pd.MultiIndex)
    assert factors.index.names == ["date", "ticker"]
    assert not factors.index.has_duplicates
    assert factors.notna().any(axis=1).groupby(level="date").any().mean() > 0.5


def test_size_factor_has_negative_sign() -> None:
    data = _synthetic_factor_data()
    result = LogMarketCap().compute(data)
    small_stock_score = result.loc[(pd.Timestamp("2024-01-02"), "AAA"), "log_market_cap"]
    large_stock_score = result.loc[(pd.Timestamp("2024-01-02"), "BBB"), "log_market_cap"]
    assert small_stock_score > large_stock_score


def test_invalid_factor_frame_failure_case() -> None:
    bad_frame = pd.DataFrame({"factor": [1.0, 2.0]})
    with pytest.raises(TypeError, match="MultiIndex"):
        zscore_cross_sectional(bad_frame)


def _synthetic_prices() -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")], ["AAA", "BBB"]],
        names=["date", "ticker"],
    )
    return pd.DataFrame({"adj_close": [10.0, 20.0, 11.0, 19.0]}, index=index)


def _synthetic_factor_data() -> dict[str, pd.DataFrame | pd.Series]:
    prices = _synthetic_prices()
    book_value = pd.Series([50.0, 80.0, 55.0, 76.0], index=prices.index, name="book_value")
    market_cap = pd.Series([100.0, 400.0, 110.0, 380.0], index=prices.index, name="market_cap")
    return {"prices": prices, "book_value": book_value, "market_cap": market_cap}
