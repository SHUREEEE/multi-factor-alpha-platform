"""V4 data-integrity gates for ADV freshness and PIT validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


PASS = "PASS"
FAIL = "FAIL"


@dataclass(frozen=True)
class LaunchGateResult:
    """Result of applying the V4 PIT launch gate."""

    launch_allowed: bool
    incident_required: bool
    failed_checks: pd.DataFrame


class LaunchBlockedError(RuntimeError):
    """Raised when V4 launch/order generation is blocked by data integrity."""


class PitLaunchGateError(RuntimeError):
    """Raised when the D6 PIT launch gate blocks a build."""


@dataclass(frozen=True)
class Adv20FreshnessResult:
    """ADV20 freshness and observation-count validation result."""

    pass_fail: bool
    missing_symbols: list[str]
    stale_symbols: list[str]
    insufficient_obs_symbols: list[str]
    override_applied_symbols: list[str]
    blocked_symbols: list[str]
    reason: str


@dataclass(frozen=True)
class PitAuditResult:
    """Point-in-time pre-signal audit result."""

    overall_status: str
    per_dataset_status: dict[str, str]
    failures: list[dict[str, object]]
    missing_required_datasets: list[str]
    decision_timestamp_utc: object


def validate_adv20_freshness(
    adv20_usd: pd.DataFrame,
    asof_date: pd.Timestamp | str | None = None,
    *,
    required_symbols: Iterable[str] | None = None,
    max_staleness_trading_days: int | None = None,
    symbols: Iterable[str] | None = None,
    min_observations: int = 20,
    max_age_bdays: int = 1,
    event_day_override_symbols: Iterable[str] | None = None,
    event_day_overrides: Iterable[str] | None = None,
) -> pd.DataFrame | Adv20FreshnessResult:
    """Validate that ADV20 values are present, recent, and observation-backed.

    Missing or stale ADV20 blocks order generation for the affected symbol.
    An event-day override allows a symbol with fewer observations to pass, but
    it does not waive missing or stale values.
    """
    if required_symbols is not None:
        if asof_date is None:
            raise TypeError("asof_date is required for D6 ADV20 freshness validation.")
        return _validate_adv20_records(
            adv20_usd,
            asof_date=asof_date,
            required_symbols=required_symbols,
            max_staleness_trading_days=max_staleness_trading_days if max_staleness_trading_days is not None else max_age_bdays,
            min_observations=min_observations,
            event_day_override_symbols=event_day_override_symbols,
        )

    if not isinstance(adv20_usd, pd.DataFrame):
        raise TypeError("adv20_usd must be a pandas DataFrame.")
    if min_observations <= 0:
        raise ValueError("min_observations must be positive.")
    if max_age_bdays < 0:
        raise ValueError("max_age_bdays must be non-negative.")

    asof = pd.Timestamp(asof_date).normalize()
    data = adv20_usd.copy()
    data.index = pd.to_datetime(data.index).normalize()
    asof_metadata = data.attrs.get("asof_date")
    requested_symbols = list(symbols) if symbols is not None else list(data.columns)
    overrides = set(event_day_overrides or [])

    rows: list[dict[str, object]] = []
    historical = data.loc[data.index <= asof]
    for symbol in requested_symbols:
        if symbol not in data.columns:
            rows.append(_adv_row(symbol, asof, None, float("nan"), 0, None, FAIL, "missing_symbol"))
            continue

        series = historical[symbol].dropna()
        if series.empty:
            rows.append(_adv_row(symbol, asof, None, float("nan"), 0, None, FAIL, "missing_adv20"))
            continue

        latest_date = pd.Timestamp(series.index.max()).normalize()
        latest_value = float(series.loc[latest_date])
        observation_count = int(series.tail(min_observations).shape[0])
        age_bdays = _business_day_age(latest_date, asof)

        metadata_age = _metadata_age(asof_metadata, asof)
        if asof_metadata is None:
            status, reason = FAIL, "missing_asof_metadata"
        elif metadata_age is None or metadata_age > max_age_bdays:
            status, reason = FAIL, "stale_asof_metadata"
        elif latest_value <= 0.0:
            status, reason = FAIL, "non_positive_adv20"
        elif age_bdays is None or age_bdays > max_age_bdays:
            status, reason = FAIL, "stale_adv20"
        elif observation_count < min_observations and symbol not in overrides:
            status, reason = FAIL, "insufficient_observations"
        else:
            status, reason = PASS, "event_day_override" if observation_count < min_observations else "fresh"

        rows.append(_adv_row(symbol, asof, latest_date, latest_value, observation_count, age_bdays, status, reason))

    return pd.DataFrame(rows)


def run_pit_pre_signal_audit(
    datasets: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
    *,
    audit_records: pd.DataFrame | None = None,
    decision_timestamp_utc: pd.Timestamp | str,
    required_datasets: Iterable[str] | None = None,
    required_symbols: Iterable[str] | None = None,
    required_fields: dict[str, Iterable[str]] | None = None,
    artifact_path: str | Path | None = None,
) -> pd.DataFrame | PitAuditResult:
    """Run point-in-time audit checks before V4 signal generation.

    The input must contain the audit schema documented in `reports/v4_design.md`.
    Each row is evaluated independently and receives `audit_status` PASS/FAIL.
    """
    if audit_records is not None:
        return _run_pit_records_audit(
            audit_records,
            decision_timestamp_utc=decision_timestamp_utc,
            required_datasets=set(required_datasets or []),
        )

    if datasets is None:
        raise TypeError("datasets or audit_records must be provided.")
    if isinstance(datasets, dict):
        audit = _audit_dataset_mapping(datasets, decision_timestamp_utc, required_symbols, required_fields)
        if artifact_path is not None:
            _write_json_records(audit, artifact_path)
        return audit

    required = {
        "date",
        "dataset",
        "max_asof_timestamp_utc",
        "missing_symbol_count",
        "future_timestamp_count",
        "stale_field_count",
        "corporate_action_audit_pass",
    }
    if not isinstance(datasets, pd.DataFrame):
        raise TypeError("datasets must be a pandas DataFrame.")
    missing = sorted(required - set(datasets.columns))
    if missing:
        raise ValueError(f"datasets missing required columns: {missing}")

    decision_ts = pd.Timestamp(decision_timestamp_utc)
    audit = datasets.copy()
    audit["max_asof_timestamp_utc"] = pd.to_datetime(audit["max_asof_timestamp_utc"])

    reasons: list[str] = []
    statuses: list[str] = []
    for _, row in audit.iterrows():
        row_reasons: list[str] = []
        if pd.Timestamp(row["max_asof_timestamp_utc"]) > decision_ts:
            row_reasons.append("future_asof_timestamp")
        if int(row["missing_symbol_count"]) != 0:
            row_reasons.append("missing_symbols")
        if int(row["future_timestamp_count"]) != 0:
            row_reasons.append("future_timestamps")
        if int(row["stale_field_count"]) != 0:
            row_reasons.append("stale_fields")
        if not bool(row["corporate_action_audit_pass"]):
            row_reasons.append("corporate_action_audit_failed")

        statuses.append(PASS if not row_reasons else FAIL)
        reasons.append("pass" if not row_reasons else ";".join(row_reasons))

    audit["audit_status"] = statuses
    audit["failure_reason"] = reasons
    if artifact_path is not None:
        _write_json_records(audit, artifact_path)
    return audit


def enforce_pit_launch_gate(
    audit: pd.DataFrame | PitAuditResult,
    adv20_freshness: pd.DataFrame | None = None,
    builder_output_path: str | Path | None = None,
    *,
    incident_sink=None,
    incident_record_path: str | Path | None = None,
    raise_on_fail: bool = False,
) -> LaunchGateResult | None:
    """Block launch/order artifacts when any required PIT audit row fails."""
    if isinstance(audit, PitAuditResult):
        if audit.overall_status == PASS:
            return None
        incident = {
            "incident_type": "V4_PIT_LAUNCH_BLOCKED",
            "decision_timestamp_utc": str(audit.decision_timestamp_utc),
            "failures": audit.failures,
            "missing_required_datasets": audit.missing_required_datasets,
        }
        if incident_sink is not None:
            incident_sink(incident)
        reasons = sorted({str(failure["reason"]) for failure in audit.failures})
        raise PitLaunchGateError("V4 PIT launch gate failed: " + ",".join(reasons))

    if not isinstance(audit, pd.DataFrame):
        raise TypeError("audit must be a pandas DataFrame.")
    if "audit_status" not in audit.columns:
        raise ValueError("audit must include audit_status.")

    failed = audit[audit["audit_status"] != PASS].copy()
    if adv20_freshness is not None:
        failed_adv = adv20_freshness[adv20_freshness["status"] != PASS].copy()
        if not failed_adv.empty:
            failed_adv = failed_adv.rename(columns={"status": "audit_status"})
            failed_adv["dataset"] = "adv20"
            failed = pd.concat([failed, failed_adv], ignore_index=True, sort=False)
    result = LaunchGateResult(
        launch_allowed=failed.empty,
        incident_required=not failed.empty,
        failed_checks=failed.reset_index(drop=True),
    )
    if not result.launch_allowed:
        if incident_record_path is not None:
            _write_incident(result, incident_record_path, builder_output_path)
        if raise_on_fail:
            raise LaunchBlockedError("V4 launch blocked by PIT/ADV data-integrity gate.")
    return result


def _adv_row(
    symbol: str,
    asof: pd.Timestamp,
    latest_date: pd.Timestamp | None,
    value: float,
    observation_count: int,
    age_bdays: int | None,
    status: str,
    reason: str,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "asof_date": asof,
        "latest_date": latest_date,
        "adv20_usd": value,
        "observation_count": observation_count,
        "age_bdays": age_bdays,
        "status": status,
        "reason": reason,
        "order_block_Y_N": "Y" if status == FAIL else "N",
    }


def _validate_adv20_records(
    adv20: pd.DataFrame,
    *,
    asof_date,
    required_symbols: Iterable[str],
    max_staleness_trading_days: int,
    min_observations: int,
    event_day_override_symbols: Iterable[str] | None,
) -> Adv20FreshnessResult:
    required = {"symbol", "adv20_usd", "as_of_date", "observations_used", "feed_timestamp_utc"}
    if not isinstance(adv20, pd.DataFrame):
        raise TypeError("adv20 must be a pandas DataFrame.")
    missing_columns = sorted(required - set(adv20.columns))
    if missing_columns:
        raise ValueError(f"adv20 missing required columns: {missing_columns}")
    requested = pd.Index(required_symbols).astype(str)
    overrides = set(str(symbol) for symbol in (event_day_override_symbols or []))
    if adv20.empty:
        missing_symbols = sorted(requested.tolist())
        return Adv20FreshnessResult(False, missing_symbols, [], [], [], missing_symbols, "MISSING")

    asof = pd.Timestamp(asof_date).normalize()
    data = adv20.copy()
    data["symbol"] = data["symbol"].astype(str)
    data["as_of_date"] = pd.to_datetime(data["as_of_date"], errors="coerce").dt.normalize()
    data["observations_used"] = pd.to_numeric(data["observations_used"], errors="coerce")
    data = data.drop_duplicates("symbol", keep="last").set_index("symbol")

    missing_symbols = sorted(set(requested) - set(data.index))
    stale_symbols: list[str] = []
    insufficient: list[str] = []
    override_applied: list[str] = []
    for symbol in requested:
        if symbol in missing_symbols:
            continue
        row = data.loc[symbol]
        as_of = row["as_of_date"]
        if pd.isna(as_of) or (asof - pd.Timestamp(as_of).normalize()).days > max_staleness_trading_days:
            stale_symbols.append(str(symbol))
        obs = row["observations_used"]
        if pd.isna(obs) or int(obs) < min_observations:
            insufficient.append(str(symbol))
            if str(symbol) in overrides and str(symbol) not in stale_symbols:
                override_applied.append(str(symbol))

    blocked = sorted((set(missing_symbols) | set(stale_symbols) | set(insufficient)) - set(override_applied))
    reasons = []
    if missing_symbols:
        reasons.append("MISSING")
    if stale_symbols:
        reasons.append("STALE")
    if insufficient:
        reasons.append("INSUFFICIENT_OBS")
    return Adv20FreshnessResult(
        pass_fail=not blocked,
        missing_symbols=missing_symbols,
        stale_symbols=sorted(stale_symbols),
        insufficient_obs_symbols=sorted(insufficient),
        override_applied_symbols=sorted(override_applied),
        blocked_symbols=blocked,
        reason="PASS" if not blocked else ";".join(reasons),
    )


def _business_day_age(latest_date: pd.Timestamp, asof: pd.Timestamp) -> int | None:
    if latest_date > asof:
        return None
    return int(len(pd.bdate_range(latest_date, asof)) - 1)


def _metadata_age(asof_metadata: object, asof: pd.Timestamp) -> int | None:
    if asof_metadata is None:
        return None
    metadata_date = pd.Timestamp(asof_metadata).normalize()
    return _business_day_age(metadata_date, asof)


def _audit_dataset_mapping(
    datasets: dict[str, pd.DataFrame],
    decision_timestamp_utc: pd.Timestamp | str,
    required_symbols: Iterable[str] | None,
    required_fields: dict[str, Iterable[str]] | None,
) -> pd.DataFrame:
    decision_ts = pd.Timestamp(decision_timestamp_utc)
    symbols = set(required_symbols or [])
    rows = []
    for name, frame in datasets.items():
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"dataset {name} must be a pandas DataFrame.")
        fields = set((required_fields or {}).get(name, []))
        max_asof = _max_asof_timestamp(frame)
        missing_symbols = _missing_symbol_count(frame, symbols)
        future_timestamps = int(max_asof > decision_ts) if max_asof is not pd.NaT else 1
        stale_fields = len(fields - set(frame.columns))
        corporate_action_pass = bool(frame.attrs.get("corporate_action_audit_pass", True))
        row = {
            "date": decision_ts.normalize(),
            "dataset": name,
            "max_asof_timestamp_utc": max_asof,
            "missing_symbol_count": missing_symbols,
            "future_timestamp_count": future_timestamps,
            "stale_field_count": stale_fields,
            "corporate_action_audit_pass": corporate_action_pass,
        }
        rows.append(row)
    return run_pit_pre_signal_audit(pd.DataFrame(rows), decision_timestamp_utc=decision_timestamp_utc)


def _run_pit_records_audit(
    audit_records: pd.DataFrame,
    *,
    decision_timestamp_utc,
    required_datasets: set[str],
) -> PitAuditResult:
    required = {
        "date",
        "dataset",
        "max_asof_timestamp_utc",
        "missing_symbol_count",
        "future_timestamp_count",
        "stale_field_count",
        "corporate_action_audit_pass",
        "audit_status",
    }
    if not isinstance(audit_records, pd.DataFrame):
        raise TypeError("audit_records must be a pandas DataFrame.")
    missing = sorted(required - set(audit_records.columns))
    if missing:
        raise ValueError(f"audit_records missing required columns: {missing}")
    decision_ts = pd.Timestamp(decision_timestamp_utc)
    records = audit_records.copy()
    records["dataset"] = records["dataset"].astype(str)
    records["max_asof_timestamp_utc"] = pd.to_datetime(records["max_asof_timestamp_utc"], utc=True)
    missing_required = sorted(set(required_datasets) - set(records["dataset"]))
    failures: list[dict[str, object]] = []
    per_dataset: dict[str, str] = {}
    for dataset in missing_required:
        failures.append({"dataset": dataset, "reason": "MISSING_DATASET"})
        per_dataset[dataset] = FAIL

    for _, row in records.iterrows():
        dataset = str(row["dataset"])
        reasons = []
        if pd.Timestamp(row["max_asof_timestamp_utc"]) > decision_ts:
            reasons.append("FUTURE_ASOF")
        if int(row["missing_symbol_count"]) > 0:
            reasons.append("MISSING_SYMBOLS")
        if int(row["future_timestamp_count"]) > 0:
            reasons.append("FUTURE_TIMESTAMPS")
        if int(row["stale_field_count"]) > 0:
            reasons.append("STALE_FIELDS")
        if bool(row["corporate_action_audit_pass"]) is not True:
            reasons.append("CORPORATE_ACTION_AUDIT_FAIL")
        if str(row["audit_status"]) != PASS:
            reasons.append("AUDIT_STATUS_FAIL")
        per_dataset[dataset] = FAIL if reasons else PASS
        for reason in reasons:
            failures.append({"dataset": dataset, "reason": reason})

    return PitAuditResult(
        overall_status=PASS if not failures else FAIL,
        per_dataset_status=per_dataset,
        failures=failures,
        missing_required_datasets=missing_required,
        decision_timestamp_utc=decision_ts,
    )


def _max_asof_timestamp(frame: pd.DataFrame) -> pd.Timestamp:
    if "asof_timestamp_utc" in frame.columns:
        return pd.to_datetime(frame["asof_timestamp_utc"]).max()
    if "max_asof_timestamp_utc" in frame.columns:
        return pd.to_datetime(frame["max_asof_timestamp_utc"]).max()
    if "asof_timestamp_utc" in frame.attrs:
        return pd.Timestamp(frame.attrs["asof_timestamp_utc"])
    return pd.NaT


def _missing_symbol_count(frame: pd.DataFrame, required_symbols: set[str]) -> int:
    if not required_symbols:
        return 0
    symbol_column = "symbol" if "symbol" in frame.columns else "ticker" if "ticker" in frame.columns else None
    if symbol_column is None:
        return len(required_symbols)
    present = set(frame[symbol_column].dropna().astype(str))
    return len(required_symbols - present)


def _write_json_records(frame: pd.DataFrame, artifact_path: str | Path) -> None:
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frame.to_json(orient="records", date_format="iso", indent=2), encoding="utf-8")


def _write_incident(result: LaunchGateResult, incident_record_path: str | Path, builder_output_path: str | Path | None) -> None:
    path = Path(incident_record_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "incident_type": "V4_LAUNCH_BLOCKED",
        "builder_output_path": str(builder_output_path) if builder_output_path is not None else None,
        "failed_checks": json.loads(result.failed_checks.to_json(orient="records", date_format="iso")),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
