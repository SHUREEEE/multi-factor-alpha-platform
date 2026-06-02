"""Matplotlib strategy tearsheet for the multi-factor alpha pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.risk.attribution import compute_factor_exposure, risk_decomposition, summarize_attribution


PALETTE = {
    "nav": "#1f77b4",
    "drawdown": "#c44e52",
    "positive": "#55a868",
    "negative": "#c44e52",
    "neutral": "#4c72b0",
    "accent": "#8172b2",
    "orange": "#dd8452",
    "gray": "#6b7280",
}
TRADING_DAYS = 252
AUM_ASSUMPTION = "1.0 gross notional"


def generate_tearsheet(
    pnl: pd.Series,
    nav: pd.Series,
    weights: pd.DataFrame,
    attribution: pd.DataFrame,
    factor_exposures: dict,
    factor_returns: pd.DataFrame,
    factor_cov: pd.DataFrame,
    idio_var: pd.Series,
    sector_map: pd.Series,
    output_path: Path,
) -> None:
    """Generate 12-panel matplotlib figure, save as PNG."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pnl = _clean_series(pnl, "pnl")
    nav = _clean_series(nav, "nav").reindex(pnl.index).ffill()
    weights = weights.astype(float).sort_index().reindex(pnl.index)
    attribution = attribution.astype(float).reindex(pnl.index)
    factor_returns = factor_returns.astype(float).sort_index().reindex(pnl.index)
    factor_exposures = {
        name: panel.astype(float).reindex(index=pnl.index, columns=weights.columns)
        for name, panel in factor_exposures.items()
    }
    idio_var = idio_var.astype(float)

    fig, axes = plt.subplots(4, 3, figsize=(20, 24))
    flat_axes = axes.ravel()
    fig.suptitle("Multi-Factor Alpha Strategy — Tearsheet", fontsize=24, fontweight="bold", y=0.992)

    _plot_nav(flat_axes[0], nav)
    _plot_drawdown(flat_axes[1], nav)
    _plot_monthly_heatmap(flat_axes[2], pnl)
    _plot_rolling_sharpe(flat_axes[3], pnl)
    portfolio_factor_exposures = _plot_factor_exposures(flat_axes[4], weights, factor_exposures)
    risk_ts = _plot_risk_decomposition(flat_axes[5], weights, factor_exposures, factor_cov, idio_var)
    _plot_sector_exposures(flat_axes[6], weights, sector_map)
    _plot_turnover(flat_axes[7], weights)
    _plot_attribution(flat_axes[8], attribution)
    _plot_stock_contributors(flat_axes[9], weights, factor_exposures, factor_returns)
    _plot_yearly_table(flat_axes[10], pnl)
    _plot_summary_stats(flat_axes[11], pnl, weights, attribution)

    for ax in flat_axes:
        ax.title.set_fontweight("bold")
        ax.grid(True, alpha=0.25)

    start = pnl.index.min().date() if not pnl.empty else "n/a"
    end = pnl.index.max().date() if not pnl.empty else "n/a"
    factor_share = risk_ts["factor_variance"].sum() / risk_ts.sum(axis=1).replace(0.0, np.nan).sum() if not risk_ts.empty else np.nan
    footer = f"Backtest period: {start} to {end}, AUM assumption: {AUM_ASSUMPTION}, rolling factor risk share: {_fmt_pct(factor_share)}"
    fig.text(0.5, 0.01, footer, ha="center", fontsize=10, color=PALETTE["gray"])
    fig.tight_layout(rect=[0.02, 0.03, 0.98, 0.975])
    fig.savefig(output_path, dpi=150, bbox_inches="tight")


def _clean_series(series: pd.Series, name: str) -> pd.Series:
    clean = series.astype(float).copy()
    clean.index = pd.to_datetime(clean.index)
    clean = clean.sort_index().replace([np.inf, -np.inf], np.nan)
    clean.name = name
    return clean


def _plot_nav(ax: plt.Axes, nav: pd.Series) -> None:
    ax.plot(nav.index, nav, color=PALETTE["nav"], linewidth=1.8, label="Strategy NAV")
    ax.set_yscale("log")
    ax.set_title("Cumulative NAV")
    ax.set_xlabel("Date")
    ax.set_ylabel("NAV (log scale)")
    ax.legend(loc="best")


def _plot_drawdown(ax: plt.Axes, nav: pd.Series) -> None:
    drawdown = nav / nav.cummax() - 1.0
    ax.fill_between(drawdown.index, drawdown.to_numpy(), 0.0, color=PALETTE["drawdown"], alpha=0.35)
    ax.plot(drawdown.index, drawdown, color=PALETTE["drawdown"], linewidth=1.2)
    ax.set_title("Drawdown")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown")


