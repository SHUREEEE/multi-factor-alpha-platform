"""Compute price-only factors with sector neutralization enabled."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch_ticker_sectors import SECTOR_MAP_PATH  # noqa: E402
from scripts.run_factor_research import PRICE_FACTOR_NAMES  # noqa: E402
from src.factors import BetaInverse, IdiosyncraticVol, Momentum12_1, RealizedVol, ShortTermReversal, Week52High  # noqa: E402
from src.factors.base import BaseFactor  # noqa: E402
from src.factors.utils import apply_full_pipeline  # noqa: E402


PRICES_PATH = PROJECT_ROOT / "data/processed/prices.parquet"
OUTPUT_PATH = PROJECT_ROOT / "data/factor_data/factors_sector_neutral.parquet"


def main() -> None:
    """Compute sector-neutral price-only factors and save a new parquet file."""
    prices = _load_prices(PRICES_PATH)
    sector_map = _load_sector_map(SECTOR_MAP_PATH, _tickers_from_prices(prices))
    _validate_sector_map(sector_map)
    sector_panel = _build_sector_panel(prices.index, sector_map)
    data: dict[str, pd.DataFrame | pd.Series] = {"prices": prices, "industry": sector_panel}
    factors = _compute_price_factors(data)
    shifted_factors = factors.groupby(level="ticker").shift(1)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shifted_factors.to_parquet(OUTPUT_PATH, compression="snappy", index=True)
    logger.info("Saved sector-neutral price factors to {}", OUTPUT_PATH.as_posix())
    logger.info("Factor coverage:\n{}", shifted_factors[PRICE_FACTOR_NAMES].describe().T[["count", "mean", "std"]])


def _load_prices(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing prices file: {path.as_posix()}")
    prices = pd.read_parquet(path)
    if not isinstance(prices.index, pd.MultiIndex):
        raise ValueError("prices.parquet must use MultiIndex(date, ticker).")
    prices.index = prices.index.set_names(["date", "ticker"])
    return prices.sort_index()


def _tickers_from_prices(prices: pd.DataFrame) -> list[str]:
    return sorted(prices.index.get_level_values("ticker").unique().astype(str))


def _load_sector_map(path: Path, tickers: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError("Missing sector map. Run python scripts/fetch_ticker_sectors.py --force-refresh first.")
    sector_map = pd.read_parquet(path)
    missing_tickers = sorted(set(tickers) - set(sector_map["ticker"].astype(str)))
    if missing_tickers:
        raise ValueError(f"Sector map missing {len(missing_tickers)} tickers. Refresh {path.as_posix()}.")
    return sector_map[sector_map["ticker"].isin(tickers)].copy()


def _build_sector_panel(target_index: pd.MultiIndex, sector_map: pd.DataFrame) -> pd.Series:
    if not {"ticker", "sector"}.issubset(sector_map.columns):
        raise ValueError("sector_map must contain ticker and sector columns.")
    ticker_to_sector = sector_map.set_index("ticker")["sector"].astype(str)
    ticker_values = target_index.get_level_values("ticker").astype(str)
    sectors = pd.Series(ticker_values.map(ticker_to_sector).fillna("Unknown"), index=target_index, name="sector")
    return sectors.sort_index()


def _validate_sector_map(sector_map: pd.DataFrame, min_known_ratio: float = 0.8) -> None:
    if sector_map.empty:
        raise ValueError("sector_map is empty; cannot run sector neutralization.")
    known_ratio = float((sector_map["sector"].astype(str) != "Unknown").mean())
    if known_ratio < min_known_ratio:
        raise ValueError(
            f"Only {known_ratio:.1%} of tickers have known sectors. "
            "Refetch data/raw/ticker_sector_map.parquet after Yahoo rate limits clear."
        )


def _compute_price_factors(data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
    processed_factors = []
    for factor in _price_factor_library():
        raw_factor = factor.compute(data)
        sector = data["industry"]
        clean_factor = apply_full_pipeline(raw_factor, sector, market_cap=None)
        processed_factors.append(clean_factor.rename(columns={clean_factor.columns[0]: factor.name}))
        logger.info("Computed sector-neutral {}", factor.name)
    return pd.concat(processed_factors, axis=1).sort_index()


def _price_factor_library() -> list[BaseFactor]:
    return [Momentum12_1(), ShortTermReversal(), Week52High(), IdiosyncraticVol(), BetaInverse(), RealizedVol()]


if __name__ == "__main__":
    main()
