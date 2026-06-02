"""Unit tests for Pillar 4.3 transaction cost evaluation."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_pillar4_stage43_costs import STAGE43_PORTFOLIOS, _stage43_portfolios
from src.combination.config import load_pillar4_config
from src.portfolio.costs import apply_linear_transaction_costs, summarize_net_returns


def test_cost_deduction_math_is_correct() -> None:
    daily_returns = _daily_returns(turnover=0.5)
    costed = apply_linear_transaction_costs(daily_returns, cost_bps=10)
    assert costed["transaction_cost"].iloc[0] == pytest.approx(0.0005)
    assert costed["net_return"].iloc[0] == pytest.approx(0.0095)


def test_higher_turnover_is_penalized_more() -> None:
    low_turnover = apply_linear_transaction_costs(_daily_returns(turnover=0.2), cost_bps=20)
    high_turnover = apply_linear_transaction_costs(_daily_returns(turnover=0.8), cost_bps=20)
    assert high_turnover["net_return"].mean() < low_turnover["net_return"].mean()
    assert high_turnover["transaction_cost"].mean() > low_turnover["transaction_cost"].mean()


def test_zero_bps_reproduces_gross_returns() -> None:
    daily_returns = _daily_returns(turnover=0.5)
    costed = apply_linear_transaction_costs(daily_returns, cost_bps=0)
    assert costed["net_return"].equals(daily_returns["long_short_return"])
    assert summarize_net_returns(costed)["net_cumulative_return"] == pytest.approx((1.01**3) - 1.0)


def test_yaml_driven_stage43_portfolio_definitions_work() -> None:
    config = load_pillar4_config("config/pillar4_candidate_factors.yaml")
    portfolios = _stage43_portfolios(config)
    assert [portfolio.name for portfolio in portfolios] == STAGE43_PORTFOLIOS
    assert portfolios[0].factors == ["short_term_reversal", "idiosyncratic_vol", "week_52_high"]
    assert portfolios[1].weighting == "fm_abs_tstat"


def test_invalid_cost_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="cost_bps"):
        apply_linear_transaction_costs(_daily_returns(turnover=0.5), cost_bps=-1)
    with pytest.raises(ValueError, match="missing"):
        apply_linear_transaction_costs(pd.DataFrame({"long_short_return": [0.01]}), cost_bps=5)


def _daily_returns(turnover: float) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=3)
    return pd.DataFrame(
        {
            "long_short_return": [0.01, 0.01, 0.01],
            "turnover": [turnover, turnover, turnover],
        },
        index=pd.Index(dates, name="date"),
    )
