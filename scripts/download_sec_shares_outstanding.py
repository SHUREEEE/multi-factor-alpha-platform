"""Download SEC companyfacts shares outstanding into fundamentals long format."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SEC_HEADERS = {
    "User-Agent": "multi-factor-alpha-platform research contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SHARES_CONCEPTS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    tickers = _load_tickers(Path(args.tickers), int(args.limit) if args.limit else None)
    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept-Encoding": "gzip, deflate"})
    ticker_map = fetch_sec_ticker_map(session)
    output_path = Path(args.output)
    rows = _load_existing_output(output_path)
    existing_tickers = set(pd.concat(rows, ignore_index=True)["ticker"].unique()) if rows else set()
    missing = []
    for position, ticker in enumerate(tickers, start=1):
        if ticker in existing_tickers and not args.refresh_existing:
            continue
        cik = ticker_map.get(_sec_symbol(ticker))
        if cik is None:
            missing.append({"ticker": ticker, "reason": "missing_cik"})
            continue
        payload = fetch_companyfacts(session, cik, retry_count=int(args.retry_count), sleep_seconds=float(args.retry_sleep_seconds))
        if not payload:
            missing.append({"ticker": ticker, "reason": "download_failed"})
            continue
        ticker_rows = parse_shares_outstanding(payload, ticker)
        if ticker_rows.empty:
            missing.append({"ticker": ticker, "reason": "missing_shares_outstanding"})
        else:
            rows.append(ticker_rows)
            existing_tickers.add(ticker)
        if position % int(args.checkpoint_every) == 0:
            _write_outputs(rows, missing, output_path, Path(args.missing_report), len(tickers))
            print(f"Checkpoint {position}/{len(tickers)} tickers; downloaded={len(existing_tickers)}; missing={len(missing)}", flush=True)
        if args.sleep_seconds > 0 and position < len(tickers):
            time.sleep(float(args.sleep_seconds))
    _write_outputs(rows, missing, output_path, Path(args.missing_report), len(tickers))
    print(f"Saved SEC shares fundamentals to {output_path}")
    print(f"Saved missing report to {Path(args.missing_report)}")
    return 0


def fetch_sec_ticker_map(session: requests.Session) -> dict[str, str]:
    for _ in range(3):
        try:
            response = session.get(SEC_TICKER_MAP_URL, timeout=30)
            response.raise_for_status()
            payload = response.json()
            mapping: dict[str, str] = {}
            for item in payload.values():
                ticker = str(item["ticker"]).upper()
                cik = str(item["cik_str"]).zfill(10)
                mapping[ticker] = cik
                mapping[ticker.replace(".", "-")] = cik
                mapping[ticker.replace("-", ".")] = cik
            return mapping
        except requests.RequestException:
            time.sleep(2.0)
    raise RuntimeError("Failed to download SEC ticker map after retries.")


def fetch_companyfacts(session: requests.Session, cik: str, retry_count: int = 3, sleep_seconds: float = 2.0) -> dict:
    for attempt in range(1, retry_count + 1):
        try:
            response = session.get(SEC_COMPANYFACTS_URL.format(cik=str(cik).zfill(10)), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt < retry_count:
                time.sleep(sleep_seconds * attempt)
    return {}


def parse_shares_outstanding(payload: dict, ticker: str) -> pd.DataFrame:
    """Parse SEC companyfacts shares outstanding facts into long fundamentals."""
    facts = payload.get("facts", {})
    candidates = []
    for taxonomy, concept in SHARES_CONCEPTS:
        concept_payload = facts.get(taxonomy, {}).get(concept, {})
        units = concept_payload.get("units", {})
        for unit_rows in units.values():
            for row in unit_rows:
                value = row.get("val")
                filed = row.get("filed") or row.get("end")
                form = str(row.get("form", ""))
                if value is None or filed is None:
                    continue
                if form and form not in {"10-K", "10-Q", "20-F", "40-F", "10-K/A", "10-Q/A", "10-KT", "10-QT"}:
                    continue
                candidates.append({"date": filed, "ticker": ticker, "field": "shares_outstanding", "value": value})
        if candidates:
            break
    frame = pd.DataFrame(candidates, columns=["date", "ticker", "field", "value"])
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["date", "value"])
    frame = frame[frame["value"] > 0.0]
    return frame.sort_values(["date", "ticker", "field"]).reset_index(drop=True)


def _load_tickers(path: Path, limit: int | None) -> list[str]:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
        if isinstance(frame.index, pd.MultiIndex) and "ticker" in frame.index.names:
            tickers = frame.index.get_level_values("ticker").astype(str).unique().tolist()
        elif "ticker" in frame.columns:
            tickers = frame["ticker"].astype(str).unique().tolist()
        else:
            raise ValueError("ticker parquet must contain ticker column or MultiIndex level.")
    else:
        frame = pd.read_csv(path)
        if "ticker" not in frame.columns:
            raise ValueError("ticker CSV must contain ticker column.")
        tickers = frame["ticker"].astype(str).unique().tolist()
    tickers = sorted({str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()})
    return tickers[:limit] if limit else tickers


def _load_existing_output(path: Path) -> list[pd.DataFrame]:
    if not path.exists():
        return []
    existing = pd.read_parquet(path)
    if existing.empty:
        return []
    return [existing[["date", "ticker", "field", "value"]].copy()]


def _write_outputs(rows: list[pd.DataFrame], missing: list[dict[str, str]], output_path: Path, missing_path: Path, requested_count: int) -> None:
    output = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "ticker", "field", "value"])
    output = output.drop_duplicates(["date", "ticker", "field"], keep="last").sort_values(["date", "ticker", "field"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(output_path, compression="snappy", index=False)
    missing_path.parent.mkdir(parents=True, exist_ok=True)
    missing_path.write_text(
        json.dumps(
            {
                "requested": requested_count,
                "downloaded": int(output["ticker"].nunique()) if not output.empty else 0,
                "missing": missing,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _sec_symbol(ticker: str) -> str:
    return str(ticker).strip().upper().replace("-", ".")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download shares outstanding from SEC companyfacts.")
    parser.add_argument("--tickers", default="data/processed/prices.parquet")
    parser.add_argument("--output", default="data/raw/sec_shares_outstanding.parquet")
    parser.add_argument("--missing-report", default="reports/sec_shares_outstanding_missing.json")
    parser.add_argument("--user-agent", default=SEC_HEADERS["User-Agent"])
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    parser.add_argument("--retry-count", type=int, default=3)
    parser.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--limit", type=int, default=None, help="Optional smoke-test ticker limit.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
