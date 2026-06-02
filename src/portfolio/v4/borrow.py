"""V4 short concentration and PB borrow controls.

D3 keeps borrow and concentration as rule-based post-optimizer controls. These
functions never substitute ADV or market cap for PB borrow availability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


PASS = "PASS"
FAIL = "FAIL"
BORROW_REQUIRED_COLUMNS = {
    "date",
    "symbol",
    "locate_available_shares",
    "borrow_rate_bps",
    "utilization_pct",
    "htb_flag",
    "feed_timestamp_utc",
}


class BorrowFeedSchemaError(ValueError):
    """Raised when the PB borrow feed does not match the required schema."""


@dataclass(frozen=True)
class ShortConcentrationResult:
    """Short concentration check and optional enforcement result."""

    top10_share: float
    max_single_share: float
    top10_pass: bool
    single_name_pass: bool
    violating_symbols: list[str]
    enforced_weights: pd.Series | None = None


@dataclass(frozen=True)
class BorrowCapResult:
    """PB borrow-cap result for one decision date."""

    blocked_symbols: list[str]
    htb_symbols: list[str]
    htb_notional_share: float
    htb_cap_pass: bool
    locate_violations: list[str]
    utilization_warnings: list[str]
    enforced_weights: pd.Series
    feed_freshness_pass: bool
    locate_check_mode: Literal["binary", "shares"]


def enforce_short_concentration_limits(
    weights: pd.Series,
    *,
    top10_cap: float = 0.25,
    single_name_cap: float = 0.05,
    mode: Literal["check", "enforce"] = "check",
) -> ShortConcentrationResult:
    """Evaluate and optionally enforce short-book concentration limits."""
    if not 0.0 < top10_cap <= 1.0:
        raise ValueError("top10_cap must be in (0, 1].")
    if not 0.0 < single_name_cap <= 1.0:
        raise ValueError("single_name_cap must be in (0, 1].")
    if mode not in {"check", "enforce"}:
        raise ValueError("mode must be 'check' or 'enforce'.")

    clean = weights.fillna(0.0).astype(float).copy()
    metrics = _short_metrics(clean)
    violating = _violating_short_symbols(clean, metrics["short_total"], top10_cap, single_name_cap)
    top10_pass = metrics["top10_share"] <= top10_cap + 1e-12
    single_pass = metrics["max_single_share"] <= single_name_cap + 1e-12
    if mode == "check":
        return ShortConcentrationResult(
            top10_share=metrics["top10_share"],
            max_single_share=metrics["max_single_share"],
            top10_pass=top10_pass,
            single_name_pass=single_pass,
            violating_symbols=violating,
            enforced_weights=None,
        )

    enforced = clean.copy()
    short_total = metrics["short_total"]
    if short_total <= 0.0:
        return ShortConcentrationResult(0.0, 0.0, True, True, [], enforced)

    enforced = _enforce_single_short_cap(enforced, short_total, single_name_cap)
    if enforced is None:
        return ShortConcentrationResult(
            top10_share=metrics["top10_share"],
            max_single_share=metrics["max_single_share"],
            top10_pass=top10_pass,
            single_name_pass=False,
            violating_symbols=violating,
            enforced_weights=None,
        )

    enforced = _enforce_top10_short_cap(enforced, short_total, top10_cap)
    if enforced is None:
        return ShortConcentrationResult(
            top10_share=metrics["top10_share"],
            max_single_share=metrics["max_single_share"],
            top10_pass=False,
            single_name_pass=True,
            violating_symbols=violating,
            enforced_weights=None,
        )

    final = _short_metrics(enforced)
    final_violating = _violating_short_symbols(enforced, short_total, top10_cap, single_name_cap)
    return ShortConcentrationResult(
        top10_share=final["top10_share"],
        max_single_share=final["max_single_share"],
        top10_pass=final["top10_share"] <= top10_cap + 1e-12,
        single_name_pass=final["max_single_share"] <= single_name_cap + 1e-12,
        violating_symbols=final_violating,
        enforced_weights=enforced,
    )


def apply_pb_borrow_caps(
    weights: pd.Series,
    borrow_feed: pd.DataFrame,
    *,
    asof_date: pd.Timestamp,
    htb_notional_cap: float = 0.25,
    feed_max_age_days: int = 1,
    aum_usd: float,
    gross: float,
    prices: pd.Series | None = None,
) -> BorrowCapResult:
    """Apply PB locate, HTB, freshness, and missing-data blocks to shorts."""
    if not 0.0 <= htb_notional_cap <= 1.0:
        raise ValueError("htb_notional_cap must be in [0, 1].")
    if feed_max_age_days < 0:
        raise ValueError("feed_max_age_days must be non-negative.")
    if aum_usd <= 0.0:
        raise ValueError("aum_usd must be positive.")
    if gross <= 0.0:
        raise ValueError("gross must be positive.")

    feed = _validate_borrow_feed_schema(borrow_feed)
    clean = weights.fillna(0.0).astype(float).copy()
    short_abs = _short_abs(clean)
    active_shorts = short_abs[short_abs > 0.0]
    feed_by_symbol = feed.drop_duplicates("symbol", keep="last").set_index("symbol")
    enforced = clean.copy()

    blocked: set[str] = set()
    missing = sorted(set(active_shorts.index) - set(feed_by_symbol.index))
    blocked.update(missing)

    aligned = feed_by_symbol.reindex(active_shorts.index)
    stale_symbols = _stale_feed_symbols(aligned, asof_date, feed_max_age_days)
    blocked.update(stale_symbols)
    feed_freshness_pass = not stale_symbols

    locate_check_mode: Literal["binary", "shares"] = "binary" if prices is None else "shares"
    locate_violations: list[str] = []
    if prices is None:
        zero_locates = aligned["locate_available_shares"].fillna(0.0).astype(float) <= 0.0
        locate_violations = sorted(aligned.index[zero_locates].dropna().astype(str).tolist())
        blocked.update(locate_violations)
    else:
        locate_violations = _apply_share_locate_caps(enforced, aligned, prices, aum_usd, gross)

    for symbol in sorted(blocked):
        if symbol in enforced.index:
            enforced.loc[symbol] = 0.0

    utilization = aligned["utilization_pct"].fillna(0.0).astype(float)
    utilization_warnings = sorted(aligned.index[utilization > 0.90].dropna().astype(str).tolist())

    post_block_short_abs = _short_abs(enforced)
    post_active_shorts = post_block_short_abs[post_block_short_abs > 0.0]
    htb_flags = aligned["htb_flag"].fillna(False).astype(bool)
    htb_symbols = sorted([symbol for symbol in active_shorts.index if bool(htb_flags.get(symbol, False))])
    htb_share = _htb_share(post_active_shorts, htb_symbols)
    htb_cap_pass = htb_share <= htb_notional_cap + 1e-12

    if not htb_cap_pass:
        adjusted = _enforce_htb_cap(enforced, htb_symbols, htb_notional_cap)
        if adjusted is not None:
            enforced = adjusted
            htb_share = _htb_share(_short_abs(enforced)[lambda s: s > 0.0], htb_symbols)
            htb_cap_pass = htb_share <= htb_notional_cap + 1e-12

    return BorrowCapResult(
        blocked_symbols=sorted(blocked),
        htb_symbols=htb_symbols,
        htb_notional_share=htb_share,
        htb_cap_pass=htb_cap_pass,
        locate_violations=sorted(locate_violations),
        utilization_warnings=utilization_warnings,
        enforced_weights=enforced,
        feed_freshness_pass=feed_freshness_pass,
        locate_check_mode=locate_check_mode,
    )


def validate_pb_borrow_feed_schema(borrow_feed: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a PB borrow feed without applying portfolio caps."""
    return _validate_borrow_feed_schema(borrow_feed)