def _plot_monthly_heatmap(ax: plt.Axes, pnl: pd.Series) -> None:
    daily = pnl.fillna(0.0)
    monthly = (1.0 + daily).groupby(daily.index.to_period("M")).prod() - 1.0
    monthly.index = monthly.index.to_timestamp(how="end")
    table = monthly.to_frame("return")
    table["year"] = table.index.year
    table["month"] = table.index.month
    heatmap = table.pivot(index="year", columns="month", values="return").reindex(columns=range(1, 13))
    data = heatmap.to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(data)) if np.isfinite(data).any() else 0.01
    ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(12), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], rotation=45)
    ax.set_yticks(range(len(heatmap.index)), heatmap.index.astype(str))
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            if np.isfinite(data[y, x]):
                ax.text(x, y, f"{data[y, x] * 100:.1f}", ha="center", va="center", fontsize=7)
    ax.set_title("Monthly Returns Heatmap")
    ax.set_xlabel("Month")
    ax.set_ylabel("Year")


def _plot_rolling_sharpe(ax: plt.Axes, pnl: pd.Series) -> None:
    rolling = pnl.rolling(TRADING_DAYS, min_periods=60)
    sharpe = rolling.mean() / rolling.std(ddof=1) * np.sqrt(TRADING_DAYS)
    ax.plot(sharpe.index, sharpe, color=PALETTE["accent"], linewidth=1.4)
    ax.axhline(1.0, color=PALETTE["gray"], linestyle="--", linewidth=1.0)
    ax.set_title("Rolling 252-Day Sharpe")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sharpe")


