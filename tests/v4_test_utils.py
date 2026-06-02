"""Shared tiny V4 fixtures for contract tests."""

from __future__ import annotations

import pandas as pd

from src.portfolio.v4.builder import V4Config, V4InputBundle


def tiny_inputs() -> V4InputBundle:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw = pd.DataFrame({"AAA": [0.5], "BBB": [0.5], "CCC": [-0.5], "DDD": [-0.5]}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    return V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
    )


def tiny_config(**overrides) -> V4Config:
    values = {
        "sector_net_cap": 1.0,
        "gross_target": 2.0,
        "turnover_penalty": 0.0,
        "no_trade_band_bps": 0.0,
        "short_top10_cap": 1.0,
        "single_short_cap": 0.60,
    }
    values.update(overrides)
    return V4Config(**values)
