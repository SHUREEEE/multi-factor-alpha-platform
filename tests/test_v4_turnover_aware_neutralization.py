"""Tests for V4 turnover-aware neutralization.

Covers: REQ-F-001.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.optimization import sector_net_exposure, solve_sector_net_weights, solve_turnover_aware_weights


def test_turnover_aware_solver_reduces_turnover_vs_sector_only_path() -> None:
    raw = pd.Series({"AAA": 0.9, "BBB": 0.1, "CCC": -0.1, "DDD": -0.9})
    prior = pd.Series({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5})
    betas = pd.Series({"AAA": 1.0, "BBB": 1.1, "CCC": 0.9, "DDD": 1.2})
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})

    sector_only = solve_sector_net_weights(raw, sectors, sector_net_cap=0.20, gross_target=2.0)
    turnover_aware = solve_turnover_aware_weights(
        raw,
        prior,
        betas,
        sectors,
        sector_net_cap=0.20,
        gross_target=2.0,
        turnover_penalty=4.0,
        no_trade_band_bps=0.0,
        short_top10_cap=0.25,
        single_short_cap=0.05,
    )

    assert (turnover_aware - prior).abs().sum() <= 0.5 * (sector_only - prior).abs().sum()
    assert sector_net_exposure(turnover_aware, sectors).abs().max() <= 0.20 + 1e-12


def test_turnover_aware_solver_records_solver_path() -> None:
    raw = pd.Series({"AAA": 0.9, "BBB": 0.1, "CCC": -0.1, "DDD": -0.9})
    prior = pd.Series({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5})
    betas = pd.Series({"AAA": 1.0, "BBB": 1.1, "CCC": 0.9, "DDD": 1.2})
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})

    result = solve_turnover_aware_weights(
        raw,
        prior,
        betas,
        sectors,
        sector_net_cap=0.20,
        gross_target=2.0,
        turnover_penalty=1.0,
        no_trade_band_bps=0.0,
        short_top10_cap=0.25,
        single_short_cap=0.05,
    )

    assert result.attrs["solver_path"] in {"cvxpy", "projection"}


def test_no_trade_band_keeps_small_changes_at_prior_weights() -> None:
    raw = pd.Series({"AAA": 0.505, "BBB": 0.495, "CCC": -0.505, "DDD": -0.495})
    prior = pd.Series({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5})
    betas = pd.Series({"AAA": 1.0, "BBB": 1.1, "CCC": 0.9, "DDD": 1.2})
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})

    result = solve_turnover_aware_weights(
        raw,
        prior,
        betas,
        sectors,
        sector_net_cap=1.0,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=100.0,
        short_top10_cap=0.25,
        single_short_cap=0.05,
    )

    assert (result - prior.astype(float)).abs().max() < 1e-8


def test_builder_uses_prior_weights_and_reports_turnover() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2, name="date")
    raw = pd.DataFrame(
        {
            "AAA": [0.5, 0.9],
            "BBB": [0.5, 0.1],
            "CCC": [-0.5, -0.1],
            "DDD": [-0.5, -0.9],
        },
        index=dates,
    )
    prior = pd.DataFrame(
        {
            "AAA": [0.5, 0.5],
            "BBB": [0.5, 0.5],
            "CCC": [-0.5, -0.5],
            "DDD": [-0.5, -0.5],
        },
        index=dates,
    )
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        prior_weights=prior,
    )
    config = V4Config(sector_net_cap=0.20, gross_target=2.0, turnover_penalty=4.0, no_trade_band_bps=0.0)

    result = build_v4_weights(inputs, config)

    assert "REQ-F-001" in result.manifest["implemented_requirements"]
    assert result.diagnostics.loc[dates[1], "turnover"] < 1.6
    assert result.diagnostics["max_abs_sector_net"].max() <= 0.20 + 1e-12