def _plot_factor_exposures(ax: plt.Axes, weights: pd.DataFrame, factor_exposures: dict) -> pd.DataFrame:
    exposures = compute_factor_exposure(weights.shift(1), factor_exposures)
    for column in exposures.columns:
        ax.plot(exposures.index, exposures[column], linewidth=1.1, label=column)
    ax.set_title("Factor Exposures Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel("Exposure")
    ax.legend(loc="best", fontsize=8)
    return exposures


def _plot_risk_decomposition(
    ax: plt.Axes,
    weights: pd.DataFrame,
    factor_exposures: dict,
    factor_cov: pd.DataFrame,
    idio_var: pd.Series,
) -> pd.DataFrame:
    rows = []
    shifted_weights = weights.shift(1).fillna(0.0)
    for date, row in shifted_weights.iterrows():
        if row.abs().sum() == 0.0:
            rows.append({"factor_variance": 0.0, "idiosyncratic_variance": 0.0})
            continue
        one_day_exposures = {name: panel.loc[date] for name, panel in factor_exposures.items() if date in panel.index}
        risk = risk_decomposition(row, one_day_exposures, factor_cov, idio_var)
        rows.append({"factor_variance": risk["factor_variance"], "idiosyncratic_variance": risk["idiosyncratic_variance"]})
    risk_ts = pd.DataFrame(rows, index=weights.index).rolling(60, min_periods=1).mean()
    ax.stackplot(
        risk_ts.index,
        risk_ts["factor_variance"],
        risk_ts["idiosyncratic_variance"],
        labels=["Factor variance", "Idio variance"],
        colors=[PALETTE["neutral"], PALETTE["orange"]],
        alpha=0.75,
    )
    ax.set_title("Risk Decomposition (60-Day Rolling)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Variance")
    ax.legend(loc="best", fontsize=8)
    return risk_ts


def _plot_sector_exposures(ax: plt.Axes, weights: pd.DataFrame, sector_map: pd.Series) -> None:
    sectors = sector_map.reindex(weights.columns).fillna("Unknown")
    exposure = weights.shift(1).fillna(0.0).T.groupby(sectors).sum().T
    if not exposure.empty:
        ax.stackplot(exposure.index, [exposure[column] for column in exposure.columns], labels=exposure.columns, alpha=0.75)
    ax.set_title("Sector Exposures Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel("Net Weight")
    ax.legend(loc="best", fontsize=7, ncol=2)


def _plot_turnover(ax: plt.Axes, weights: pd.DataFrame) -> None:
    turnover = weights.fillna(0.0).diff().abs().sum(axis=1)
    ax.plot(turnover.index, turnover, color=PALETTE["gray"], alpha=0.5, linewidth=0.8, label="Daily turnover")
    ax.plot(turnover.index, turnover.rolling(60, min_periods=1).mean(), color=PALETTE["negative"], linewidth=1.4, label="60-day MA")
    ax.set_title("Turnover Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily gross turnover (x)")
    ax.legend(loc="best")


def _plot_attribution(ax: plt.Axes, attribution: pd.DataFrame) -> None:
    summary = summarize_attribution(attribution)
    values = summary["factor_contribution_breakdown"].copy()
    values["gross_pure_alpha"] = summary["pure_alpha_gross_total"]
    if "transaction_cost" in attribution.columns:
        values["transaction_cost"] = summary["transaction_cost_total"]
    series = pd.Series(values).sort_values()
    colors = [PALETTE["positive"] if value >= 0.0 else PALETTE["negative"] for value in series]
    ax.bar(series.index, series.values, color=colors)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Cumulative Attribution")
    ax.set_xlabel("Component")
    ax.set_ylabel("Contribution")


def _plot_stock_contributors(
    ax: plt.Axes,
    weights: pd.DataFrame,
    factor_exposures: dict,
    factor_returns: pd.DataFrame,
) -> None:
    aligned_factors = [name for name in factor_exposures if name in factor_returns.columns]
    predicted_returns = pd.DataFrame(0.0, index=weights.index, columns=weights.columns)
    for factor in aligned_factors:
        predicted_returns = predicted_returns.add(factor_exposures[factor].mul(factor_returns[factor], axis=0), fill_value=0.0)
    stock_contrib = weights.shift(1).fillna(0.0).mul(predicted_returns.fillna(0.0)).sum(axis=0).sort_values()
    selected = pd.concat([stock_contrib.head(10), stock_contrib.tail(10)]).drop_duplicates()
    colors = [PALETTE["positive"] if value >= 0.0 else PALETTE["negative"] for value in selected]
    ax.barh(selected.index.astype(str), selected.values, color=colors)
    ax.axvline(0.0, color="black", linewidth=0.8)
    ax.set_title("Top 10 / Bottom 10 Contributors")
    ax.set_xlabel("Model-Implied Cumulative PnL")
    ax.set_ylabel("Ticker")


def _plot_yearly_table(ax: plt.Axes, pnl: pd.Series) -> None:
    rows = []
    for year, values in pnl.groupby(pnl.index.year):
        rows.append(
            [
                str(year),
                _fmt_pct((1.0 + values.fillna(0.0)).prod() - 1.0),
                f"{_sharpe(values):.2f}",
                _fmt_pct(_max_drawdown(values)),
                _fmt_pct(float((values > 0.0).mean())),
            ]
        )
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=["Year", "Return", "Sharpe", "MaxDD", "HitRate"], loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.3)
    ax.set_title("Yearly Performance Table")
    ax.set_xlabel("Year")
    ax.set_ylabel("Metrics")


def _plot_summary_stats(ax: plt.Axes, pnl: pd.Series, weights: pd.DataFrame, attribution: pd.DataFrame) -> None:
    stats = _summary_metrics(pnl, weights, attribution)
    lines = [f"{key}: {value}" for key, value in stats.items()]
    ax.axis("off")
    ax.text(0.02, 0.96, "\n".join(lines), transform=ax.transAxes, va="top", ha="left", fontsize=12, family="monospace")
    ax.set_title("Summary Stats")
    ax.set_xlabel("Metric")
    ax.set_ylabel("Value")


def _summary_metrics(pnl: pd.Series, weights: pd.DataFrame, attribution: pd.DataFrame) -> dict[str, str]:
    summary = summarize_attribution(attribution)
    total = summary["total_return"]
    factor_pct = summary["factor_contribution_total"] / total if total != 0.0 else np.nan
    turnover = weights.fillna(0.0).diff().abs().sum(axis=1).mean() * TRADING_DAYS
    return {
        "GrossReturn": _fmt_pct(summary["gross_total_return"]),
        "TxnCost": _fmt_pct(summary["transaction_cost_total"]),
        "Sharpe": f"{_sharpe(pnl):.2f}",
        "Sortino": f"{_sortino(pnl):.2f}",
        "Calmar": f"{_calmar(pnl):.2f}",
        "AnnRet": _fmt_pct(_annual_return(pnl)),
        "AnnVol": _fmt_pct(float(pnl.std(ddof=1) * np.sqrt(TRADING_DAYS))),
        "MaxDD": _fmt_pct(_max_drawdown(pnl)),
        "HitRate": _fmt_pct(float((pnl > 0.0).mean())),
        "Turnover": f"{float(turnover):.2f}x/year",
        "PureAlpha%": _fmt_pct(summary["pure_alpha_pct_of_total"]),
        "FactorContrib%": _fmt_pct(factor_pct),
    }


def _annual_return(pnl: pd.Series) -> float:
    clean = pnl.dropna()
    if clean.empty:
        return np.nan
    return float((1.0 + clean).prod() ** (TRADING_DAYS / clean.shape[0]) - 1.0)


def _sharpe(pnl: pd.Series) -> float:
    clean = pnl.dropna()
    vol = float(clean.std(ddof=1))
    return float(clean.mean() / vol * np.sqrt(TRADING_DAYS)) if vol > 0.0 else np.nan


def _sortino(pnl: pd.Series) -> float:
    clean = pnl.dropna()
    downside = clean[clean < 0.0]
    vol = float(downside.std(ddof=1))
    return float(clean.mean() / vol * np.sqrt(TRADING_DAYS)) if vol > 0.0 else np.nan


def _calmar(pnl: pd.Series) -> float:
    max_dd = abs(_max_drawdown(pnl))
    return _annual_return(pnl) / max_dd if max_dd > 0.0 else np.nan


def _max_drawdown(pnl: pd.Series) -> float:
    wealth = (1.0 + pnl.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min()) if not drawdown.empty else np.nan


def _fmt_pct(value: float) -> str:
    return "nan" if pd.isna(value) else f"{value * 100:.2f}%"
