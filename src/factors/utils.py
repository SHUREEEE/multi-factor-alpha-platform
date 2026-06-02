"""Preprocessing and data-alignment utilities for factor research."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
import statsmodels.api as sm


def validate_multiindex_frame(frame: pd.DataFrame | pd.Series, name: str) -> None:
    """Validate that an object uses ``(date, ticker)`` MultiIndex."""
    if not isinstance(frame, (pd.DataFrame, pd.Series)):
        raise TypeError(f"{name} must be a pandas DataFrame or Series.")
    if not isinstance(frame.index, pd.MultiIndex):
        raise TypeError(f"{name} must use MultiIndex(date, ticker).")
    if list(frame.index.names) != ["date", "ticker"]:
        raise ValueError(f"{name} index names must be ['date', 'ticker'].")


def single_column_frame(values: pd.Series, column_name: str) -> pd.DataFrame:
    """Convert a MultiIndex Series into a clean single-column DataFrame."""
    validate_multiindex_frame(values, column_name)  # 中文：统一检查索引，防止横截面处理按错维度。
    factor_frame = values.astype(float).to_frame(column_name)  # 中文：因子值必须是数值，便于回归和标准化。
    factor_frame = factor_frame.replace([np.inf, -np.inf], np.nan)  # 中文：无穷值会破坏 OLS 和 z-score。
    return factor_frame.sort_index()


def stack_wide_panel(wide_frame: pd.DataFrame) -> pd.Series:
    """Stack a date-by-ticker wide panel while preserving missing observations."""
    panel = wide_frame.rename_axis(index="date", columns="ticker")  # 中文：显式命名索引，避免长表索引名称丢失。
    long_frame = panel.reset_index().melt(id_vars="date", var_name="ticker", value_name="value")  # 中文：melt 保留 NaN，比新版 stack 更稳定。
    long_frame = long_frame.sort_values(["date", "ticker"])  # 中文：排序让输出与价格 MultiIndex 顺序一致。
    return long_frame.set_index(["date", "ticker"])["value"].astype(float)


def get_prices(data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
    """Return validated price panel from the input dictionary."""
    prices = data.get("prices")  # 中文：所有价格类因子都从统一 key 读取，减少接口混乱。
    if not isinstance(prices, pd.DataFrame):
        raise TypeError("data['prices'] must be a pandas DataFrame.")
    validate_multiindex_frame(prices, "prices")
    if "adj_close" not in prices.columns:
        raise ValueError("prices must contain adj_close.")
    return prices.sort_index()


def get_returns(data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
    """Return wide daily return matrix with dates as index and tickers as columns."""
    prices = get_prices(data)  # 中文：优先从清洗价格数据计算收益，保证口径一致。
    if "return_1d" in prices.columns:
        returns = prices["return_1d"].unstack("ticker")  # 中文：已有收益列时直接使用 Pillar 1 结果。
    else:
        returns = prices["adj_close"].unstack("ticker").pct_change()  # 中文：否则用复权价计算日收益。
    return returns.replace([np.inf, -np.inf], np.nan)


def get_market_returns(data: dict[str, pd.DataFrame | pd.Series], returns: pd.DataFrame) -> pd.Series:
    """Return market proxy returns aligned to the stock-return matrix."""
    provided_market = data.get("market_returns")  # 中文：真实项目应优先传入 SPY 或 CRSP 市场收益。
    if isinstance(provided_market, pd.Series):
        return provided_market.reindex(returns.index).astype(float)
    warnings.warn("market_returns missing; using equal-weight universe return as market proxy.", stacklevel=2)
    return returns.mean(axis=1, skipna=True)  # 中文：等权市场代理只是免费数据 fallback，需在报告中披露。


def get_panel(data: dict[str, pd.DataFrame | pd.Series], key: str) -> pd.Series:
    """Return one MultiIndex Series, or an all-NaN template if unavailable."""
    value = data.get(key)  # 中文：基本面字段可能缺失，不能因为一个字段缺失让全流程崩溃。
    if isinstance(value, pd.DataFrame):
        if value.shape[1] != 1:
            raise ValueError(f"data['{key}'] DataFrame must have exactly one column.")
        series = value.iloc[:, 0]
    elif isinstance(value, pd.Series):
        series = value
    else:
        template = _template_index(data)  # 中文：使用价格索引生成 NaN，保持输出形状可合并。
        return pd.Series(np.nan, index=template, name=key, dtype=float)
    validate_multiindex_frame(series, key)
    return series.astype(float).sort_index()


def divide_panel(numerator: pd.Series, denominator: pd.Series, column_name: str) -> pd.DataFrame:
    """Safely divide two aligned MultiIndex panels."""
    aligned_numerator, aligned_denominator = numerator.align(denominator, join="outer")  # 中文：先对齐日期和股票，避免错位相除。
    clean_denominator = aligned_denominator.where(aligned_denominator != 0)  # 中文：除以 0 没有金融含义，设为 NaN。
    values = aligned_numerator / clean_denominator  # 中文：pandas 会自动保留缺失数据为 NaN。
    return single_column_frame(values, column_name)


def winsorize(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Cap extreme values by lower and upper quantiles."""
    if not isinstance(s, pd.Series):
        raise TypeError("s must be a pandas Series.")
    if not 0 <= lower < upper <= 1:
        raise ValueError("lower and upper must satisfy 0 <= lower < upper <= 1.")
    if s.dropna().empty:
        return s.astype(float)
    lower_value = s.quantile(lower)  # 中文：下分位数定义极端低值边界。
    upper_value = s.quantile(upper)  # 中文：上分位数定义极端高值边界。
    return s.clip(lower=lower_value, upper=upper_value).astype(float)


