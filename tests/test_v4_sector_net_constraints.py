"""Tests for V4 sector-net constrained optimization.

Covers: REQ-F-002.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights
from src.portfolio.v4.optimization import build_sector_net_constraints, sector_net_exposure, solve_sector_net_weights


def test_build_sector_net_constraints_returns_one_hot_matrix() -> None:
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech"})

    matrix = build_sector_net_constraints(["AAA", "BBB", "CCC"], sectors)

    assert matrix.loc["Tech", "AAA"] == pytest.approx(1.0)
    assert matrix.loc["Tech", "CCC"] == pytest.approx(1.0)
    assert matrix.loc["Health", "BBB"] == pytest.approx(1.0)
    assert matrix["AAA"].sum() == pytest.approx(1.0)


def test_solve_sector_net_weights_enforces_signed_sector_cap() -> None:
    raw = pd.Series({"AAA": 0.8, "BBB": 0.2, "CCC": -0.1, "DDD": -0.9})
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})

    solved = solve_sector_net_weights(raw, sectors, sector_net_cap=0.20, gross_target=2.0)
    sector_net = sector_net_exposure(solved, sectors)

    assert solved.where(solved > 0.0, 0.0).sum() == pytest.approx(1.0)
    assert -solved.where(solved < 0.0, 0.0).sum() == pytest.approx(1.0)
    assert sector_net.abs().max() <= 0.20 + 1e-12
    assert set(solved[solved != 0.0].index) == {"AAA", "BBB", "CCC", "DDD"}


def test_turnover_solver_enforces_adversarial_sector_net_cap() -> None:
    from src.portfolio.v4.optimization import solve_turnover_aware_weights

    raw = pd.Series({"AAA": 0.9, "BBB": 0.1, "CCC": -0.5, "DDD": -0.5})
    prior = pd.Series({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5})
    betas = pd.Series({"AAA": 1.0, "BBB": 1.0, "CCC": 1.0, "DDD": 1.0})
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Health", "DDD": "Health"})

    solved = solve_turnover_aware_weights(
        raw,
        prior,
        betas,
        sectors,
        sector_net_cap=0.15,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=0.0,
        short_top10_cap=0.25,
        single_short_cap=0.05,
    )

    assert sector_net_exposure(solved, sectors).abs().max() <= 0.15 + 1e-8


def test_build_v4_weights_runs_raw_to_sector_net_path() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2, name="date")
    raw = pd.DataFrame(
        {
            "AAA": [0.8, 0.7],
            "BBB": [0.2, 0.3],
            "CCC": [-0.1, -0.2],
            "DDD": [-0.9, -0.8],
        },
        index=dates,
    )
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(index=dates, columns=raw.columns),
    )
    config = V4Config(sector_net_cap=0.20, gross_target=2.0, turnover_penalty=0.0, no_trade_band_bps=0.0)

    result = build_v4_weights(inputs, config)

    assert result.weights.shape == raw.shape
    assert result.diagnostics["max_abs_sector_net"].max() <= 0.20 + 1e-12
    sector_checks = result.validation_status[result.validation_status["requirement"] == "REQ-F-002"]
    assert (sector_checks["status"] == "PASS").all()
    assert "REQ-F-002" in result.manifest["implemented_requirements"]
