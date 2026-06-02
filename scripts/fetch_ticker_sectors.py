"""Fetch and cache ticker sector classifications.

The first source is the Wikipedia S&P 500 constituent table because it is
stable and includes GICS sectors. yfinance is used only as a fallback for
tickers still missing after the Wikipedia pass.
"""

from __future__ import annotations

import sys
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SECTOR_MAP_PATH = PROJECT_ROOT / "data/raw/ticker_sector_map.parquet"
PRICES_PATH = PROJECT_ROOT / "data/processed/prices.parquet"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
YAHOO_BATCH_SIZE = 20
YAHOO_BATCH_SLEEP_SECONDS = 3.0
YAHOO_RETRY_DELAYS = [2.0, 5.0, 10.0]


def main() -> None:
    """Fetch sectors for all tickers in the current price universe."""
    args = _parse_args()
    prices = pd.read_parquet(PRICES_PATH)
    tickers = sorted(prices.index.get_level_values("ticker").unique().astype(str))
    sector_map = fetch_sector_map(
        tickers=tickers,
        output_path=SECTOR_MAP_PATH,
        force_refresh=args.force_refresh,
        use_wikipedia=not args.skip_wikipedia,
        use_yahoo=not args.skip_yahoo,
    )
    _log_coverage(sector_map)


def _parse_args() -> Namespace:
    parser = ArgumentParser(description="Fetch ticker sector classifications.")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cached parquet and rebuild sector map.")
    parser.add_argument("--skip-wikipedia", action="store_true", help="Skip Wikipedia S&P 500 sector source.")
    parser.add_argument("--skip-yahoo", action="store_true", help="Skip yfinance fallback for missing tickers.")
    return parser.parse_args()


def fetch_sector_map(
    tickers: list[str],
    output_path: Path = SECTOR_MAP_PATH,
    force_refresh: bool = False,
    use_wikipedia: bool = True,
    use_yahoo: bool = True,
) -> pd.DataFrame:
    """Fetch sectors, save progress after each batch, and support resume."""
    sector_map = _initial_sector_map(tickers, output_path, force_refresh)
    if use_wikipedia:
        sector_map = _apply_wikipedia_sectors(sector_map)
        _save_sector_map(sector_map, output_path)
    if use_yahoo:
        sector_map = _apply_yahoo_fallback(sector_map, output_path)
    _save_sector_map(sector_map, output_path)
    return sector_map.sort_values("ticker").reset_index(drop=True)


def _initial_sector_map(tickers: list[str], output_path: Path, force_refresh: bool) -> pd.DataFrame:
    if output_path.exists() and not force_refresh:
        cached = pd.read_parquet(output_path)
        cached = _normalize_sector_map(cached)
    else:
        cached = pd.DataFrame(columns=["ticker", "sector", "sub_industry", "source"])
    known_lookup = cached.set_index("ticker") if not cached.empty else pd.DataFrame()
    rows = [_initial_row(ticker, known_lookup) for ticker in tickers]
    return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)


def _initial_row(ticker: str, known_lookup: pd.DataFrame) -> dict[str, str]:
    if ticker in known_lookup.index:
        row = known_lookup.loc[ticker]
        sector = str(row.get("sector", "Unknown")).strip()
        if sector and sector != "Unknown":
            return {
                "ticker": ticker,
                "sector": sector,
                "sub_industry": str(row.get("sub_industry", "Unknown")).strip() or "Unknown",
                "source": str(row.get("source", "cache")).strip() or "cache",
            }
    return {"ticker": ticker, "sector": "Unknown", "sub_industry": "Unknown", "source": "missing"}


def _apply_wikipedia_sectors(sector_map: pd.DataFrame) -> pd.DataFrame:
    wiki_map = _fetch_sp500_wikipedia_map()
    if wiki_map.empty:
        logger.warning("Wikipedia sector map is empty; continuing to yfinance fallback.")
        return sector_map
    enriched = sector_map.merge(wiki_map, on="ticker", how="left", suffixes=("", "_wiki"))
    missing_mask = enriched["sector"].eq("Unknown") & enriched["sector_wiki"].notna()
    enriched.loc[missing_mask, "sector"] = enriched.loc[missing_mask, "sector_wiki"]
    enriched.loc[missing_mask, "sub_industry"] = enriched.loc[missing_mask, "sub_industry_wiki"]
    enriched.loc[missing_mask, "source"] = "wikipedia_sp500"
    output = enriched[["ticker", "sector", "sub_industry", "source"]]
    logger.info("Wikipedia filled {} sectors.", int(missing_mask.sum()))
    return output.sort_values("ticker").reset_index(drop=True)


