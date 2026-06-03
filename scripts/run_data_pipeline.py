"""Run the Day 1 data ingestion pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.cleaner import apply_pit_lag, clean_prices, compute_returns, make_daily_fundamentals
from src.data.fundamentals_contract import validate_daily_fundamentals
from src.data.downloader import (
    YFinanceDownloader,
    get_nasdaq100_tickers,
    get_sp500_tickers,
)
from src.data.universe import Universe


def parse_args() -> argparse.Namespace:
    """Parse PowerShell-friendly CLI arguments."""
    parser = argparse.ArgumentParser(description="Run US equity data pipeline.")
    parser.add_argument("--config", default="config/universe.yaml")
    parser.add_argument("--skip-fundamentals", action="store_true")
    parser.add_argument("--max-tickers", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    """Download, clean, and save raw and processed datasets."""
    args = parse_args()  # 中文：CLI 参数让你可以先跑少量股票测试，再跑完整 universe。
    config = _load_config(args.config)  # 中文：把日期、路径、股票池放配置文件，避免硬编码。
    raw_dir = Path(config["data"]["raw_dir"])  # 中文：raw 数据保留下载原貌，方便排查。
    processed_dir = Path(config["data"]["processed_dir"])  # 中文：processed 数据给研究模块直接使用。
    tickers = _build_ticker_list(config, args.max_tickers)  # 中文：合并 S&P 500、NASDAQ-100 和手动名单。
    universe = Universe.from_tickers(tickers, name=config["universe"]["name"])  # 中文：用类封装股票池逻辑，便于以后升级。
    active_tickers = universe.get_active_tickers(config["dates"]["start"])  # 中文：现在是静态 universe，接口先按 PIT 方式设计。
    downloader = YFinanceDownloader(
        retry_count=int(config["download"]["retry_count"]),
        sleep_seconds=float(config["download"]["api_sleep_seconds"]),
    )
    logger.info("Downloading prices for {} tickers.", len(active_tickers))
    raw_prices = downloader.download_prices(
        active_tickers,
        config["dates"]["start"],
        config["dates"]["end"],
        raw_dir / "prices_raw.parquet",
    )
    processed_prices = compute_returns(clean_prices(raw_prices))  # 中文：先清洗再算收益，避免坏价格制造极端收益。
    _save_processed(processed_prices, processed_dir / config["data"]["price_file"])  # 中文：处理后数据保留 MultiIndex。
    logger.info("Processed prices shape: {}", processed_prices.shape)
    logger.info("Processed prices head:\n{}", processed_prices.head())
    if not args.skip_fundamentals:
        _run_fundamental_pipeline(config, downloader, active_tickers, raw_dir, processed_dir, processed_prices)


def _load_config(config_path: str | Path) -> dict[str, Any]:
    with Path(config_path).open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)  # 中文：YAML 比代码更适合让初学者修改参数。


def _build_ticker_list(config: dict[str, Any], max_tickers: int | None) -> list[str]:
    ticker_sources = config["universe"]["sources"]
    tickers: list[str] = []  # 中文：先收集所有来源，再统一去重和排除。
    if ticker_sources["sp500"]["enabled"]:
        tickers.extend(get_sp500_tickers())
    if ticker_sources["nasdaq100"]["enabled"]:
        tickers.extend(get_nasdaq100_tickers())
    tickers.extend(config["universe"]["manual_include"])
    excluded = set(config["universe"]["manual_exclude"])  # 中文：set 查询更快，也表达“黑名单”的含义。
    cleaned_tickers = sorted({ticker for ticker in tickers if ticker not in excluded})  # 中文：去重后排序保证输出稳定。
    return cleaned_tickers[:max_tickers] if max_tickers else cleaned_tickers


def _run_fundamental_pipeline(
    config: dict[str, Any],
    downloader: YFinanceDownloader,
    tickers: list[str],
    raw_dir: Path,
    processed_dir: Path,
    processed_prices: pd.DataFrame,
) -> None:
    logger.info("Downloading fundamentals for {} tickers.", len(tickers))
    raw_fundamentals = downloader.download_fundamentals(tickers, raw_dir / "fundamentals_raw.parquet")
    lag_days = int(config["research"]["fundamental_lag_trading_days"])
    processed_fundamentals = apply_pit_lag(raw_fundamentals, lag_days=lag_days)
    _save_processed(processed_fundamentals, processed_dir / config["data"]["fundamental_file"])
    daily_fundamentals = make_daily_fundamentals(raw_fundamentals, processed_prices, lag_days=lag_days)
    _save_processed(daily_fundamentals, processed_dir / config["data"]["daily_fundamental_file"])
    contract_report = validate_daily_fundamentals(daily_fundamentals, price_index=processed_prices.index)
    _write_contract_report(contract_report.to_dict(), processed_dir / "daily_fundamentals_contract.json")
    logger.info("Processed fundamentals shape: {}", processed_fundamentals.shape)
    logger.info("Daily PIT fundamentals shape: {}", daily_fundamentals.shape)
    logger.info("Daily PIT fundamentals contract: {}", contract_report.to_dict())
    logger.info("Daily PIT fundamentals head:\n{}", daily_fundamentals.head())


def _save_processed(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, compression="snappy", index=True)


def _write_contract_report(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
