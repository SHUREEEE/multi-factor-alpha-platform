"""Download market and fundamental data for the alpha research platform."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from loguru import logger


PRICE_COLUMNS: list[str] = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
]

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


class DataDownloader(ABC):
    """Abstract downloader interface for future paid data vendors."""

    @abstractmethod
    def download_prices(
        self,
        tickers: list[str],
        start: str,
        end: str,
        output_path: str | Path,
    ) -> pd.DataFrame:
        """Download daily OHLCV data."""

    @abstractmethod
    def download_fundamentals(
        self,
        tickers: list[str],
        output_path: str | Path,
    ) -> pd.DataFrame:
        """Download fundamental data."""


class YFinanceDownloader(DataDownloader):
    """Downloader backed by Yahoo chart data, with yfinance fallbacks."""

    def __init__(self, retry_count: int = 3, sleep_seconds: float = 0.5) -> None:
        self.retry_count = retry_count
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()
        self.session.headers.update(HTTP_HEADERS)

    def download_prices(
        self,
        tickers: list[str],
        start: str,
        end: str,
        output_path: str | Path,
    ) -> pd.DataFrame:
        """Download daily OHLCV and save long-format Parquet."""
        _validate_tickers(tickers)
        price_frames: list[pd.DataFrame] = []
        for ticker in tickers:
            price_frame = self._download_one_price(ticker, start, end)
            if not price_frame.empty:
                price_frames.append(price_frame)
            else:
                logger.warning("No price data downloaded for {}.", ticker)
            time.sleep(self.sleep_seconds)
        combined_prices = _concat_or_empty(price_frames, PRICE_COLUMNS)
        _save_parquet(combined_prices, output_path)
        return combined_prices

    def download_fundamentals(
        self,
        tickers: list[str],
        output_path: str | Path,
    ) -> pd.DataFrame:
        """Download quarterly fundamentals and save long-format Parquet."""
        _validate_tickers(tickers)
        fundamental_frames: list[pd.DataFrame] = []
        for ticker in tickers:
            fundamental_frame = self._download_one_fundamental(ticker)
            if not fundamental_frame.empty:
                fundamental_frames.append(fundamental_frame)
            time.sleep(self.sleep_seconds)
        combined_fundamentals = _concat_or_empty(fundamental_frames, ["date", "ticker", "field", "value"])
        _save_parquet(combined_fundamentals, output_path)
        return combined_fundamentals

    def _download_one_price(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        for attempt_number in range(1, self.retry_count + 1):
            raw_prices = self._download_with_chart_api(ticker, start, end)
            if not raw_prices.empty:
                return raw_prices

            raw_prices = self._download_with_yfinance(ticker, start, end)
            if not raw_prices.empty:
                return _format_price_frame(raw_prices, ticker)

            if attempt_number < self.retry_count:
                time.sleep(2.0 * attempt_number)
        return pd.DataFrame(columns=PRICE_COLUMNS)

    def _download_with_yfinance(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        import yfinance as yf

        try:
            return yf.download(
                ticker,
                start=start,
                end=_inclusive_end_date(end),
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:
            logger.debug("yfinance failed for {}: {}", ticker, exc)
            return pd.DataFrame()

    def _download_with_chart_api(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        start_epoch = int(pd.Timestamp(start, tz="UTC").timestamp())
        end_epoch = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "period1": start_epoch,
            "period2": end_epoch,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return _format_chart_response(response.json(), ticker)
        except Exception as exc:
            logger.debug("Yahoo chart API failed for {}: {}", ticker, exc)
            return pd.DataFrame(columns=PRICE_COLUMNS)

    def _download_one_fundamental(self, ticker: str) -> pd.DataFrame:
        import yfinance as yf

        for attempt_number in range(1, self.retry_count + 1):
            try:
                yahoo_ticker = yf.Ticker(ticker)
                fundamental_frame = _format_fundamental_frame(
                    ticker,
                    yahoo_ticker.quarterly_financials,
                    yahoo_ticker.quarterly_balance_sheet,
                )
                if not fundamental_frame.empty:
                    return fundamental_frame
            except Exception as exc:
                logger.debug("Fundamental download failed for {}: {}", ticker, exc)
            if attempt_number < self.retry_count:
                time.sleep(2.0 * attempt_number)
        return pd.DataFrame(columns=["date", "ticker", "field", "value"])


def download_prices(
    tickers: Iterable[str],
    start: str,
    end: str,
    output_path: str | Path,
) -> pd.DataFrame:
    """Download prices with the default yfinance downloader."""
    downloader = YFinanceDownloader()
    return downloader.download_prices(list(tickers), start, end, output_path)


def download_fundamentals(tickers: Iterable[str], output_path: str | Path) -> pd.DataFrame:
    """Download fundamentals with the default yfinance downloader.

    Notes
    -----
    yfinance 财务数据有限：字段可能缺失、可能被重述，也不是真正的
    point-in-time vendor data，所以只能用于教学和项目原型。
    """
    downloader = YFinanceDownloader()
    return downloader.download_fundamentals(list(tickers), output_path)


def get_sp500_tickers() -> list[str]:
    """Scrape the current S&P 500 ticker list from Wikipedia."""
    tables = _read_html_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    constituents = tables[0]
    return _standardize_tickers(constituents["Symbol"].tolist())


def get_nasdaq100_tickers() -> list[str]:
    """Scrape the current NASDAQ-100 ticker list from Wikipedia."""
    tables = _read_html_tables("https://en.wikipedia.org/wiki/Nasdaq-100")
    for table in tables:
        if "Ticker" in table.columns:
            return _standardize_tickers(table["Ticker"].tolist())
        if "Symbol" in table.columns:
            return _standardize_tickers(table["Symbol"].tolist())
    raise ValueError("Could not find NASDAQ-100 ticker column on Wikipedia.")


def _read_html_tables(url: str) -> list[pd.DataFrame]:
    """Read HTML tables with browser-like headers."""
    response = requests.get(url, headers=HTTP_HEADERS, timeout=30)
    response.raise_for_status()
    return pd.read_html(StringIO(response.text))


def _format_price_frame(raw_prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalize yfinance price output into platform schema."""
    if raw_prices.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    normalized_prices = raw_prices.reset_index()
    normalized_prices.columns = [_normalize_column_name(column) for column in normalized_prices.columns]
    normalized_prices["ticker"] = ticker
    return normalized_prices[PRICE_COLUMNS]


