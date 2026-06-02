"""Clean raw market data and enforce point-in-time rules."""

from __future__ import annotations

import pandas as pd


def clean_prices(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Clean OHLCV data and return a MultiIndex frame.

    Parameters
    ----------
    price_frame:
        Long-format raw price data with date, ticker, OHLC, adjusted close, and volume.

    Returns
    -------
    pandas.DataFrame
        Cleaned prices indexed by (date, ticker).
    """
    _require_columns(price_frame, ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])
    cleaned_prices = price_frame.copy()  # 中文：不修改原始输入，便于调试和复现。
    cleaned_prices["date"] = pd.to_datetime(cleaned_prices["date"])  # 中文：统一日期类型，后续才能正确排序和索引。
    cleaned_prices["ticker"] = cleaned_prices["ticker"].astype(str)  # 中文：ticker 必须是字符串，避免数字代码被误处理。
    numeric_columns = ["open", "high", "low", "close", "adj_close", "volume"]  # 中文：价格和成交量必须能做数值计算。
    cleaned_prices[numeric_columns] = cleaned_prices[numeric_columns].apply(pd.to_numeric, errors="coerce")
    cleaned_prices = cleaned_prices.dropna(subset=["date", "ticker", "adj_close"])  # 中文：没有复权价就无法算可靠收益。
    cleaned_prices = cleaned_prices[cleaned_prices["adj_close"] > 0]  # 中文：复权价小于等于 0 在真实股票中不合理。
    cleaned_prices = cleaned_prices[cleaned_prices["volume"].fillna(0) >= 0]  # 中文：成交量不能为负，NaN 暂时按 0 检查。
    cleaned_prices = cleaned_prices.drop_duplicates(subset=["date", "ticker"], keep="last")  # 中文：同一天同股票只保留一条。
    cleaned_prices = cleaned_prices.sort_values(["date", "ticker"])  # 中文：排序让 groupby 和 head 输出更可读。
    cleaned_prices = cleaned_prices.set_index(["date", "ticker"])  # 中文：研究层通常按 date×ticker MultiIndex 工作。
    assert cleaned_prices.index.is_unique, "Processed price index must be unique."
    return cleaned_prices


def compute_returns(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Add daily returns computed from adjusted close.

    Notes
    -----
    This function only computes realized returns. Trading signals must still be
    shifted by one day before use to avoid look-ahead bias.
    """
    if not isinstance(price_frame.index, pd.MultiIndex):
        raise TypeError("price_frame must use MultiIndex(date, ticker).")
    if "adj_close" not in price_frame.columns:
        raise ValueError("price_frame must contain adj_close.")
    prices_with_returns = price_frame.copy()  # 中文：保留原始价格列，新增收益列。
    grouped_adj_close = prices_with_returns["adj_close"].groupby(level="ticker")  # 中文：每只股票单独算收益，不能跨股票相除。
    prices_with_returns["return_1d"] = grouped_adj_close.pct_change()  # 中文：今日收益 = 今日复权价 / 昨日复权价 - 1。
    prices_with_returns["return_1d"] = prices_with_returns["return_1d"].replace([float("inf"), float("-inf")], pd.NA)
    return prices_with_returns


def apply_pit_lag(fundamentals: pd.DataFrame, lag_days: int = 45) -> pd.DataFrame:
    """Lag fundamental data by trading days to reduce look-ahead bias.

    Parameters
    ----------
    fundamentals:
        Long-format fundamentals with date, ticker, field, and value.
    lag_days:
        Number of business days used as publication-delay approximation.

    Returns
    -------
    pandas.DataFrame
        Fundamentals with an available_date column.
    """
    _require_columns(fundamentals, ["date", "ticker", "field", "value"])
    if lag_days < 0:
        raise ValueError("lag_days must be non-negative.")
    lagged_fundamentals = fundamentals.copy()  # 中文：PIT 处理生成新表，不覆盖原始财报日期。
    lagged_fundamentals["date"] = pd.to_datetime(lagged_fundamentals["date"])  # 中文：日期类型才能加交易日偏移。
    lagged_fundamentals["available_date"] = lagged_fundamentals["date"] + pd.offsets.BDay(lag_days)
    lagged_fundamentals = lagged_fundamentals.sort_values(["available_date", "ticker", "field"])
    assert (lagged_fundamentals["available_date"] >= lagged_fundamentals["date"]).all()
    return lagged_fundamentals


def make_daily_fundamentals(
    fundamentals: pd.DataFrame,
    prices: pd.DataFrame,
    lag_days: int = 45,
) -> pd.DataFrame:
    """Convert lagged quarterly fundamentals into a daily PIT panel.

    Parameters
    ----------
    fundamentals:
        Long-format quarterly fundamentals with date, ticker, field, and value.
    prices:
        Processed daily prices indexed by (date, ticker), including adj_close.
    lag_days:
        Minimum business-day lag before fundamental values become usable.

    Returns
    -------
    pandas.DataFrame
        Daily point-in-time fundamentals indexed by (date, ticker).
    """
    _validate_price_index(prices)
    lagged_fundamentals = apply_pit_lag(fundamentals, lag_days=lag_days)
    wide_fundamentals = _pivot_lagged_fundamentals(lagged_fundamentals)
    daily_fundamentals = _align_fundamentals_to_prices(wide_fundamentals, prices)
    daily_fundamentals = _add_market_cap(daily_fundamentals, prices)
    assert daily_fundamentals.index.equals(prices.index)
    return daily_fundamentals


def _validate_price_index(prices: pd.DataFrame) -> None:
    """Validate daily price panel index and market-cap inputs."""
    if not isinstance(prices.index, pd.MultiIndex):
        raise TypeError("prices must use MultiIndex(date, ticker).")
    if prices.index.names != ["date", "ticker"]:
        raise ValueError("prices index names must be ['date', 'ticker'].")
    if "adj_close" not in prices.columns:
        raise ValueError("prices must contain adj_close for market_cap.")


def _pivot_lagged_fundamentals(lagged_fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Pivot lagged long-format fundamentals into wide daily-ready data."""
    wide_fundamentals = lagged_fundamentals.pivot_table(
        index=["available_date", "ticker"],
        columns="field",
        values="value",
        aggfunc="last",
    )
    wide_fundamentals.index = wide_fundamentals.index.set_names(["date", "ticker"])
    return wide_fundamentals.sort_index()


def _align_fundamentals_to_prices(
    wide_fundamentals: pd.DataFrame,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    """Align every ticker's PIT fundamentals to the price index."""
    daily_frames: list[pd.DataFrame] = []
    for ticker, ticker_prices in prices.groupby(level="ticker", sort=False):
        ticker_daily = _align_one_ticker(wide_fundamentals, ticker_prices, str(ticker))
        daily_frames.append(ticker_daily)
    daily_fundamentals = pd.concat(daily_frames).sort_index()
    return daily_fundamentals.reindex(prices.index)


def _align_one_ticker(
    wide_fundamentals: pd.DataFrame,
    ticker_prices: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """Forward-fill one ticker's fundamentals after available_date."""
    price_dates = ticker_prices.index.get_level_values("date")  # 中文：最终日频表必须只保留真实交易日。
    if ticker not in wide_fundamentals.index.get_level_values("ticker"):
        return pd.DataFrame(index=ticker_prices.index)  # 中文：没有基本面时返回空列，保持价格索引完整。
    ticker_fundamentals = wide_fundamentals.xs(ticker, level="ticker")  # 中文：每只股票单独做 as-of 对齐，避免串股票。
    union_dates = price_dates.union(ticker_fundamentals.index)  # 中文：保留财报可用日，否则 ffill 可能找不到起点。
    aligned = ticker_fundamentals.reindex(union_dates).sort_index().ffill().reindex(price_dates)
    aligned["ticker"] = ticker  # 中文：恢复 ticker 层，输出仍然是 date×ticker MultiIndex。
    return aligned.set_index("ticker", append=True)


def _add_market_cap(daily_fundamentals: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Compute daily market cap from shares outstanding and adjusted close."""
    enriched_fundamentals = daily_fundamentals.copy()
    if "shares_outstanding" not in enriched_fundamentals.columns:
        enriched_fundamentals["market_cap"] = pd.NA
        return enriched_fundamentals
    shares = pd.to_numeric(enriched_fundamentals["shares_outstanding"], errors="coerce")
    enriched_fundamentals["market_cap"] = shares * prices["adj_close"]
    return enriched_fundamentals


def _require_columns(frame: pd.DataFrame, required_columns: list[str]) -> None:
    """Raise a clear error when a required input column is missing."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")
    missing_columns = sorted(set(required_columns) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
