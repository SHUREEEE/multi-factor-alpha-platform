"""Compute and preprocess all Pillar 2 style factors."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors import (  # noqa: E402
    Accruals,
    BaseFactor,
    BetaInverse,
    BookToMarket,
    EarningsYield,
    GrossProfitability,
    IdiosyncraticVol,
    LogMarketCap,
    LogRevenue,
    LogTotalAssets,
    Momentum12_1,
    ROE,
    RealizedVol,
    SalesToPrice,
    ShortTermReversal,
    Week52High,
)
from src.factors.utils import apply_full_pipeline, build_daily_fundamental_panels  # noqa: E402
from scripts.compute_sector_neutral_price_factors import _build_sector_panel, _load_sector_map  # noqa: E402
from scripts.fetch_ticker_sectors import SECTOR_MAP_PATH  # noqa: E402

PRICES_PATH = PROJECT_ROOT / "data/processed/prices.parquet"
FUNDAMENTALS_PATH = PROJECT_ROOT / "data/processed/fundamentals.parquet"
DAILY_FUNDAMENTALS_PATH = PROJECT_ROOT / "data/processed/daily_fundamentals.parquet"
FACTORS_PATH = PROJECT_ROOT / "data/factor_data/factors.parquet"
LEGACY_FACTORS_PATH = PROJECT_ROOT / "data/factor_data/all_factors.parquet"
SECTOR_NEUTRAL_FACTORS_PATH = PROJECT_ROOT / "data/factor_data/factors_full_sector_neutral.parquet"
FACTOR_REQUIREMENTS = {
    "book_to_market": ["book_value", "market_cap"],
    "earnings_yield": ["net_income", "market_cap"],
    "sales_to_price": ["revenue", "market_cap"],
    "momentum_12_1": ["prices"],
    "short_term_reversal": ["prices"],
    "week_52_high": ["prices"],
    "roe": ["net_income", "book_value"],
    "gross_profitability": ["gross_profit", "total_assets"],
    "accruals": ["net_income", "operating_cashflow", "total_assets"],
    "idiosyncratic_vol": ["prices"],
    "beta_inverse": ["prices"],
    "realized_vol": ["prices"],
    "log_market_cap": ["market_cap"],
    "log_total_assets": ["total_assets"],
    "log_revenue": ["revenue"],
}


def main() -> None:
    """Run the full factor computation pipeline."""
    prices = _load_prices(PRICES_PATH)
    fundamentals = _load_fundamentals(DAILY_FUNDAMENTALS_PATH, FUNDAMENTALS_PATH)
    data = _build_factor_data(prices, fundamentals)
    raw_factors = _compute_and_preprocess(data, neutralize_with_sector=False)
    sector_data = _add_sector_neutralizer(data, prices)
    sector_neutral_factors = _compute_and_preprocess(sector_data, neutralize_with_sector=True)
    shifted_factors = raw_factors.groupby(level="ticker").shift(1)
    shifted_sector_neutral = sector_neutral_factors.groupby(level="ticker").shift(1)
    _validate_factor_output(shifted_factors)
    _validate_factor_output(shifted_sector_neutral)
    _save_factors(shifted_factors, FACTORS_PATH)
    _save_factors(shifted_factors, LEGACY_FACTORS_PATH)
    _save_factors(shifted_sector_neutral, SECTOR_NEUTRAL_FACTORS_PATH)
    _print_summary(shifted_factors)


def _load_prices(path: Path) -> pd.DataFrame:
    """Load processed prices with a strict MultiIndex check."""
    if not path.exists():
        raise FileNotFoundError(f"Missing prices file: {path}")
    prices = pd.read_parquet(path)
    if not isinstance(prices.index, pd.MultiIndex):
        raise ValueError("prices.parquet must use MultiIndex(date, ticker).")
    prices.index = prices.index.set_names(["date", "ticker"])
    if prices.index.has_duplicates:
        raise ValueError("prices.parquet contains duplicate (date, ticker) rows.")
    logger.info("Loaded prices from {} with shape {}", path.as_posix(), prices.shape)
    return prices.sort_index()


def _load_fundamentals(daily_path: Path, long_path: Path) -> pd.DataFrame:
    """Load daily PIT fundamentals if available, otherwise lagged long fundamentals."""
    if daily_path.exists():
        fundamentals = pd.read_parquet(daily_path)
        logger.info("Loaded daily PIT fundamentals from {} with shape {}", daily_path.as_posix(), fundamentals.shape)
        return fundamentals
    if not long_path.exists():
        logger.warning("No fundamentals found; fundamental factors will be NaN.")
        return pd.DataFrame(columns=["date", "ticker", "field", "value", "available_date"])
    fundamentals = pd.read_parquet(long_path)
    if fundamentals.empty:
        logger.warning("fundamentals.parquet is empty; fundamental factors will be NaN.")
    else:
        logger.info("Loaded lagged long fundamentals from {} with shape {}", long_path.as_posix(), fundamentals.shape)
    return fundamentals


def _build_factor_data(prices: pd.DataFrame, fundamentals: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    """Build the input dictionary consumed by all factor classes."""
    data: dict[str, pd.DataFrame | pd.Series] = {"prices": prices}
    if isinstance(fundamentals.index, pd.MultiIndex):
        fundamentals.index = fundamentals.index.set_names(["date", "ticker"])
        data.update({column: fundamentals[column] for column in fundamentals.columns})
    else:
        data.update(build_daily_fundamental_panels(fundamentals, prices.index))
    if "market_cap" not in data:
        logger.warning("market_cap missing; value and market-cap size factors will be NaN.")
    if "industry" not in data:
        logger.warning("industry missing; pipeline will use only available neutralizers.")
    return data


def _compute_and_preprocess(data: dict[str, pd.DataFrame | pd.Series], neutralize_with_sector: bool) -> pd.DataFrame:
    """Compute every raw factor, then apply winsorize -> neutralize -> zscore."""
    processed_factors: list[pd.DataFrame] = []
    skipped_factors: list[str] = []
    for factor in _factor_library():
        if not _requirements_available(factor.name, data):
            skipped_factors.append(factor.name)
            continue
        try:
            raw_factor = factor.compute(data)
            if raw_factor.notna().sum().sum() == 0:
                logger.warning("Skipping {} because computed values are all NaN.", factor.name)
                skipped_factors.append(factor.name)
                continue
            industry = data.get("industry") if neutralize_with_sector and isinstance(data.get("industry"), (pd.Series, pd.DataFrame)) else None
            market_cap = data.get("market_cap") if isinstance(data.get("market_cap"), (pd.Series, pd.DataFrame)) else None
            clean_factor = apply_full_pipeline(raw_factor, industry, market_cap)
            processed_factors.append(clean_factor.rename(columns={clean_factor.columns[0]: factor.name}))
            logger.info("Computed {}", factor.name)
        except Exception as error:  # noqa: BLE001
            logger.warning("Skipping {} because computation failed: {}", factor.name, error)
            skipped_factors.append(factor.name)
    logger.info("{} factors computed; {} skipped.", len(processed_factors), len(skipped_factors))
    if skipped_factors:
        logger.warning("Skipped factors: {}", ", ".join(skipped_factors))
    if not processed_factors:
        raise ValueError("No factors were computed.")
    return pd.concat(processed_factors, axis=1).sort_index()


def _requirements_available(factor_name: str, data: dict[str, pd.DataFrame | pd.Series]) -> bool:
    required_fields = FACTOR_REQUIREMENTS[factor_name]
    missing_fields = [field for field in required_fields if not _field_available(field, data)]
    if missing_fields:
        logger.warning("Skipping {} due to missing fields: {}", factor_name, ", ".join(missing_fields))
        return False
    return True


def _field_available(field: str, data: dict[str, pd.DataFrame | pd.Series]) -> bool:
    if field == "prices":
        return isinstance(data.get("prices"), pd.DataFrame)
    value = data.get(field)
    if isinstance(value, pd.DataFrame):
        return bool(value.notna().any().any())
    if isinstance(value, pd.Series):
        return bool(value.notna().any())
    return False


def _add_sector_neutralizer(data: dict[str, pd.DataFrame | pd.Series], prices: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    output = dict(data)
    try:
        tickers = sorted(prices.index.get_level_values("ticker").unique().astype(str))
        sector_map = _load_sector_map(SECTOR_MAP_PATH, tickers)
        output["industry"] = _build_sector_panel(prices.index, sector_map)
        logger.info("Added sector neutralizer from {}", SECTOR_MAP_PATH.as_posix())
    except Exception as error:  # noqa: BLE001
        logger.warning("Sector neutralizer unavailable: {}", error)
    return output


def _factor_library() -> list[BaseFactor]:
    """Return the ordered Pillar 2 factor library."""
    return [
        BookToMarket(),
        EarningsYield(),
        SalesToPrice(),
        Momentum12_1(),
        ShortTermReversal(),
        Week52High(),
        ROE(),
        GrossProfitability(),
        Accruals(),
        IdiosyncraticVol(),
        BetaInverse(),
        RealizedVol(),
        LogMarketCap(),
        LogTotalAssets(),
        LogRevenue(),
    ]


def _validate_factor_output(factors: pd.DataFrame) -> None:
    """Validate the saved factor panel contract."""
    if not isinstance(factors.index, pd.MultiIndex):
        raise ValueError("factors must use MultiIndex(date, ticker).")
    if list(factors.index.names) != ["date", "ticker"]:
        raise ValueError("factor index names must be ['date', 'ticker'].")
    if factors.index.has_duplicates:
        raise ValueError("factor index contains duplicate (date, ticker) rows.")
    date_has_values = factors.notna().any(axis=1).groupby(level="date").any()
    usable_date_ratio = float(date_has_values.mean())
    if usable_date_ratio < 0.5:
        raise ValueError("less than half of dates have any non-empty factor values.")
    logger.info("{:.1%} of dates have at least one non-empty factor value.", usable_date_ratio)


def _save_factors(factors: pd.DataFrame, path: Path) -> None:
    """Save factors as compressed parquet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    factors.to_parquet(path, compression="snappy", index=True)
    logger.info("Saved factors to {}", path.as_posix())


def _print_summary(factors: pd.DataFrame) -> None:
    """Log shape, summary statistics, and known data limitations."""
    logger.info("Factor shape: {}", factors.shape)
    logger.info("Factor summary statistics:\n{}", factors.describe().T[["count", "mean", "std", "min", "max"]])
    logger.info("Low beta market proxy: external market_returns if provided; otherwise equal-weight universe return.")
    logger.info("Bias note: Yahoo/free-data universe can contain survivorship bias.")


if __name__ == "__main__":
    main()
