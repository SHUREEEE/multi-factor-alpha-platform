"""Run the v2 institutional research validation pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_walk_forward_validation import build_walk_forward_rows  # noqa: E402
from src.portfolio.attribution import factor_residual_decomposition, variance_contribution_shares  # noqa: E402
from src.portfolio.capacity import borrow_feasible_flag, compute_participation, compute_turnover_impact_cost  # noqa: E402
from src.portfolio.factor_interactions import (  # noqa: E402
    factor_correlation_matrix,
    factor_exposure_summary,
    orthogonalize_factor,
    pca_factor_diagnostics,
    rolling_factor_correlation,
)
from src.research.factor_turnover import summarize_factor_turnover  # noqa: E402
from src.research.ic_analysis import compute_ic_timeseries, extract_daily_return_matrix, summarize_ic  # noqa: E402
from src.research.ic_analysis import make_forward_returns, prepare_factor_series  # noqa: E402
from src.research.ic_decay import compute_ic_decay  # noqa: E402
from src.research.quantile_test import (  # noqa: E402
    compute_annualized_sharpe,
    compute_long_short_return,
    compute_monotonicity,
    quantile_portfolio_returns,
)
from src.research.regime_validation import build_default_regimes, summarize_factor_by_regime, summarize_portfolio_by_regime  # noqa: E402
from src.research.significance import benjamini_hochberg, newey_west_mean_test  # noqa: E402


DEFAULT_CONFIG = ROOT / "config/institutional_validation.yaml"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config = _load_config(args.config)
    factors = _load_factors(_project_path(config["factor_file"]), config["factor_names"])
    prices = _load_prices(_project_path(config["price_file"]))
    output_dir = _project_path(config["output_dir"])
    report_file = _project_path(config["report_file"])
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    market_returns = _market_proxy(prices)
    regimes = build_default_regimes(market_returns)
    regimes.to_csv(output_dir / "regime_definitions.csv")

    factor_summary, ic_decay, turnover, quantile_regime, quantile_returns = _run_factor_validation(factors, prices, regimes, config)
    factor_summary.to_csv(output_dir / "factor_validation_summary.csv", index=False)
    ic_decay.to_csv(output_dir / "ic_decay.csv", index=False)
    turnover.to_csv(output_dir / "factor_turnover.csv", index=False)
    quantile_regime.to_csv(output_dir / "quantile_returns_by_regime.csv", index=False)
    quantile_returns.to_csv(output_dir / "quantile_portfolio_returns.csv", index=False)

    factor_corr = factor_correlation_matrix(factors)
    pca = pca_factor_diagnostics(factors)
    orthogonal = _run_orthogonalized_factor_diagnostics(factors, prices, config)
    rolling_corr = _run_rolling_factor_correlations(factors)
    factor_corr.to_csv(output_dir / "factor_correlation_matrix.csv")
    pca.to_csv(output_dir / "pca_factor_diagnostics.csv", index=False)
    orthogonal.to_csv(output_dir / "orthogonalized_factor_diagnostics.csv", index=False)
    rolling_corr.to_csv(output_dir / "rolling_factor_correlations.csv", index=False)

    portfolio_returns = _load_portfolio_returns(config, prices, factors)
    oos = _run_oos_validation(portfolio_returns, config)
    locked_oos = _run_locked_oos_validation(factors, prices, config)
    regime_portfolio = summarize_portfolio_by_regime(portfolio_returns, market_returns, regimes)
    oos.to_csv(output_dir / "oos_validation_windows.csv", index=False)
    locked_oos.to_csv(output_dir / "locked_factor_oos_windows.csv", index=False)
    regime_portfolio.to_csv(output_dir / "portfolio_returns_by_regime.csv", index=False)

    capacity = _run_capacity_grid(config, portfolio_returns)
    capacity.to_csv(output_dir / "capacity_impact_grid.csv", index=False)
    weights = _load_or_build_validation_weights(config, prices, factors)
    exposures, risk_ts, risk_summary = _run_risk_decomposition(weights, factors, portfolio_returns, prices, config)
    feature_importance = _build_feature_importance(factor_summary, locked_oos, orthogonal, risk_summary)
    exposures.to_csv(output_dir / "factor_exposure_timeseries.csv")
    risk_ts.to_csv(output_dir / "risk_decomposition.csv")
    risk_summary.to_csv(output_dir / "risk_decomposition_summary.csv", index=False)
    feature_importance.to_csv(output_dir / "feature_importance.csv", index=False)

    manifest = _manifest(config, output_dir)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_file.write_text(
        _build_report(
            factor_summary,
            ic_decay,
            turnover,
            factor_corr,
            pca,
            orthogonal,
            oos,
            locked_oos,
            regime_portfolio,
            capacity,
            risk_summary,
            feature_importance,
            manifest,
            rolling_corr,
        ),
        encoding="utf-8",
    )
    print(f"Saved institutional validation artifacts to {output_dir.as_posix()}")
    print(f"Saved report to {report_file.as_posix()}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v2 institutional validation pack.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Validation YAML config.")
    return parser.parse_args(argv)


def _load_config(path_text: str) -> dict[str, object]:
    path = _project_path(path_text)
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    required = {"factor_file", "price_file", "factor_names", "output_dir", "report_file"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"institutional validation config missing keys: {missing}")
    return config


def _project_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _load_factors(path: Path, factor_names: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing factor file: {path.as_posix()}")
    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError("factor file must use MultiIndex(date, ticker).")
    frame.index = frame.index.set_names(["date", "ticker"])
    missing = sorted(set(factor_names) - set(frame.columns))
    if missing:
        raise ValueError(f"factor file missing configured factors: {missing}")
    return frame[factor_names].astype(float).sort_index()


def _load_prices(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing price file: {path.as_posix()}")
    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError("price file must use MultiIndex(date, ticker).")
    if "return_1d" not in frame.columns:
        raise ValueError("price file must contain return_1d.")
    frame.index = frame.index.set_names(["date", "ticker"])
    return frame.sort_index()


def _run_factor_validation(
    factors: pd.DataFrame,
    prices: pd.DataFrame,
    regimes: pd.DataFrame,
    config: dict[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    periods = [int(value) for value in config.get("ic_periods", [1, 5, 10, 21, 63])]
    n_quantiles = int(config.get("n_quantiles", 10))
    nw_lags = int(config.get("nw_lags", 5))
    summary_rows = []
    decay_rows = []
    turnover_rows = []
    regime_rows = []
    quantile_return_rows = []
    p_values = []
    for factor_name in factors.columns:
        factor_frame = factors[[factor_name]]
        ic_table = compute_ic_timeseries(factor_frame, prices, periods=periods, already_shifted=True)
        ic_1d = summarize_ic(ic_table["ic_1d"])
        hac = newey_west_mean_test(ic_table["ic_1d"], lags=nw_lags)
        quantiles = _fast_quantile_portfolio_returns(factor_frame, prices, n_quantiles=n_quantiles)
        long_short = compute_long_short_return(quantiles)
        quantile_output = quantiles.copy()
        quantile_output.insert(0, "factor_name", factor_name)
        quantile_output.insert(1, "date", quantile_output.index)
        quantile_return_rows.append(quantile_output.reset_index(drop=True))
        turnover = summarize_factor_turnover(factor_frame, n_quantiles=n_quantiles, already_shifted=True)
        summary_rows.append(
            {
                "factor_name": factor_name,
                "ic_mean_1d": ic_1d["mean_ic"],
                "ic_ir_1d": ic_1d["ic_ir"],
                "ic_tstat_1d": hac["t_stat"],
                "ic_p_value_1d": hac["p_value"],
                "ic_hit_rate_1d": ic_1d["hit_rate"],
                "long_short_sharpe": compute_annualized_sharpe(long_short),
                "monotonicity": compute_monotonicity(quantiles),
                "rank_autocorr_mean": turnover["rank_autocorr_mean"],
                "signal_half_life_days": turnover["signal_half_life_days"],
            }
        )
        p_values.append(hac["p_value"])
        decay = compute_ic_decay(factor_frame, prices, periods=periods, already_shifted=True, nw_lags=nw_lags)
        decay.insert(0, "factor_name", factor_name)
        decay_rows.append(decay)
        turnover_rows.append({"factor_name": factor_name, **turnover})
        regime = _summarize_factor_by_regime_from_tables(ic_table, long_short, regimes)
        regime.insert(0, "factor_name", factor_name)
        regime_rows.append(regime)
    summary = pd.DataFrame(summary_rows)
    summary["ic_fdr_p_value_1d"] = benjamini_hochberg(pd.Series(p_values)).to_numpy(dtype=float)
    return (
        summary,
        pd.concat(decay_rows, ignore_index=True),
        pd.DataFrame(turnover_rows),
        pd.concat(regime_rows, ignore_index=True),
        pd.concat(quantile_return_rows, ignore_index=True),
    )


def _summarize_factor_by_regime_from_tables(ic_table: pd.DataFrame, long_short: pd.Series, regimes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    boolean_columns = [column for column in regimes.columns if regimes[column].dtype == bool]
    for regime_name in boolean_columns:
        mask = regimes[regime_name].reindex(ic_table.index).fillna(False).astype(bool)
        regime_ic = ic_table.loc[mask, "ic_1d"].replace([np.inf, -np.inf], np.nan).dropna()
        regime_ls = long_short.reindex(ic_table.index).loc[mask].replace([np.inf, -np.inf], np.nan).dropna()
        rows.append(
            {
                "regime": regime_name,
                "n_days": int(mask.sum()),
                "ic_mean_1d": float(regime_ic.mean()) if not regime_ic.empty else np.nan,
                "ic_hit_rate_1d": float((regime_ic > 0.0).mean()) if not regime_ic.empty else np.nan,
                "long_short_mean_1d": float(regime_ls.mean()) if not regime_ls.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _fast_quantile_portfolio_returns(
    factor_df: pd.DataFrame | pd.Series,
    prices: pd.DataFrame,
    *,
    n_quantiles: int,
) -> pd.DataFrame:
    factor = prepare_factor_series(factor_df, already_shifted=True).unstack("ticker").sort_index()
    forward = make_forward_returns(prices, period=1).unstack("ticker").reindex(index=factor.index, columns=factor.columns)
    ranks = factor.rank(axis=1, method="first", pct=True)
    output = pd.DataFrame(index=factor.index)
    for quantile in range(1, n_quantiles + 1):
        lower = (quantile - 1) / n_quantiles
        upper = quantile / n_quantiles
        if quantile == 1:
            mask = ranks <= upper
        else:
            mask = (ranks > lower) & (ranks <= upper)
        output[f"Q{quantile}"] = forward.where(mask).mean(axis=1, skipna=True)
    output.index.name = "date"
    return output


def _market_proxy(prices: pd.DataFrame) -> pd.Series:
    returns = extract_daily_return_matrix(prices)
    if "SPY" in returns.columns:
        return returns["SPY"].rename("market_return")
    return returns.mean(axis=1, skipna=True).rename("equal_weight_market_return")


def _load_portfolio_returns(config: dict[str, object], prices: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    daily_returns_file = config.get("daily_returns_file")
    if daily_returns_file and _project_path(str(daily_returns_file)).exists():
        frame = pd.read_parquet(_project_path(str(daily_returns_file)))
        if isinstance(frame, pd.Series):
            series = frame
        else:
            series = frame[_detect_return_column(frame)]
        series.index = pd.to_datetime(series.index)
        return series.astype(float).sort_index().rename("portfolio_return")
    return _synthetic_equal_weight_factor_portfolio(prices, factors)


def _synthetic_equal_weight_factor_portfolio(prices: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    returns = extract_daily_return_matrix(prices)
    score = factors.groupby(level="date").rank(pct=True).mean(axis=1).unstack("ticker").reindex(index=returns.index, columns=returns.columns)
    demeaned = score.sub(score.mean(axis=1), axis=0)
    weights = demeaned.div(demeaned.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    portfolio_returns = (weights.shift(1) * returns).sum(axis=1, min_count=1)
    portfolio_returns.name = "price_only_factor_portfolio_return"
    return portfolio_returns.dropna()


def _detect_return_column(frame: pd.DataFrame) -> str:
    for column in ("net_return", "daily_return", "long_short_return", "pnl", "return"):
        if column in frame.columns:
            return column
    numeric = frame.select_dtypes(include="number")
    if numeric.shape[1] == 1:
        return str(numeric.columns[0])
    raise ValueError("Could not detect portfolio return column.")


def _run_oos_validation(portfolio_returns: pd.Series, config: dict[str, object]) -> pd.DataFrame:
    rows = build_walk_forward_rows(
        portfolio_returns,
        train_years=int(config.get("train_years", 5)),
        test_years=int(config.get("test_years", 1)),
        min_train_days=int(config.get("min_train_days", 252)),
        min_test_days=int(config.get("min_test_days", 126)),
    )
    return pd.DataFrame([row.__dict__ for row in rows])


def _run_locked_oos_validation(factors: pd.DataFrame, prices: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """Run train-locked factor selection, direction, and equal-risk weighting."""
    returns = extract_daily_return_matrix(prices)
    common_dates = sorted(set(factors.index.get_level_values("date")).intersection(returns.index))
    train_years = int(config.get("train_years", 5))
    test_years = int(config.get("test_years", 1))
    min_train_days = int(config.get("min_train_days", 252))
    min_test_days = int(config.get("min_test_days", 126))
    rows = []
    if not common_dates:
        return pd.DataFrame()
    years = sorted(pd.Index(common_dates).year.unique())
    for start_year in years:
        train_start = pd.Timestamp(f"{start_year}-01-01")
        train_end = pd.Timestamp(f"{start_year + train_years - 1}-12-31")
        test_start = pd.Timestamp(f"{start_year + train_years}-01-01")
        test_end = pd.Timestamp(f"{start_year + train_years + test_years - 1}-12-31")
        train_dates = [date for date in common_dates if train_start <= pd.Timestamp(date) <= train_end]
        test_dates = [date for date in common_dates if test_start <= pd.Timestamp(date) <= test_end]
        if len(train_dates) < min_train_days or len(test_dates) < min_test_days:
            continue
        window_id = f"{start_year}_{start_year + train_years - 1}_to_{start_year + train_years}_{start_year + train_years + test_years - 1}"
        train_scores = _train_factor_scores(factors, prices, train_dates)
        selected = train_scores[train_scores["selected"]].copy()
        if selected.empty:
            selected = train_scores.reindex(train_scores["ic_mean"].abs().sort_values(ascending=False).index).head(min(3, len(train_scores))).copy()
        weights = _locked_factor_weights(selected)
        train_portfolio = _factor_combo_returns(factors, returns, train_dates, weights)
        test_portfolio = _factor_combo_returns(factors, returns, test_dates, weights)
        for split, stream in (("train", train_portfolio), ("test", test_portfolio)):
            rows.append(
                {
                    "window_id": window_id,
                    "split": split,
                    "start_date": str(pd.Timestamp(stream.index.min()).date()) if not stream.empty else "",
                    "end_date": str(pd.Timestamp(stream.index.max()).date()) if not stream.empty else "",
                    "n_days": int(stream.dropna().shape[0]),
                    "sharpe": compute_annualized_sharpe(stream),
                    "annual_return": _annualized_return(stream),
                    "max_drawdown": _max_drawdown(stream),
                    "selected_factors": ",".join(weights.index),
                    "locked_weights": json.dumps({key: round(float(value), 6) for key, value in weights.items()}, sort_keys=True),
                }
            )
    return pd.DataFrame(rows)


def _train_factor_scores(factors: pd.DataFrame, prices: pd.DataFrame, train_dates: list[pd.Timestamp]) -> pd.DataFrame:
    rows = []
    for factor_name in factors.columns:
        factor_slice = factors[[factor_name]].loc[(train_dates, slice(None)), :]
        price_slice = prices.loc[(train_dates, slice(None)), :]
        ic_table = compute_ic_timeseries(factor_slice, price_slice, periods=[1], already_shifted=True)
        hac = newey_west_mean_test(ic_table["ic_1d"], lags=5)
        ic_mean = float(hac["mean"]) if not pd.isna(hac["mean"]) else float("nan")
        rows.append(
            {
                "factor_name": factor_name,
                "ic_mean": ic_mean,
                "ic_tstat": hac["t_stat"],
                "direction": 1.0 if ic_mean >= 0.0 else -1.0,
                "selected": bool(abs(ic_mean) > 0.005 and abs(float(hac["t_stat"])) > 0.5) if not pd.isna(hac["t_stat"]) else False,
            }
        )
    return pd.DataFrame(rows).set_index("factor_name")


def _locked_factor_weights(train_scores: pd.DataFrame) -> pd.Series:
    strength = train_scores["ic_mean"].abs().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if strength.sum() <= 0.0:
        strength = pd.Series(1.0, index=train_scores.index)
    weights = strength / strength.sum()
    return (weights * train_scores["direction"].astype(float)).rename("locked_factor_weight")


def _factor_combo_returns(factors: pd.DataFrame, returns: pd.DataFrame, dates: list[pd.Timestamp], weights: pd.Series) -> pd.Series:
    if not dates:
        return pd.Series(dtype=float, name="locked_factor_oos_return")
    factor_slice = factors.loc[(dates, slice(None)), weights.index]
    score = factor_slice.mul(weights, axis=1).sum(axis=1).unstack("ticker")
    score = score.reindex(index=pd.Index(dates), columns=returns.columns)
    demeaned = score.sub(score.mean(axis=1), axis=0)
    portfolio_weights = demeaned.div(demeaned.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    stream = (portfolio_weights.shift(1) * returns.reindex(index=portfolio_weights.index, columns=portfolio_weights.columns)).sum(axis=1, min_count=1)
    stream.name = "locked_factor_oos_return"
    return stream.dropna()


def _run_capacity_grid(config: dict[str, object], portfolio_returns: pd.Series) -> pd.DataFrame:
    weights_path = _project_path(str(config.get("weights_file", "")))
    capacity_config = dict(config.get("capacity", {}) or {})
    aum_values = [float(value) for value in capacity_config.get("aum_usd", [25_000_000, 100_000_000])]
    impact_coefficients = [float(value) for value in capacity_config.get("impact_coefficients", [0.5])]
    gross = float(capacity_config.get("gross", 1.5))
    if not weights_path.exists():
        return pd.DataFrame(
            [
                {
                    "aum_usd": aum,
                    "impact_coefficient": impact,
                    "gross": gross,
                    "status": "blocked_missing_weights_or_adv",
                    "mean_participation": np.nan,
                    "mean_daily_impact_cost": np.nan,
                    "borrow_feasible_proxy": borrow_feasible_flag(0.0, 0.0),
                }
                for aum in aum_values
                for impact in impact_coefficients
            ]
        )
    weights = pd.read_parquet(weights_path).astype(float)
    weights.index = pd.to_datetime(weights.index)
    adv = pd.DataFrame(50_000_000.0, index=weights.index, columns=weights.columns)
    vol = pd.DataFrame(float(portfolio_returns.std(ddof=1) or 0.02), index=weights.index, columns=weights.columns)
    rows = []
    for aum in aum_values:
        participation = compute_participation(weights, adv, aum_usd=aum, gross=gross)
        for impact in impact_coefficients:
            impact_cost = compute_turnover_impact_cost(weights, adv, vol, aum_usd=aum, gross=gross, impact_coefficient=impact)
            short_concentration = _mean_top_short_concentration(weights)
            rows.append(
                {
                    "aum_usd": aum,
                    "impact_coefficient": impact,
                    "gross": gross,
                    "status": "proxy_adv_assumption",
                    "mean_participation": float(participation.mean(axis=1, skipna=True).mean(skipna=True)),
                    "p95_participation": float(participation.quantile(0.95, axis=1).mean(skipna=True)),
                    "mean_daily_impact_cost": float(impact_cost.mean(skipna=True)),
                    "borrow_feasible_proxy": borrow_feasible_flag(0.0, short_concentration),
                }
            )
    return pd.DataFrame(rows)


def _run_orthogonalized_factor_diagnostics(factors: pd.DataFrame, prices: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """Compare each raw factor to its residual after orthogonalizing to peers."""
    rows = []
    periods = [1]
    for factor_name in factors.columns:
        controls = factors.drop(columns=[factor_name])
        if controls.empty:
            continue
        residual = orthogonalize_factor(factors[factor_name], controls)
        raw_ic = compute_ic_timeseries(factors[[factor_name]], prices, periods=periods, already_shifted=True)["ic_1d"]
        residual_ic = compute_ic_timeseries(residual.to_frame(factor_name), prices, periods=periods, already_shifted=True)["ic_1d"]
        raw_hac = newey_west_mean_test(raw_ic, lags=int(config.get("nw_lags", 5)))
        residual_hac = newey_west_mean_test(residual_ic, lags=int(config.get("nw_lags", 5)))
        rows.append(
            {
                "factor_name": factor_name,
                "raw_ic_mean_1d": raw_hac["mean"],
                "raw_ic_tstat_1d": raw_hac["t_stat"],
                "orthogonalized_ic_mean_1d": residual_hac["mean"],
                "orthogonalized_ic_tstat_1d": residual_hac["t_stat"],
                "orthogonalized_ic_retention": _safe_div(residual_hac["mean"], raw_hac["mean"], min_abs_denominator=0.001),
                "controls": ",".join(controls.columns),
            }
        )
    return pd.DataFrame(rows)


def _run_rolling_factor_correlations(factors: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    rows = []
    columns = list(factors.columns)
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1 :]:
            series = rolling_factor_correlation(factors, left, right, window=window)
            clean = series.replace([np.inf, -np.inf], np.nan).dropna()
            rows.append(
                {
                    "left_factor": left,
                    "right_factor": right,
                    "window": window,
                    "mean_rolling_corr": float(clean.mean()) if not clean.empty else np.nan,
                    "min_rolling_corr": float(clean.min()) if not clean.empty else np.nan,
                    "max_rolling_corr": float(clean.max()) if not clean.empty else np.nan,
                    "n_obs": int(clean.shape[0]),
                }
            )
    return pd.DataFrame(rows)


def _load_or_build_validation_weights(config: dict[str, object], prices: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    weights_path = _project_path(str(config.get("weights_file", "")))
    if weights_path.exists():
        weights = pd.read_parquet(weights_path).astype(float)
        weights.index = pd.to_datetime(weights.index)
        return weights.sort_index()
    returns = extract_daily_return_matrix(prices)
    score = factors.groupby(level="date").rank(pct=True).mean(axis=1).unstack("ticker").reindex(index=returns.index, columns=returns.columns)
    demeaned = score.sub(score.mean(axis=1), axis=0)
    weights = demeaned.div(demeaned.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    weights.index.name = "date"
    return weights


def _run_risk_decomposition(
    weights: pd.DataFrame,
    factors: pd.DataFrame,
    portfolio_returns: pd.Series,
    prices: pd.DataFrame,
    config: dict[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exposures = factor_exposure_summary(weights, factors)
    returns = extract_daily_return_matrix(prices).reindex(index=weights.index, columns=weights.columns)
    factor_pnl = pd.DataFrame(index=weights.index)
    for factor_name in factors.columns:
        factor_panel = factors[factor_name].unstack("ticker").reindex(index=weights.index, columns=weights.columns)
        factor_signal = factor_panel.sub(factor_panel.mean(axis=1), axis=0)
        factor_signal = factor_signal.div(factor_signal.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
        factor_pnl[f"{factor_name}_pnl"] = (factor_signal.shift(1) * returns).sum(axis=1, min_count=1)
    total = portfolio_returns.reindex(factor_pnl.index).fillna(0.0)
    decomposition = factor_residual_decomposition(total, factor_pnl.fillna(0.0))
    variance_shares = variance_contribution_shares(total, factor_pnl.fillna(0.0))
    exposure_summary = exposures.agg(["mean", "std", "min", "max"]).T.reset_index().rename(columns={"index": "factor_name"})
    summary_rows = []
    for factor_name in factors.columns:
        pnl_column = f"{factor_name}_pnl"
        summary_rows.append(
            {
                "factor_name": factor_name,
                "mean_exposure": _lookup_summary(exposure_summary, factor_name, "mean"),
                "exposure_std": _lookup_summary(exposure_summary, factor_name, "std"),
                "variance_share": float(variance_shares.get(pnl_column, np.nan)),
                "mean_factor_pnl": float(factor_pnl[pnl_column].mean(skipna=True)),
                "pnl_tstat": newey_west_mean_test(factor_pnl[pnl_column], lags=int(config.get("nw_lags", 5)))["t_stat"],
            }
        )
    return exposures, decomposition, pd.DataFrame(summary_rows)


def _build_feature_importance(
    factor_summary: pd.DataFrame,
    locked_oos: pd.DataFrame,
    orthogonal: pd.DataFrame,
    risk_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    oos_tests = locked_oos[locked_oos["split"].eq("test")] if not locked_oos.empty and "split" in locked_oos.columns else pd.DataFrame()
    for _, row in factor_summary.iterrows():
        factor_name = row["factor_name"]
        selected_share = _selected_oos_share(oos_tests, factor_name)
        orth_row = orthogonal[orthogonal["factor_name"].eq(factor_name)] if not orthogonal.empty else pd.DataFrame()
        risk_row = risk_summary[risk_summary["factor_name"].eq(factor_name)] if not risk_summary.empty else pd.DataFrame()
        ic_strength = abs(float(row["ic_mean_1d"])) if not pd.isna(row["ic_mean_1d"]) else 0.0
        ls_strength = abs(float(row["long_short_sharpe"])) if not pd.isna(row["long_short_sharpe"]) else 0.0
        orth_retention = float(orth_row["orthogonalized_ic_retention"].iloc[0]) if not orth_row.empty and not pd.isna(orth_row["orthogonalized_ic_retention"].iloc[0]) else 0.0
        variance_share = abs(float(risk_row["variance_share"].iloc[0])) if not risk_row.empty and not pd.isna(risk_row["variance_share"].iloc[0]) else 0.0
        score = ic_strength * 100.0 + min(ls_strength, 5.0) + selected_share + min(abs(orth_retention), 2.0) + min(variance_share, 2.0)
        rows.append(
            {
                "factor_name": factor_name,
                "importance_score": float(score),
                "ic_abs_component": ic_strength,
                "long_short_sharpe_abs_component": ls_strength,
                "oos_selected_window_share": selected_share,
                "orthogonalized_ic_retention": orth_retention,
                "variance_share_abs": variance_share,
            }
        )
    return pd.DataFrame(rows).sort_values("importance_score", ascending=False)


def _mean_top_short_concentration(weights: pd.DataFrame) -> float:
    from src.portfolio.capacity import top_short_concentration

    values = [top_short_concentration(row) for _, row in weights.iterrows()]
    clean = pd.Series(values).replace([np.inf, -np.inf], np.nan).dropna()
    return float(clean.mean()) if not clean.empty else 0.0


def _selected_oos_share(oos_tests: pd.DataFrame, factor_name: str) -> float:
    if oos_tests.empty or "selected_factors" not in oos_tests.columns:
        return 0.0
    selected = oos_tests["selected_factors"].fillna("").map(lambda text: factor_name in str(text).split(","))
    return float(selected.mean()) if not selected.empty else 0.0


def _lookup_summary(summary: pd.DataFrame, factor_name: str, column: str) -> float:
    row = summary[summary["factor_name"].eq(factor_name)]
    if row.empty or column not in row.columns:
        return float("nan")
    return float(row[column].iloc[0])


def _safe_div(numerator: object, denominator: object, min_abs_denominator: float = 0.0) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or abs(float(denominator)) <= min_abs_denominator:
        return float("nan")
    return float(numerator) / float(denominator)


def _annualized_return(returns: pd.Series) -> float:
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if clean.empty:
        return float("nan")
    total = float((1.0 + clean).prod() - 1.0)
    years = clean.shape[0] / 252.0
    return float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0.0 else float("nan")


def _max_drawdown(returns: pd.Series) -> float:
    clean = returns.fillna(0.0).astype(float)
    if clean.empty:
        return float("nan")
    wealth = (1.0 + clean).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def _manifest(config: dict[str, object], output_dir: Path) -> dict[str, object]:
    return {
        "version": "v2 Institutional Research Validation Pack",
        "output_dir": str(output_dir.relative_to(ROOT)),
        "price_only_default": True,
        "fundamentals_status": "full_universe_coverage_gated; market_cap_ready_subset_restored_without_equal_cap_fallback",
        "market_cap_ready_attribution": "results/market_cap_ready_attribution",
        "factor_count": len(config["factor_names"]),
    }


def _build_report(
    factor_summary: pd.DataFrame,
    ic_decay: pd.DataFrame,
    turnover: pd.DataFrame,
    factor_corr: pd.DataFrame,
    pca: pd.DataFrame,
    orthogonal: pd.DataFrame,
    oos: pd.DataFrame,
    locked_oos: pd.DataFrame,
    regime_portfolio: pd.DataFrame,
    capacity: pd.DataFrame,
    risk_summary: pd.DataFrame,
    feature_importance: pd.DataFrame,
    manifest: dict[str, object],
    rolling_corr: pd.DataFrame,
) -> str:
    best = factor_summary.sort_values("ic_fdr_p_value_1d", na_position="last").head(5)
    test_rows = oos[oos["split"].eq("test")] if not oos.empty and "split" in oos.columns else pd.DataFrame()
    locked_test_rows = locked_oos[locked_oos["split"].eq("test")] if not locked_oos.empty and "split" in locked_oos.columns else pd.DataFrame()
    lines = [
        "# v2 Institutional Research Validation Pack",
        "",
        "## Executive Summary",
        "",
        "- This report validates signal stability, statistical significance, factor interaction, OOS behavior, regime behavior, and implementation constraints.",
        "- It is a research evidence pack, not a production/live-readiness claim.",
        f"- Fundamentals-dependent attribution remains `{manifest['fundamentals_status']}`.",
        "",
        "## Factor Validation",
        "",
        _markdown_table(best),
        "",
        "## IC Decay",
        "",
        _markdown_table(ic_decay.head(20)),
        "",
        "## Factor Turnover",
        "",
        _markdown_table(turnover),
        "",
        "## Factor Interaction",
        "",
        f"- Max absolute off-diagonal correlation: {_max_abs_offdiag(factor_corr):.4f}",
        f"- PC1 explained variance: {_first_value(pca, 'explained_variance_ratio'):.4f}",
        "",
        "## Rolling Factor Correlations",
        "",
        _markdown_table(rolling_corr),
        "",
        "## Orthogonalized Factor Diagnostics",
        "",
        _markdown_table(orthogonal),
        "",
        "## OOS Validation",
        "",
        _markdown_table(test_rows),
        "",
        "## Train-Locked Factor OOS Validation",
        "",
        _markdown_table(locked_test_rows),
        "",
        "## Regime Validation",
        "",
        _markdown_table(regime_portfolio),
        "",
        "## Exposure And Risk Decomposition",
        "",
        _markdown_table(risk_summary),
        "",
        "## Feature Importance",
        "",
        _markdown_table(feature_importance),
        "",
        "## Capacity And Impact",
        "",
        _markdown_table(capacity),
        "",
        "## Artifact Contract",
        "",
        "- `factor_validation_summary.csv`",
        "- `ic_decay.csv`",
        "- `factor_turnover.csv`",
        "- `quantile_portfolio_returns.csv`",
        "- `quantile_returns_by_regime.csv`",
        "- `factor_correlation_matrix.csv`",
        "- `rolling_factor_correlations.csv`",
        "- `pca_factor_diagnostics.csv`",
        "- `orthogonalized_factor_diagnostics.csv`",
        "- `oos_validation_windows.csv`",
        "- `locked_factor_oos_windows.csv`",
        "- `factor_exposure_timeseries.csv`",
        "- `risk_decomposition.csv`",
        "- `risk_decomposition_summary.csv`",
        "- `feature_importance.csv`",
        "- `capacity_impact_grid.csv`",
        "",
    ]
    return "\n".join(lines)


def _max_abs_offdiag(frame: pd.DataFrame) -> float:
    if frame.empty:
        return float("nan")
    values = frame.to_numpy(dtype=float).copy()
    np.fill_diagonal(values, np.nan)
    return float(np.nanmax(np.abs(values)))


def _first_value(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return float("nan")
    return float(frame[column].iloc[0])


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows available."
    view = frame.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: "n/a" if pd.isna(value) else f"{float(value):.4f}")
    columns = list(view.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
