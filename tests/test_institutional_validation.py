"""Tests for the v2 institutional validation pack."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from scripts.run_institutional_validation import main as run_validation
from scripts.run_institutional_validation import _run_locked_oos_validation
from src.portfolio.factor_interactions import factor_correlation_matrix, orthogonalize_factor, pca_factor_diagnostics, rolling_factor_correlation
from src.research.factor_turnover import rank_autocorrelation, summarize_factor_turnover
from src.research.ic_decay import compute_ic_decay
from src.research.significance import benjamini_hochberg, newey_west_mean_test


def test_ic_decay_weakens_with_short_lived_predictability() -> None:
    dates = pd.bdate_range("2024-01-02", periods=12)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    factor = pd.DataFrame({"factor": np.tile(np.arange(1.0, 6.0), len(dates))}, index=index)
    returns = []
    for date_pos in range(len(dates)):
        sign = 1.0 if date_pos % 2 == 0 else -1.0
        returns.extend(sign * np.arange(1.0, 6.0) * 0.01)
    prices = pd.DataFrame({"return_1d": returns}, index=index)
    decay = compute_ic_decay(factor, prices, periods=[1, 5], nw_lags=1)
    one_day = float(decay.loc[decay["horizon"].eq(1), "ic_mean"].iloc[0])
    five_day = float(decay.loc[decay["horizon"].eq(5), "ic_mean"].iloc[0])
    assert one_day > five_day


def test_newey_west_and_fdr_are_stable() -> None:
    result = newey_west_mean_test(pd.Series([0.01, 0.02, 0.03, 0.02, 0.01]), lags=1)
    assert result["mean"] == pytest.approx(0.018)
    assert result["t_stat"] > 0.0
    adjusted = benjamini_hochberg(pd.Series([0.01, 0.04, 0.03], index=["a", "b", "c"]))
    assert adjusted.loc["a"] == pytest.approx(0.03)
    assert adjusted.loc["b"] == pytest.approx(0.04)
    assert adjusted.loc["c"] == pytest.approx(0.04)


def test_factor_turnover_boundaries() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    stable = pd.DataFrame({"factor": np.tile([1.0, 2.0, 3.0, 4.0], len(dates))}, index=index)
    flipped_values = []
    for pos in range(len(dates)):
        flipped_values.extend([1.0, 2.0, 3.0, 4.0] if pos % 2 == 0 else [4.0, 3.0, 2.0, 1.0])
    flipped = pd.DataFrame({"factor": flipped_values}, index=index)
    assert rank_autocorrelation(stable).dropna().mean() == pytest.approx(1.0)
    assert rank_autocorrelation(flipped).dropna().mean() < 0.0
    assert summarize_factor_turnover(stable, n_quantiles=4)["quantile_turnover_mean"] == pytest.approx(0.0)


def test_pca_and_orthogonalization_outputs() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5)
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    base = np.tile([1.0, 2.0, 3.0, 4.0], len(dates))
    factors = pd.DataFrame({"a": base, "b": base * 2.0, "c": np.tile([4.0, 1.0, 3.0, 2.0], len(dates))}, index=index)
    corr = factor_correlation_matrix(factors)
    pca = pca_factor_diagnostics(factors)
    residual = orthogonalize_factor(factors["b"], factors[["a"]])
    assert corr.loc["a", "b"] == pytest.approx(1.0)
    assert pca["explained_variance_ratio"].iloc[0] > 0.5
    assert residual.dropna().abs().max() < 1e-10


def test_rolling_factor_correlation_is_date_level() -> None:
    dates = pd.bdate_range("2024-01-02", periods=8)
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    factors = pd.DataFrame(
        {
            "a": np.tile([1.0, 2.0, 3.0, 4.0], len(dates)),
            "b": np.tile([1.0, 2.0, 3.0, 4.0], len(dates)),
        },
        index=index,
    )
    rolling = rolling_factor_correlation(factors, "a", "b", window=3)
    assert rolling.shape[0] == len(dates)
    assert rolling.dropna().iloc[-1] == pytest.approx(1.0)


def test_institutional_validation_runner_price_only(tmp_path: Path) -> None:
    dates = pd.bdate_range("2024-01-02", periods=90)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    base = np.tile(np.arange(1.0, 6.0), len(dates))
    factors = pd.DataFrame(
        {
            "momentum_12_1": base,
            "short_term_reversal": -base,
            "week_52_high": base * 0.5,
        },
        index=index,
    )
    returns = np.tile(np.arange(1.0, 6.0) * 0.001, len(dates))
    prices = pd.DataFrame({"return_1d": returns}, index=index)
    factor_path = tmp_path / "factors.parquet"
    price_path = tmp_path / "prices.parquet"
    factors.to_parquet(factor_path)
    prices.to_parquet(price_path)
    config = {
        "factor_file": str(factor_path),
        "price_file": str(price_path),
        "weights_file": str(tmp_path / "missing_weights.parquet"),
        "output_dir": str(tmp_path / "validation"),
        "report_file": str(tmp_path / "institutional_validation.md"),
        "factor_names": list(factors.columns),
        "ic_periods": [1, 5],
        "n_quantiles": 5,
        "nw_lags": 1,
        "train_years": 1,
        "test_years": 1,
        "min_train_days": 20,
        "min_test_days": 20,
        "capacity": {"aum_usd": [1000000], "gross": 1.0, "impact_coefficients": [0.5]},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    assert run_validation(["--config", str(config_path)]) == 0
    output_dir = tmp_path / "validation"
    assert (output_dir / "factor_validation_summary.csv").exists()
    assert (output_dir / "ic_decay.csv").exists()
    assert (output_dir / "quantile_portfolio_returns.csv").exists()
    assert (output_dir / "orthogonalized_factor_diagnostics.csv").exists()
    assert (output_dir / "rolling_factor_correlations.csv").exists()
    assert (output_dir / "locked_factor_oos_windows.csv").exists()
    assert (output_dir / "factor_exposure_timeseries.csv").exists()
    assert (output_dir / "risk_decomposition_summary.csv").exists()
    assert (output_dir / "feature_importance.csv").exists()
    assert (output_dir / "capacity_impact_grid.csv").exists()
    feature_importance = pd.read_csv(output_dir / "feature_importance.csv")
    orthogonal = pd.read_csv(output_dir / "orthogonalized_factor_diagnostics.csv")
    assert {"importance_score", "oos_selected_window_share", "variance_share_abs"} <= set(feature_importance.columns)
    assert {"raw_ic_mean_1d", "orthogonalized_ic_mean_1d", "orthogonalized_ic_retention"} <= set(orthogonal.columns)
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["price_only_default"] is True
    assert "market_cap_ready_subset_restored" in manifest["fundamentals_status"]


def test_locked_oos_uses_train_selected_weights_only() -> None:
    dates = pd.bdate_range("2019-01-02", periods=540)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    index = pd.MultiIndex.from_product([dates, tickers], names=["date", "ticker"])
    cross_section = np.tile(np.arange(1.0, 6.0), len(dates))
    factors = pd.DataFrame({"good": cross_section, "bad": -cross_section}, index=index)
    returns = pd.DataFrame({"return_1d": cross_section * 0.001}, index=index)
    config = {"train_years": 1, "test_years": 1, "min_train_days": 200, "min_test_days": 100}
    oos = _run_locked_oos_validation(factors, returns, config)
    test_rows = oos[oos["split"].eq("test")]
    assert not test_rows.empty
    assert test_rows["locked_weights"].str.contains("good").all()
    assert test_rows["selected_factors"].str.len().min() > 0
