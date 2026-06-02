"""Unit tests for Pillar 5.4 capacity logic."""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.capacity import borrow_feasible_flag, compute_participation, compute_turnover_impact_cost


def test_participation_rate_includes_aum_and_gross_scaling() -> None:
    dates = pd.bdate_range("2024-01-02", periods=1, name="date")
    weights = pd.DataFrame({"AAA": [0.10]}, index=dates)
    adv20 = pd.DataFrame({"AAA": [10_000_000.0]}, index=dates)
    participation = compute_participation(weights, adv20, aum_usd=100_000_000.0, gross=1.5)
    assert participation.loc[dates[0], "AAA"] == pytest.approx(1.5)


def test_impact_cost_is_monotonic_in_aum() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3, name="date")
    weights = pd.DataFrame({"AAA": [0.0, 0.10, 0.20]}, index=dates)
    adv20 = pd.DataFrame({"AAA": [10_000_000.0, 10_000_000.0, 10_000_000.0]}, index=dates)
    daily_vol = pd.DataFrame({"AAA": [0.02, 0.02, 0.02]}, index=dates)
    low = compute_turnover_impact_cost(weights, adv20, daily_vol, 50_000_000.0, 1.0, 0.5)
    high = compute_turnover_impact_cost(weights, adv20, daily_vol, 200_000_000.0, 1.0, 0.5)
    assert high.dropna().mean() > low.dropna().mean()


def test_borrow_feasible_flag_transitions_at_thresholds() -> None:
    assert borrow_feasible_flag(htb_share=0.20, top10_short_concentration=0.30)
    assert not borrow_feasible_flag(htb_share=0.31, top10_short_concentration=0.30)
    assert not borrow_feasible_flag(htb_share=0.20, top10_short_concentration=0.41)