def _format_chart_response(payload: dict, ticker: str) -> pd.DataFrame:
    """Normalize Yahoo chart API JSON into platform schema."""
    result = payload.get("chart", {}).get("result") or []
    if not result:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = chart.get("indicators", {}).get("adjclose") or [{}]
    adj_close = adjusted[0].get("adjclose", quote.get("close", []))
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize(),
            "ticker": ticker,
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "adj_close": adj_close,
            "volume": quote.get("volume", []),
        }
    )
    return frame.dropna(subset=["close", "adj_close"])[PRICE_COLUMNS]


def _format_fundamental_frame(
    ticker: str,
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
) -> pd.DataFrame:
    """Extract selected quarterly financial statement rows."""
    selected_rows = {
        "Total Revenue": "revenue",
        "Net Income": "net_income",
        "Total Assets": "total_assets",
        "Stockholders Equity": "book_value",
        "Ordinary Shares Number": "shares_outstanding",
        "Share Issued": "shares_outstanding",
    }
    long_frames = [
        _select_fundamental_rows(financials, ticker, selected_rows),
        _select_fundamental_rows(balance_sheet, ticker, selected_rows),
    ]
    combined = _concat_or_empty(long_frames, ["date", "ticker", "field", "value"])
    return combined.drop_duplicates(["date", "ticker", "field"], keep="last")


def _select_fundamental_rows(
    source_frame: pd.DataFrame,
    ticker: str,
    row_map: dict[str, str],
) -> pd.DataFrame:
    """Select and reshape available financial statement rows."""
    if source_frame.empty:
        return pd.DataFrame(columns=["date", "ticker", "field", "value"])
    available_rows = [row for row in row_map if row in source_frame.index]
    if not available_rows:
        return pd.DataFrame(columns=["date", "ticker", "field", "value"])
    selected = source_frame.loc[available_rows].rename(index=row_map)
    long_frame = selected.T.reset_index(names="date").melt(id_vars="date", var_name="field", value_name="value")
    long_frame["ticker"] = ticker
    return long_frame[["date", "ticker", "field", "value"]]


def _normalize_column_name(column: object) -> str:
    """Normalize vendor column names to snake_case."""
    if isinstance(column, tuple):
        column = next((part for part in column if part), column[0])
    return str(column).lower().replace(" ", "_")


def _standardize_tickers(raw_tickers: Iterable[str]) -> list[str]:
    """Convert ticker symbols into Yahoo-compatible format."""
    tickers = [str(ticker).strip().replace(".", "-") for ticker in raw_tickers]
    return sorted({ticker for ticker in tickers if ticker and ticker != "nan"})


def _inclusive_end_date(end: str) -> str:
    """Convert user-facing inclusive end date into yfinance right-open end."""
    end_timestamp = pd.Timestamp(end)
    return (end_timestamp + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _validate_tickers(tickers: list[str]) -> None:
    """Validate ticker input before slow network calls."""
    if not isinstance(tickers, list):
        raise TypeError("tickers must be a list[str].")
    if not tickers:
        raise ValueError("tickers cannot be empty.")
    assert all(isinstance(ticker, str) for ticker in tickers), "Every ticker must be a string."


def _concat_or_empty(frames: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    """Concatenate non-empty frames while preserving an empty schema."""
    valid_frames = [frame for frame in frames if not frame.empty]
    if not valid_frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(valid_frames, ignore_index=True)


def _save_parquet(frame: pd.DataFrame, output_path: str | Path) -> None:
    """Save a frame as snappy-compressed Parquet."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, compression="snappy", index=False)
