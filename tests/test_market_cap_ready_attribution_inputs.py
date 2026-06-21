"""Tests for market-cap-ready attribution universe selection."""

from __future__ import annotations

import pandas as pd

from scripts.build_market_cap_ready_attribution_inputs import select_market_cap_ready_tickers


def test_select_market_cap_ready_tickers_filters_low_coverage() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    index = pd.MultiIndex.from_product([dates, ["AAA", "BBB", "CCC"]], names=["date", "ticker"])
    frame = pd.DataFrame(
        {
            "market_cap": [
                1.0,
                2.0,
                None,
                1.1,
                2.1,
                None,
                1.2,
                None,
                None,
                1.3,
                2.3,
                3.3,
            ]
        },
        index=index,
    )

    selected = select_market_cap_ready_tickers(frame, pd.Index(["AAA", "BBB", "CCC"]), min_ticker_coverage=0.75)

    assert selected == ["AAA", "BBB"]