def _validate_borrow_feed_schema(borrow_feed: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(borrow_feed, pd.DataFrame):
        raise BorrowFeedSchemaError("borrow_feed must be a pandas DataFrame.")
    missing = sorted(BORROW_REQUIRED_COLUMNS - set(borrow_feed.columns))
    if missing:
        raise BorrowFeedSchemaError(f"borrow_feed missing required columns: {missing}")
    feed = borrow_feed.copy()
    for column in ("locate_available_shares", "borrow_rate_bps", "utilization_pct"):
        try:
            feed[column] = pd.to_numeric(feed[column])
        except Exception as exc:  # pragma: no cover - pandas raises varied errors.
            raise BorrowFeedSchemaError(f"borrow_feed column {column} must be numeric.") from exc
        if feed[column].isna().any():
            raise BorrowFeedSchemaError(f"borrow_feed column {column} contains null or non-numeric values.")
    if feed["symbol"].isna().any():
        raise BorrowFeedSchemaError("borrow_feed column symbol contains null values.")
    try:
        feed["feed_timestamp_utc"] = pd.to_datetime(feed["feed_timestamp_utc"], utc=True)
    except Exception as exc:  # pragma: no cover
        raise BorrowFeedSchemaError("borrow_feed column feed_timestamp_utc must be datetime-like.") from exc
    if feed["feed_timestamp_utc"].isna().any():
        raise BorrowFeedSchemaError("borrow_feed column feed_timestamp_utc contains null values.")
    feed["htb_flag"] = feed["htb_flag"].map(_coerce_bool)
    if feed["htb_flag"].isna().any():
        raise BorrowFeedSchemaError("borrow_feed column htb_flag must be boolean-like.")
    return feed


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "t", "yes", "y", "1"}:
            return True
        if lowered in {"false", "f", "no", "n", "0"}:
            return False
    return None


def _short_abs(weights: pd.Series) -> pd.Series:
    return (-weights.where(weights < 0.0, 0.0)).astype(float)


def _short_metrics(weights: pd.Series) -> dict[str, float]:
    short_abs = _short_abs(weights)
    active = short_abs[short_abs > 0.0]
    short_total = float(active.sum())
    if short_total <= 0.0:
        return {"short_total": 0.0, "top10_share": 0.0, "max_single_share": 0.0}
    shares = active / short_total
    return {
        "short_total": short_total,
        "top10_share": float(shares.nlargest(10).sum()),
        "max_single_share": float(shares.max()),
    }