def _fetch_sp500_wikipedia_map() -> pd.DataFrame:
    try:
        request = Request(SP500_WIKI_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            tables = pd.read_html(response)
    except Exception as error:  # noqa: BLE001
        logger.warning("Failed to read S&P 500 Wikipedia table: {}", error)
        return pd.DataFrame(columns=["ticker", "sector", "sub_industry"])
    for table in tables:
        if {"Symbol", "GICS Sector", "GICS Sub-Industry"}.issubset(table.columns):
            return _format_wikipedia_table(table)
    logger.warning("Could not find expected GICS columns in Wikipedia tables.")
    return pd.DataFrame(columns=["ticker", "sector", "sub_industry"])


def _format_wikipedia_table(table: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(
        {
            "ticker": table["Symbol"].astype(str).str.replace(".", "-", regex=False).str.strip(),
            "sector": table["GICS Sector"].astype(str).str.strip(),
            "sub_industry": table["GICS Sub-Industry"].astype(str).str.strip(),
        }
    )
    return output.drop_duplicates(subset=["ticker"]).sort_values("ticker").reset_index(drop=True)


def _apply_yahoo_fallback(sector_map: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    pending_tickers = sector_map.loc[sector_map["sector"].eq("Unknown"), "ticker"].tolist()
    logger.info("yfinance fallback pending tickers: {}", len(pending_tickers))
    for batch_start in range(0, len(pending_tickers), YAHOO_BATCH_SIZE):
        batch = pending_tickers[batch_start : batch_start + YAHOO_BATCH_SIZE]
        sector_map = _fetch_yahoo_batch(sector_map, batch)
        _save_sector_map(sector_map, output_path)
        _log_coverage(sector_map)
        if batch_start + YAHOO_BATCH_SIZE < len(pending_tickers):
            time.sleep(YAHOO_BATCH_SLEEP_SECONDS)
    return sector_map


def _fetch_yahoo_batch(sector_map: pd.DataFrame, batch: list[str]) -> pd.DataFrame:
    for ticker in batch:
        sector, source = _fetch_yahoo_sector_with_retry(ticker)
        if sector != "Unknown":
            sector_map.loc[sector_map["ticker"].eq(ticker), "sector"] = sector
            sector_map.loc[sector_map["ticker"].eq(ticker), "source"] = source
    return sector_map


def _fetch_yahoo_sector_with_retry(ticker: str) -> tuple[str, str]:
    for attempt_number, delay_seconds in enumerate([0.0, *YAHOO_RETRY_DELAYS], start=1):
        if delay_seconds:
            time.sleep(delay_seconds)
        try:
            info = yf.Ticker(ticker).info
            sector = info.get("sector") if isinstance(info, dict) else None
            clean_sector = str(sector).strip() if sector else "Unknown"
            if clean_sector != "Unknown":
                return clean_sector, "yfinance"
            logger.warning("Missing sector for {} on attempt {}.", ticker, attempt_number)
        except Exception as error:  # noqa: BLE001
            logger.warning("Failed to fetch sector for {} on attempt {}: {}", ticker, attempt_number, error)
    logger.warning("Persistent failure for {}; assigning Unknown.", ticker)
    return "Unknown", "unknown"


def _normalize_sector_map(sector_map: pd.DataFrame) -> pd.DataFrame:
    output = sector_map.copy()
    if "sub_industry" not in output.columns:
        output["sub_industry"] = "Unknown"
    if "source" not in output.columns:
        output["source"] = "cache"
    output["ticker"] = output["ticker"].astype(str).str.strip()
    output["sector"] = output["sector"].fillna("Unknown").astype(str).str.strip()
    output["sub_industry"] = output["sub_industry"].fillna("Unknown").astype(str).str.strip()
    output["source"] = output["source"].fillna("cache").astype(str).str.strip()
    return output[["ticker", "sector", "sub_industry", "source"]]


def _save_sector_map(sector_map: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _normalize_sector_map(sector_map).to_parquet(output_path, compression="snappy", index=False)
    logger.info("Saved partial sector map to {}", output_path.as_posix())


def _log_coverage(sector_map: pd.DataFrame) -> None:
    total_count = int(sector_map.shape[0])
    valid_count = int((sector_map["sector"] != "Unknown").sum())
    unknown_count = total_count - valid_count
    coverage_ratio = valid_count / total_count if total_count else 0.0
    logger.info("Total tickers: {}", total_count)
    logger.info("Tickers with valid sector: {}", valid_count)
    logger.warning("Tickers still Unknown: {}", unknown_count)
    logger.info("Coverage ratio: {:.1%}", coverage_ratio)


if __name__ == "__main__":
    main()
