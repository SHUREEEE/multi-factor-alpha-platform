from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.risk.attribution import decompose_portfolio_return
from src.reporting.strategy_tearsheet import generate_tearsheet


def test_tearsheet_png_generated_and_has_12_axes(tmp_path, monkeypatch) -> None:
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2022-01-03", periods=320, name="date")
    tickers = [f"S{i:02d}" for i in range(16)]
    factors = ["value", "momentum", "lowvol"]

    weights = pd.DataFrame(rng.normal(scale=0.02, size=(len(dates), len(tickers))), index=dates, columns=tickers)
    weights = weights.sub(weights.mean(axis=1), axis=0)
    stock_returns = pd.DataFrame(rng.normal(scale=0.01, size=(len(dates), len(tickers))), index=dates, columns=tickers)
    pnl = weights.shift(1).fillna(0.0).mul(stock_returns).sum(axis=1).rename("pnl")
    nav = (1.0 + pnl).cumprod().rename("nav")
    factor_exposures = {
        factor: pd.DataFrame(rng.normal(size=(len(dates), len(tickers))), index=dates, columns=tickers)
        for factor in factors
    }
    factor_returns = pd.DataFrame(rng.normal(scale=0.001, size=(len(dates), len(factors))), index=dates, columns=factors)
    attribution = decompose_portfolio_return(weights, factor_exposures, factor_returns, stock_returns)
    factor_cov = pd.DataFrame(np.eye(len(factors)) * 0.0001, index=factors, columns=factors)
    idio_var = pd.Series(0.0002, index=tickers)
    sector_map = pd.Series({ticker: f"Sector {i % 4}" for i, ticker in enumerate(tickers)})
    output_path = tmp_path / "tearsheet.png"

    captured = {}
    original_savefig = plt.Figure.savefig

    def capture_savefig(self, *args, **kwargs):
        captured["axes"] = len(self.axes)
        return original_savefig(self, *args, **kwargs)

    monkeypatch.setattr(plt.Figure, "savefig", capture_savefig)

    generate_tearsheet(
        pnl=pnl,
        nav=nav,
        weights=weights,
        attribution=attribution,
        factor_exposures=factor_exposures,
        factor_returns=factor_returns,
        factor_cov=factor_cov,
        idio_var=idio_var,
        sector_map=sector_map,
        output_path=output_path,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 50_000
    assert captured["axes"] == 12
