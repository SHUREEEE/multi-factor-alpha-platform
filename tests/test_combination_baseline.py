"""Unit tests for Pillar 4 baseline factor combination."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.combination import EqualWeightCombiner, FactorSpec, WeightedCombiner, build_factor_correlation_report, build_sign_adjusted_panel
from src.combination.baseline import backtest_top_bottom_decile
from src.combination.config import load_pillar4_config, specs_from_config


def test_sign_adjusted_panel_flips_negative_factors_and_rezscore() -> None:
    factors = _synthetic_factor_panel()
    specs = [FactorSpec("short_term_reversal", 1), FactorSpec("realized_vol", -1)]
    adjusted = build_sign_adjusted_panel(factors, specs)
    first_date = pd.Timestamp("2024-01-02")
    realized_values = adjusted.xs(first_date, level="date")["realized_vol"]
    assert realized_values.loc["AAA"] > realized_values.loc["DDD"]
    daily_means = adjusted.groupby(level="date").mean()
    assert daily_means.abs().max().max() == pytest.approx(0.0, abs=1e-12)


def test_correlation_report_flags_highly_related_pair() -> None:
    factors = _synthetic_factor_panel()
    specs = [
        FactorSpec("short_term_reversal", 1),
        FactorSpec("idiosyncratic_vol", -1),
        FactorSpec("realized_vol", -1),
        FactorSpec("week_52_high", -1),
    ]
    adjusted = build_sign_adjusted_panel(factors, specs)
    report = build_factor_correlation_report(adjusted, threshold=0.7)
    flagged_pairs = report[report["deduplication_flag"]]
    assert not flagged_pairs.empty
    assert flagged_pairs["abs_average_rank_correlation"].max() > 0.7


def test_equal_weight_backtest_uses_lagged_signal_normal_case() -> None:
    factors = _synthetic_factor_panel(n_dates=8, n_tickers=20)
    adjusted = build_sign_adjusted_panel(
        factors,
        [
            FactorSpec("short_term_reversal", 1),
            FactorSpec("idiosyncratic_vol", -1),
            FactorSpec("realized_vol", -1),
            FactorSpec("week_52_high", -1),
        ],
    )
    composite = EqualWeightCombiner().combine(adjusted)
    prices = _synthetic_prices_from_signal(composite)
    result = backtest_top_bottom_decile(composite, prices, n_quantiles=10)
    assert result.daily_returns["long_short_return"].dropna().mean() > 0.0
    assert result.summary["n_days"] > 0
    assert result.daily_returns["turnover"].dropna().ge(0.0).all()
    assert pd.isna(result.daily_returns["long_short_return"].iloc[0])


def test_yaml_driven_factor_loading() -> None:
    config = load_pillar4_config("config/pillar4_candidate_factors.yaml")
    specs = specs_from_config(config, include_optional=True)
    assert config.source_factor_file == "data/factor_data/factors_sector_neutral.parquet"
    assert [spec.name for spec in specs] == ["short_term_reversal", "idiosyncratic_vol", "realized_vol", "week_52_high"]
    assert [spec.sign for spec in specs] == [1, -1, -1, -1]


def test_weighted_composite_uses_configured_weights() -> None:
    factors = _synthetic_factor_panel(n_dates=5, n_tickers=12)
    adjusted = build_sign_adjusted_panel(
        factors,
        [FactorSpec("short_term_reversal", 1), FactorSpec("realized_vol", -1)],
    )
    weighted = WeightedCombiner({"short_term_reversal": 0.75, "realized_vol": 0.25}).combine(adjusted)
    equal = EqualWeightCombiner().combine(adjusted)
    assert weighted.columns.tolist() == ["composite_alpha_weighted"]
    assert not weighted.equals(equal.rename(columns={"composite_alpha_equal_weight": "composite_alpha_weighted"}))
    assert weighted.groupby(level="date").mean().abs().max().iloc[0] == pytest.approx(0.0, abs=1e-12)


def test_small_cross_section_returns_nan_edge_case() -> None:
    factors = _synthetic_factor_panel(n_dates=4, n_tickers=5)
    adjusted = build_sign_adjusted_panel(
        factors,
        [FactorSpec("short_term_reversal", 1), FactorSpec("realized_vol", -1)],
    )
    composite = EqualWeightCombiner().combine(adjusted)
    prices = _synthetic_prices_from_signal(composite)
    result = backtest_top_bottom_decile(composite, prices, n_quantiles=10)
    assert result.daily_returns["long_short_return"].isna().all()


def test_failure_cases_raise_clear_errors() -> None:
    factors = _synthetic_factor_panel()
    with pytest.raises(ValueError, match="Missing"):
        build_sign_adjusted_panel(factors[["short_term_reversal"]], [FactorSpec("missing_factor", 1)])
    with pytest.raises(ValueError, match="signs"):
        build_sign_adjusted_panel(factors, [FactorSpec("short_term_reversal", 0)])
    with pytest.raises(TypeError, match="DataFrame"):
        EqualWeightCombiner().combine(pd.Series([1.0, 2.0]))
    with pytest.raises(ValueError, match="missing factor"):
        WeightedCombiner({"missing factor": 1.0}).combine(factors)


def _synthetic_factor_panel(n_dates: int = 5, n_tickers: int = 12) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    tickers = [f"T{ticker_number:02d}" for ticker_number in range(n_tickers)]
    tickers[:4] = ["AAA", "BBB", "CCC", "DDD"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    base_rank = np.tile(np.arange(1.0, n_tickers + 1.0), n_dates)
    return pd.DataFrame(
        {
            "short_term_reversal": base_rank,
            "idiosyncratic_vol": base_rank + 0.1,
            "realized_vol": base_rank,
            "week_52_high": -base_rank[::-1],
        },
        index=index,
    )


def _synthetic_prices_from_signal(composite: pd.DataFrame) -> pd.DataFrame:
    lagged_signal = composite.iloc[:, 0].unstack("ticker").shift(1)
    next_day_return = lagged_signal.rank(axis=1, pct=True).fillna(0.5) * 0.02 - 0.01
    long_returns = next_day_return.rename_axis(index="date", columns="ticker").stack()
    return pd.DataFrame({"return_1d": long_returns.astype(float)}, index=long_returns.index)
