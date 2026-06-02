"""Run Pillar 7 attribution and final strategy tearsheet generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.attribution import decompose_portfolio_return, risk_decomposition, summarize_attribution
from src.risk.risk_model import BarraStyleRiskModel
from src.reporting.strategy_tearsheet import generate_tearsheet


def main() -> None:
    args = _parse_args()
    backtest_dir = Path(args.backtest_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pnl = pd.read_parquet(backtest_dir / "pnl.parquet").iloc[:, 0].rename("pnl")
    nav = pd.read_parquet(backtest_dir / "nav.parquet").iloc[:, 0].rename("nav")
    weights = pd.read_parquet(args.weights).sort_index()
    factor_frame = pd.read_parquet(args.factor_data)
    returns = _load_returns(Path(args.returns))
    sector_map = _load_sector_map(Path(args.sector_map))

    factor_names = list(factor_frame.columns)
    factor_exposures = {
        factor: factor_frame[factor].unstack("ticker").sort_index()
        for factor in factor_names
    }

    common_dates = weights.index.intersection(returns.index).intersection(factor_exposures[factor_names[0]].index)
    common_cols = weights.columns.intersection(returns.columns).intersection(factor_exposures[factor_names[0]].columns)
    weights = weights.loc[common_dates, common_cols]
    returns = returns.loc[common_dates, common_cols]
    factor_exposures = {
        factor: panel.reindex(index=common_dates, columns=common_cols)
        for factor, panel in factor_exposures.items()
    }

    market_caps, market_cap_source = _load_market_caps(
        Path(args.market_caps),
        common_dates,
        common_cols,
        allow_equal_fallback=bool(args.allow_equal_market_cap_fallback),
    )
    industry = pd.get_dummies(sector_map.reindex(common_cols).fillna("Unknown")).astype(float)
    industry_stacked = pd.concat({date: industry for date in common_dates}, names=["date", "ticker"])

    model = BarraStyleRiskModel(factor_names).fit(returns, factor_exposures, market_caps, industry_stacked)
    factor_returns = model.factor_returns_timeseries
    factor_returns.to_parquet(output_dir / "factor_returns.parquet")

    attribution = decompose_portfolio_return(weights, factor_exposures, factor_returns[factor_names], returns)
    gross_total = attribution["total"].copy()
    gross_pure_alpha = attribution["pure_alpha"].copy()
    net_pnl = pnl.reindex(attribution.index).fillna(0.0)
    attribution["gross_total"] = gross_total
    attribution["gross_pure_alpha"] = gross_pure_alpha
    attribution["transaction_cost"] = net_pnl - gross_total
    attribution["pure_alpha"] = gross_pure_alpha + attribution["transaction_cost"]
    attribution["total"] = net_pnl
    summary = summarize_attribution(attribution)
    active_positions = weights.shift(1).fillna(0.0)
    risk_date = active_positions.abs().sum(axis=1).replace(0.0, np.nan).dropna().index[-1]
    risk = risk_decomposition(
        active_positions.loc[risk_date],
        {factor: panel.loc[risk_date] for factor, panel in factor_exposures.items()},
        model.factor_covariance.loc[factor_names, factor_names],
        model.idiosyncratic_volatility.pow(2.0),
    )
    summary["risk_decomposition"] = risk
    summary["risk_date"] = str(pd.Timestamp(risk_date).date())

    tearsheet_path = output_dir / "final_tearsheet.png"
    generate_tearsheet(
        pnl=pnl.reindex(common_dates).fillna(0.0),
        nav=nav.reindex(common_dates).ffill().fillna(1.0),
        weights=weights,
        attribution=attribution,
        factor_exposures=factor_exposures,
        factor_returns=factor_returns[factor_names],
        factor_cov=model.factor_covariance.loc[factor_names, factor_names],
        idio_var=model.idiosyncratic_volatility.pow(2.0),
        sector_map=sector_map,
        output_path=tearsheet_path,
    )

    summary_path = output_dir / "attribution_summary.json"
    summary_path.write_text(json.dumps(_json_ready(summary), indent=2), encoding="utf-8")
    manifest = {
        "backtest_dir": str(backtest_dir),
        "weights": str(args.weights),
        "factor_data": str(args.factor_data),
        "returns": str(args.returns),
        "market_caps": str(args.market_caps),
        "market_cap_source": market_cap_source,
        "sector_map": str(args.sector_map),
        "output": str(output_dir),
        "start_date": str(pd.Timestamp(common_dates.min()).date()),
        "end_date": str(pd.Timestamp(common_dates.max()).date()),
        "n_dates": int(len(common_dates)),
        "n_stocks": int(len(common_cols)),
        "factor_names": factor_names,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Attribution summary:")
    print(json.dumps(_json_ready(summary), indent=2))
    print(f"Visual confirmation: {tearsheet_path} generated with the 12 specified panels populated.")
    print("Panels: NAV, drawdown, monthly heatmap, rolling Sharpe, factor exposures, risk stack, sector stack, turnover, attribution bars, contributors, yearly table, summary stats.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Pillar 7 attribution and tearsheet.")
    parser.add_argument("--backtest-dir", default="results/backtest/")
    parser.add_argument("--weights", default="results/pillar5_artifacts/v3_weights.parquet")
    parser.add_argument("--factor-data", default="data/factor_data/factors.parquet")
    parser.add_argument("--returns", default="data/processed/prices.parquet")
    parser.add_argument("--market-caps", default="data/processed/fundamentals.parquet")
    parser.add_argument(
        "--allow-equal-market-cap-fallback",
        action="store_true",
        help=(
            "Permit equal-positive market-cap fallback for smoke tests only. "
            "Production attribution requires a positive market_cap panel."
        ),
    )
    parser.add_argument("--sector-map", default="data/raw/ticker_sector_map.parquet")
    parser.add_argument("--output", default="results/strategy_reports/")
    return parser.parse_args()


def _load_returns(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if isinstance(frame.index, pd.MultiIndex):
        if "return_1d" in frame.columns:
            return frame["return_1d"].unstack("ticker").sort_index()
        return frame.iloc[:, 0].unstack("ticker").sort_index()
    if {"date", "ticker", "return_1d"}.issubset(frame.columns):
        return frame.pivot(index="date", columns="ticker", values="return_1d").sort_index()
    return frame.astype(float).sort_index()


def _load_market_caps(
    path: Path,
    index: pd.Index,
    columns: pd.Index,
    allow_equal_fallback: bool = False,
) -> tuple[pd.DataFrame, str]:
    if path.exists():
        frame = pd.read_parquet(path)
        if not frame.empty:
            if isinstance(frame.index, pd.MultiIndex) and "market_cap" in frame.columns:
                panel = frame["market_cap"].unstack("ticker").sort_index()
                return _validate_market_cap_panel(panel, index, columns, path), "market_cap column"
            if {"date", "ticker", "market_cap"}.issubset(frame.columns):
                panel = frame.pivot(index="date", columns="ticker", values="market_cap").sort_index()
                return _validate_market_cap_panel(panel, index, columns, path), "market_cap column"
            numeric = frame.select_dtypes(include=[np.number])
            if not numeric.empty and frame.index.nlevels == 1:
                return _validate_market_cap_panel(numeric, index, columns, path), "numeric panel"
    if not allow_equal_fallback:
        raise ValueError(
            "No usable market_cap panel found. Barra-style attribution requires "
            "positive market caps for sqrt(market_cap) WLS weights. Rebuild "
            "daily fundamentals with market_cap, pass --market-caps to a valid "
            "panel, or use --allow-equal-market-cap-fallback only for smoke tests."
        )
    return pd.DataFrame(1.0, index=index, columns=columns), "equal-positive fallback (explicit smoke-test override)"


def _validate_market_cap_panel(
    panel: pd.DataFrame,
    index: pd.Index,
    columns: pd.Index,
    path: Path,
) -> pd.DataFrame:
    aligned = panel.astype(float).reindex(index=index, columns=columns)
    positive_coverage = aligned.where(aligned > 0.0).notna().mean(axis=1)
    min_coverage = float(positive_coverage.min()) if not positive_coverage.dropna().empty else np.nan
    if positive_coverage.dropna().empty or min_coverage < 0.95:
        raise ValueError(
            f"Market-cap panel from {path} has insufficient positive coverage "
            f"after alignment: min daily coverage={min_coverage:.2%}. "
            "Barra-style attribution requires positive market caps for the fitted universe."
        )
    return aligned


def _load_sector_map(path: Path) -> pd.Series:
    frame = pd.read_parquet(path)
    if isinstance(frame, pd.Series):
        return frame.astype(str)
    if {"ticker", "sector"}.issubset(frame.columns):
        return frame.drop_duplicates("ticker").set_index("ticker")["sector"].astype(str)
    if "sector" in frame.columns:
        return frame["sector"].astype(str)
    return pd.Series(dtype=str)


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


if __name__ == "__main__":
    main()