def zscore_cross_sectional(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize each date's cross-section to mean 0 and standard deviation 1."""
    _validate_factor_frame(df)  # 中文：必须按 date 横截面处理，不能把不同日期混在一起。
    standardized = df.groupby(level="date", group_keys=False).apply(_zscore_one_date)
    return standardized.reindex(df.index)


def rank_normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Convert each date's cross-section to percentile ranks in [-1, 1]."""
    _validate_factor_frame(df)
    ranked = df.groupby(level="date", group_keys=False).rank(pct=True)  # 中文：每天内部排名，避免未来分布泄露。
    normalized = 2.0 * ranked - 1.0  # 中文：把 [0,1] 排名映射到 [-1,1]，便于不同因子比较。
    return normalized.reindex(df.index)


def neutralize(
    factor_df: pd.DataFrame,
    neutralizers_dict: dict[str, pd.DataFrame | pd.Series],
) -> pd.DataFrame:
    """Remove cross-sectional industry and size exposure using statsmodels OLS."""
    _validate_factor_frame(factor_df)
    if not neutralizers_dict:
        warnings.warn("No sector or market-cap neutralizers provided; demeaning factor by date.", stacklevel=2)
        demeaned = factor_df.groupby(level="date", group_keys=False).transform(lambda values: values - values.mean(skipna=True))
        return demeaned.reindex(factor_df.index)
    neutralized = factor_df.groupby(level="date", group_keys=False).apply(
        lambda daily_factor: _neutralize_one_date(daily_factor, neutralizers_dict)
    )
    return neutralized.reindex(factor_df.index)


def apply_full_pipeline(
    factor_df: pd.DataFrame,
    industry: pd.Series | pd.DataFrame | None,
    market_cap: pd.Series | pd.DataFrame | None,
) -> pd.DataFrame:
    """Apply winsorize -> neutralize -> zscore preprocessing in the required order."""
    _validate_factor_frame(factor_df)
    winsorized = factor_df.groupby(level="date", group_keys=False).transform(winsorize)  # 中文：先截尾，避免极端值污染回归系数。
    neutralizers = _build_neutralizers(industry, market_cap)  # 中文：行业和规模暴露是常见风格混杂来源。
    neutralized = neutralize(winsorized, neutralizers)  # 中文：无中性化变量时退化为每日去均值，避免保留横截面水平偏差。
    standardized = zscore_cross_sectional(neutralized)  # 中文：最后标准化，确保残差横截面可比。
    return standardized


def build_daily_fundamental_panels(
    fundamentals: pd.DataFrame,
    target_index: pd.MultiIndex,
) -> dict[str, pd.Series]:
    """Convert PIT-lagged long fundamentals into daily as-of panels without forward filling prices."""
    if fundamentals.empty:
        return {}
    _require_columns(fundamentals, ["ticker", "field", "value", "available_date"])
    sorted_fundamentals = fundamentals.copy()  # 中文：复制输入，避免脚本外部对象被修改。
    sorted_fundamentals["available_date"] = pd.to_datetime(sorted_fundamentals["available_date"])
    fields = sorted_fundamentals["field"].dropna().unique().tolist()
    return {
        str(field): _asof_one_field(sorted_fundamentals, str(field), target_index)
        for field in fields
    }


def _neutralize_one_date(
    daily_factor: pd.DataFrame,
    neutralizers_dict: dict[str, pd.DataFrame | pd.Series],
) -> pd.DataFrame:
    column_name = daily_factor.columns[0]
    regression_frame = pd.DataFrame({"factor": daily_factor[column_name]})  # 中文：被解释变量是当天横截面因子。
    for neutralizer_name, neutralizer in neutralizers_dict.items():
        regression_frame = regression_frame.join(_daily_neutralizer(neutralizer, daily_factor.index, neutralizer_name))
    regression_frame = regression_frame.dropna(subset=["factor"])  # 中文：没有因子值的股票不能进入回归。
    if regression_frame.shape[0] < 3:
        return daily_factor * np.nan
    design_matrix = _make_design_matrix(regression_frame.drop(columns=["factor"]))  # 中文：构造截距、行业哑变量、规模变量。
    valid_rows = design_matrix.notna().all(axis=1)
    y_values = regression_frame.loc[valid_rows, "factor"]
    x_values = design_matrix.loc[valid_rows]
    if len(y_values) <= x_values.shape[1]:
        return daily_factor * np.nan
    model = sm.OLS(y_values.astype(float), x_values.astype(float), missing="drop").fit()  # 中文：OLS 残差代表剔除行业/规模后的纯因子。
    output = daily_factor.copy() * np.nan
    output.loc[y_values.index, column_name] = model.resid
    return output


def _daily_neutralizer(
    neutralizer: pd.DataFrame | pd.Series,
    daily_index: pd.MultiIndex,
    neutralizer_name: str,
) -> pd.DataFrame:
    if isinstance(neutralizer, pd.DataFrame):
        neutralizer_series = neutralizer.iloc[:, 0]
    else:
        neutralizer_series = neutralizer
    validate_multiindex_frame(neutralizer_series, neutralizer_name)
    daily_values = neutralizer_series.reindex(daily_index)  # 中文：只取当前日期股票池，保证横截面回归不看未来。
    return daily_values.to_frame(neutralizer_name)


def _make_design_matrix(exposures: pd.DataFrame) -> pd.DataFrame:
    design_parts: list[pd.DataFrame] = []
    for column in exposures.columns:
        if not is_numeric_dtype(exposures[column]):
            dummies = pd.get_dummies(exposures[column], prefix=column, drop_first=True, dtype=float)  # 中文：行业变量需转成哑变量才能进入 OLS。
            design_parts.append(dummies)
        else:
            design_parts.append(exposures[[column]].astype(float))
    design_matrix = pd.concat(design_parts, axis=1) if design_parts else pd.DataFrame(index=exposures.index)
    return sm.add_constant(design_matrix, has_constant="add")  # 中文：截距项保证残差横截面均值理论上为 0。


def _zscore_one_date(daily_frame: pd.DataFrame) -> pd.DataFrame:
    mean_values = daily_frame.mean(skipna=True)  # 中文：每天单独求均值，是横截面标准化。
    std_values = daily_frame.std(skipna=True, ddof=0)  # 中文：总体标准差让单日横截面尺度稳定。
    safe_std = std_values.replace(0, np.nan)  # 中文：同一天所有股票值相同则无法标准化。
    return (daily_frame - mean_values) / safe_std


def _build_neutralizers(
    industry: pd.Series | pd.DataFrame | None,
    market_cap: pd.Series | pd.DataFrame | None,
) -> dict[str, pd.DataFrame | pd.Series]:
    neutralizers: dict[str, pd.DataFrame | pd.Series] = {}
    if industry is not None:
        neutralizers["sector"] = industry
    if market_cap is not None:
        market_cap_series = market_cap.iloc[:, 0] if isinstance(market_cap, pd.DataFrame) else market_cap
        neutralizers["log_market_cap"] = np.log(market_cap_series.where(market_cap_series > 0))  # 中文：规模中性化通常用 log 市值。
    return neutralizers


def _asof_one_field(fundamentals: pd.DataFrame, field: str, target_index: pd.MultiIndex) -> pd.Series:
    target_frame = target_index.to_frame(index=False)  # 中文：目标是每日 date×ticker 面板。
    field_frame = fundamentals[fundamentals["field"] == field].copy()
    asof_frames = [_asof_one_ticker(field_frame, ticker, target_frame) for ticker in target_frame["ticker"].unique()]
    combined = pd.concat(asof_frames, ignore_index=True) if asof_frames else target_frame.assign(value=np.nan)
    combined = combined.set_index(["date", "ticker"]).sort_index()
    return combined["value"].astype(float).reindex(target_index)


def _asof_one_ticker(field_frame: pd.DataFrame, ticker: Any, target_frame: pd.DataFrame) -> pd.DataFrame:
    ticker_targets = target_frame[target_frame["ticker"] == ticker].sort_values("date")
    ticker_values = field_frame[field_frame["ticker"] == ticker].sort_values("available_date")
    if ticker_values.empty:
        return ticker_targets.assign(value=np.nan)
    merged = pd.merge_asof(
        ticker_targets,
        ticker_values[["available_date", "value"]],
        left_on="date",
        right_on="available_date",
        direction="backward",
    )
    return merged[["date", "ticker", "value"]]


def _template_index(data: dict[str, pd.DataFrame | pd.Series]) -> pd.MultiIndex:
    prices = data.get("prices")
    if isinstance(prices, pd.DataFrame):
        validate_multiindex_frame(prices, "prices")
        return prices.index
    raise KeyError("Missing panel and prices template.")


def _validate_factor_frame(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("factor_df must be a pandas DataFrame.")
    validate_multiindex_frame(frame, "factor_df")
    if frame.shape[1] != 1:
        raise ValueError("factor_df must contain exactly one factor column.")


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing_columns = sorted(set(columns) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