def _violating_short_symbols(weights: pd.Series, short_total: float, top10_cap: float, single_name_cap: float) -> list[str]:
    if short_total <= 0.0:
        return []
    short_abs = _short_abs(weights)
    shares = short_abs[short_abs > 0.0] / short_total
    violating = set(shares[shares > single_name_cap + 1e-12].index.astype(str))
    if float(shares.nlargest(10).sum()) > top10_cap + 1e-12:
        violating.update(shares.nlargest(10).index.astype(str))
    return sorted(violating)


def _enforce_single_short_cap(weights: pd.Series, short_total: float, cap: float) -> pd.Series | None:
    result = weights.copy()
    max_abs = cap * short_total
    for _ in range(len(result) + 1):
        short_abs = _short_abs(result)
        active = short_abs[short_abs > 0.0]
        excess = (active - max_abs).clip(lower=0.0)
        if float(excess.sum()) <= 1e-12:
            return result
        violators = excess[excess > 0.0].index
        overflow = float(excess.sum())
        result.loc[violators] = -max_abs
        recipients = active.drop(index=violators, errors="ignore")
        recipient_room = (max_abs - recipients).clip(lower=0.0)
        if float(recipient_room.sum()) <= 1e-12:
            return None
        allocation = overflow * recipient_room / float(recipient_room.sum())
        result.loc[allocation.index] = result.loc[allocation.index] - allocation
    return None


def _enforce_top10_short_cap(weights: pd.Series, short_total: float, cap: float) -> pd.Series | None:
    result = weights.copy()
    short_abs = _short_abs(result)
    active = short_abs[short_abs > 0.0].sort_values(ascending=False)
    if active.empty or len(active) <= 10:
        return None if float(active.sum()) > cap * short_total + 1e-12 else result
    top10 = active.head(10)
    rest = active.iloc[10:]
    top_target = cap * short_total
    top_sum = float(top10.sum())
    if top_sum <= top_target + 1e-12:
        return result
    if float(rest.sum()) <= 1e-12:
        return None
    scale = top_target / top_sum
    removed = top_sum - top_target
    result.loc[top10.index] = result.loc[top10.index] * scale
    redistribution = removed * rest / float(rest.sum())
    result.loc[rest.index] = result.loc[rest.index] - redistribution
    return result


def _stale_feed_symbols(aligned: pd.DataFrame, asof_date: pd.Timestamp, max_age_bdays: int) -> list[str]:
    asof = pd.Timestamp(asof_date).normalize()
    stale = []
    for symbol, row in aligned.iterrows():
        if row.isna().all():
            continue
        timestamp = row.get("feed_timestamp_utc")
        if pd.isna(timestamp):
            stale.append(str(symbol))
            continue
        feed_date = pd.Timestamp(timestamp).tz_convert(None).normalize()
        age = len(pd.bdate_range(feed_date, asof)) - 1 if feed_date <= asof else 0
        if age > max_age_bdays:
            stale.append(str(symbol))
    return sorted(stale)


def _apply_share_locate_caps(
    weights: pd.Series,
    aligned: pd.DataFrame,
    prices: pd.Series,
    aum_usd: float,
    gross: float,
) -> list[str]:
    price_series = prices.reindex(weights.index).astype(float)
    violations = []
    for symbol, weight in weights[weights < 0.0].items():
        locate = aligned["locate_available_shares"].get(symbol, 0.0)
        price = price_series.get(symbol, float("nan"))
        if pd.isna(price) or price <= 0.0 or pd.isna(locate) or float(locate) <= 0.0:
            violations.append(str(symbol))
            weights.loc[symbol] = 0.0
            continue
        short_shares = abs(float(weight)) * float(aum_usd) * float(gross) / float(price)
        if short_shares > float(locate) + 1e-12:
            max_weight = float(locate) * float(price) / (float(aum_usd) * float(gross))
            weights.loc[symbol] = -max_weight
            violations.append(str(symbol))
    return sorted(violations)


def _htb_share(active_shorts: pd.Series, htb_symbols: list[str]) -> float:
    total = float(active_shorts.sum())
    if total <= 0.0:
        return 0.0
    return float(active_shorts.reindex(htb_symbols).fillna(0.0).sum() / total)


def _enforce_htb_cap(weights: pd.Series, htb_symbols: list[str], cap: float) -> pd.Series | None:
    result = weights.copy()
    short_abs = _short_abs(result)
    active = short_abs[short_abs > 0.0]
    total = float(active.sum())
    htb_index = active.index.intersection(pd.Index(htb_symbols))
    non_htb = active.drop(index=htb_index, errors="ignore")
    htb_sum = float(active.reindex(htb_index).fillna(0.0).sum())
    target = cap * total
    if htb_sum <= target + 1e-12:
        return result
    if float(non_htb.sum()) <= 1e-12:
        return None
    scale = target / htb_sum
    removed = htb_sum - target
    result.loc[htb_index] = result.loc[htb_index] * scale
    redistribution = removed * non_htb / float(non_htb.sum())
    result.loc[redistribution.index] = result.loc[redistribution.index] - redistribution
    return result
