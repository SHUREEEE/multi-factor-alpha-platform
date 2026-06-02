"""Tests for V4 data-integrity gates.

Covers: REQ-F-012, REQ-F-013, REQ-F-015.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio.v4.data_integrity import (
    FAIL,
    LaunchBlockedError,
    PASS,
    PitLaunchGateError,
    enforce_pit_launch_gate,
    run_pit_pre_signal_audit,
    validate_adv20_freshness,
)
from src.portfolio.v4.builder import V4Config, V4InputBundle, build_v4_weights


def test_validate_adv20_freshness_blocks_missing_and_stale_symbols() -> None:
    dates = pd.bdate_range("2024-01-02", periods=21, name="date")
    adv20 = pd.DataFrame(
        {
            "AAA": [10_000_000.0] * 21,
            "BBB": [5_000_000.0] * 19 + [float("nan"), float("nan")],
        },
        index=dates,
    )
    adv20.attrs["asof_date"] = "2024-01-30"

    result = validate_adv20_freshness(adv20, "2024-01-30", symbols=["AAA", "BBB", "CCC"])

    by_symbol = result.set_index("symbol")
    assert by_symbol.loc["AAA", "status"] == PASS
    assert by_symbol.loc["AAA", "order_block_Y_N"] == "N"
    assert by_symbol.loc["BBB", "status"] == FAIL
    assert by_symbol.loc["BBB", "reason"] == "stale_adv20"
    assert by_symbol.loc["CCC", "reason"] == "missing_symbol"
    assert by_symbol.loc["CCC", "order_block_Y_N"] == "Y"


def test_validate_adv20_freshness_requires_twenty_observations_unless_overridden() -> None:
    dates = pd.bdate_range("2024-01-02", periods=10, name="date")
    adv20 = pd.DataFrame({"IPO": [2_000_000.0] * 10}, index=dates)
    adv20.attrs["asof_date"] = dates[-1]

    blocked = validate_adv20_freshness(adv20, dates[-1], symbols=["IPO"])
    allowed = validate_adv20_freshness(adv20, dates[-1], symbols=["IPO"], event_day_overrides=["IPO"])

    assert blocked.loc[0, "reason"] == "insufficient_observations"
    assert blocked.loc[0, "order_block_Y_N"] == "Y"
    assert allowed.loc[0, "status"] == PASS
    assert allowed.loc[0, "reason"] == "event_day_override"


def test_validate_adv20_freshness_blocks_missing_asof_metadata() -> None:
    dates = pd.bdate_range("2024-01-02", periods=21, name="date")
    adv20 = pd.DataFrame({"AAA": [10_000_000.0] * 21}, index=dates)

    result = validate_adv20_freshness(adv20, dates[-1], symbols=["AAA"])

    assert result.loc[0, "status"] == FAIL
    assert result.loc[0, "reason"] == "missing_asof_metadata"


def test_run_pit_pre_signal_audit_blocks_future_adjusted_or_missing_data() -> None:
    datasets = pd.DataFrame(
        [
            {
                "date": "2024-02-01",
                "dataset": "prices",
                "max_asof_timestamp_utc": "2024-02-01 20:00:00+00:00",
                "missing_symbol_count": 0,
                "future_timestamp_count": 0,
                "stale_field_count": 0,
                "corporate_action_audit_pass": True,
            },
            {
                "date": "2024-02-01",
                "dataset": "corporate_actions",
                "max_asof_timestamp_utc": "2024-02-02 01:00:00+00:00",
                "missing_symbol_count": 1,
                "future_timestamp_count": 1,
                "stale_field_count": 0,
                "corporate_action_audit_pass": False,
            },
        ]
    )

    audit = run_pit_pre_signal_audit(datasets, decision_timestamp_utc="2024-02-01 21:00:00+00:00")

    assert audit.loc[0, "audit_status"] == PASS
    assert audit.loc[1, "audit_status"] == FAIL
    assert "future_asof_timestamp" in audit.loc[1, "failure_reason"]
    assert "missing_symbols" in audit.loc[1, "failure_reason"]
    assert "corporate_action_audit_failed" in audit.loc[1, "failure_reason"]


def test_run_pit_pre_signal_audit_accepts_dataset_mapping_and_writes_artifact(tmp_path) -> None:
    prices = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "close": [10.0],
            "asof_timestamp_utc": ["2024-02-01 20:00:00+00:00"],
        }
    )
    artifact = tmp_path / "pit_audit.json"

    audit = run_pit_pre_signal_audit(
        {"prices": prices},
        decision_timestamp_utc="2024-02-01 21:00:00+00:00",
        required_symbols=["AAA"],
        required_fields={"prices": ["close"]},
        artifact_path=artifact,
    )

    assert audit.loc[0, "audit_status"] == PASS
    assert artifact.exists()


def test_enforce_pit_launch_gate_blocks_failed_audit_rows() -> None:
    audit = pd.DataFrame(
        {
            "dataset": ["prices", "adv20"],
            "audit_status": [PASS, FAIL],
            "failure_reason": ["pass", "stale_fields"],
        }
    )

    gate = enforce_pit_launch_gate(audit)

    assert not gate.launch_allowed
    assert gate.incident_required
    assert gate.failed_checks["dataset"].tolist() == ["adv20"]


def test_enforce_pit_launch_gate_raises_and_writes_incident(tmp_path) -> None:
    audit = pd.DataFrame({"dataset": ["prices"], "audit_status": [FAIL], "failure_reason": ["future_timestamps"]})
    incident = tmp_path / "incident_record.json"

    with pytest.raises(LaunchBlockedError):
        enforce_pit_launch_gate(audit, incident_record_path=incident, raise_on_fail=True)

    assert incident.exists()
    assert "V4_LAUNCH_BLOCKED" in incident.read_text(encoding="utf-8")


def test_enforce_pit_launch_gate_allows_clean_audit() -> None:
    audit = pd.DataFrame({"dataset": ["prices"], "audit_status": [PASS], "failure_reason": ["pass"]})

    gate = enforce_pit_launch_gate(audit)

    assert gate.launch_allowed
    assert not gate.incident_required
    assert gate.failed_checks.empty


def test_d6_adv20_records_all_fresh_pass() -> None:
    result = validate_adv20_freshness(
        _adv20_records(["AAA", "BBB"]),
        asof_date="2024-01-03",
        required_symbols=pd.Index(["AAA", "BBB"]),
    )

    assert result.pass_fail
    assert result.blocked_symbols == []


def test_d6_adv20_records_stale_symbol_blocks() -> None:
    records = _adv20_records(["AAA"])
    records["as_of_date"] = ["2023-12-31"]

    result = validate_adv20_freshness(records, asof_date="2024-01-03", required_symbols=pd.Index(["AAA"]))

    assert result.stale_symbols == ["AAA"]
    assert result.blocked_symbols == ["AAA"]


def test_d6_adv20_insufficient_observations_blocks_unless_overridden() -> None:
    records = _adv20_records(["IPO"], observations_used=15)

    blocked = validate_adv20_freshness(records, asof_date="2024-01-03", required_symbols=pd.Index(["IPO"]))
    allowed = validate_adv20_freshness(
        records,
        asof_date="2024-01-03",
        required_symbols=pd.Index(["IPO"]),
        event_day_override_symbols={"IPO"},
    )

    assert blocked.insufficient_obs_symbols == ["IPO"]
    assert blocked.blocked_symbols == ["IPO"]
    assert allowed.override_applied_symbols == ["IPO"]
    assert allowed.blocked_symbols == []


def test_d6_adv20_override_does_not_save_stale_symbol() -> None:
    records = _adv20_records(["IPO"], observations_used=15)
    records["as_of_date"] = ["2023-12-31"]

    result = validate_adv20_freshness(
        records,
        asof_date="2024-01-03",
        required_symbols=pd.Index(["IPO"]),
        event_day_override_symbols={"IPO"},
    )

    assert result.stale_symbols == ["IPO"]
    assert result.blocked_symbols == ["IPO"]


def test_d6_adv20_missing_symbols_and_empty_feed() -> None:
    missing = validate_adv20_freshness(_adv20_records(["AAA"]), asof_date="2024-01-03", required_symbols=pd.Index(["AAA", "BBB"]))
    empty = validate_adv20_freshness(_adv20_records([]), asof_date="2024-01-03", required_symbols=pd.Index(["AAA"]))

    assert missing.missing_symbols == ["BBB"]
    assert "BBB" in missing.blocked_symbols
    assert empty.missing_symbols == ["AAA"]


def test_d6_pit_audit_pass_and_launch_gate_silent() -> None:
    audit = run_pit_pre_signal_audit(
        audit_records=_pit_records(["prices", "borrow"]),
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        required_datasets={"prices", "borrow"},
    )

    assert audit.overall_status == PASS
    assert enforce_pit_launch_gate(audit) is None


def test_d6_pit_audit_future_asof_fails() -> None:
    records = _pit_records(["prices"])
    records.loc[0, "max_asof_timestamp_utc"] = "2024-01-04T21:00:00Z"

    audit = run_pit_pre_signal_audit(
        audit_records=records,
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        required_datasets={"prices"},
    )

    assert audit.overall_status == FAIL
    assert {"dataset": "prices", "reason": "FUTURE_ASOF"} in audit.failures


def test_d6_pit_audit_missing_symbols_and_corporate_action_fail() -> None:
    records = _pit_records(["prices"])
    records.loc[0, "missing_symbol_count"] = 3
    records.loc[0, "corporate_action_audit_pass"] = False

    audit = run_pit_pre_signal_audit(
        audit_records=records,
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        required_datasets={"prices"},
    )

    assert {"dataset": "prices", "reason": "MISSING_SYMBOLS"} in audit.failures
    assert {"dataset": "prices", "reason": "CORPORATE_ACTION_AUDIT_FAIL"} in audit.failures


def test_d6_pit_audit_missing_required_dataset_fails() -> None:
    audit = run_pit_pre_signal_audit(
        audit_records=_pit_records(["prices"]),
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        required_datasets={"prices", "adv20"},
    )

    assert audit.missing_required_datasets == ["adv20"]
    assert audit.overall_status == FAIL


def test_d6_pit_launch_gate_raises_and_calls_incident_sink() -> None:
    audit = run_pit_pre_signal_audit(
        audit_records=_pit_records(["prices"], audit_status="FAIL"),
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        required_datasets={"prices"},
    )
    incidents = []

    with pytest.raises(PitLaunchGateError):
        enforce_pit_launch_gate(audit, incident_sink=incidents.append)

    assert len(incidents) == 1
    assert incidents[0]["incident_type"] == "V4_PIT_LAUNCH_BLOCKED"


def test_d6_pit_audit_partial_dataset_failure() -> None:
    records = _pit_records(["prices", "borrow"])
    records.loc[records["dataset"] == "borrow", "stale_field_count"] = 1

    audit = run_pit_pre_signal_audit(
        audit_records=records,
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        required_datasets={"prices", "borrow"},
    )

    assert audit.overall_status == FAIL
    assert audit.per_dataset_status["prices"] == PASS
    assert audit.per_dataset_status["borrow"] == FAIL


def test_builder_d6_pit_and_adv_pass_manifest_fields() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw, sectors = _builder_raw(dates)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        pit_audit_records=_pit_records(["prices", "borrow", "adv20"]),
        decision_timestamp_utc="2024-01-03T21:00:00Z",
        adv20_records=_adv20_records(list(raw.columns)),
        required_symbols_for_adv=raw.columns,
    )

    result = build_v4_weights(inputs, _builder_config())

    assert result.manifest["pit_audit_overall_status"] == PASS
    assert result.manifest["adv20_blocked_count"] == 0


def test_builder_d6_pit_fail_enforce_true_raises() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw, sectors = _builder_raw(dates)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        pit_audit_records=_pit_records(["prices"], audit_status=FAIL),
        decision_timestamp_utc="2024-01-03T21:00:00Z",
    )

    with pytest.raises(PitLaunchGateError):
        build_v4_weights(inputs, _builder_config())


def test_builder_d6_pit_fail_enforce_false_returns_fail_status() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw, sectors = _builder_raw(dates)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        pit_audit_records=_pit_records(["prices"], audit_status=FAIL),
        decision_timestamp_utc="2024-01-03T21:00:00Z",
    )
    config = _builder_config()
    config = V4Config(**{**config.__dict__, "enforce_pit_launch_gate": False})

    result = build_v4_weights(inputs, config)

    assert result.manifest["validation_state"] == "PIT_AUDIT_FAIL"
    assert "PIT_AUDIT_FAIL" in result.manifest["validation_substatuses"]


def test_builder_d6_adv20_block_zeroes_affected_symbol() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw, sectors = _builder_raw(dates)
    adv20 = _adv20_records(list(raw.columns))
    adv20.loc[adv20["symbol"] == "CCC", "as_of_date"] = "2023-12-31"
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
        adv20_records=adv20,
        required_symbols_for_adv=raw.columns,
    )

    result = build_v4_weights(inputs, _builder_config())

    assert result.manifest["validation_state"] == "ADV20_BLOCK"
    assert result.manifest["adv20_blocked_count"] == 1
    assert result.weights.loc[dates[0], "CCC"] == pytest.approx(0.0)


def test_builder_d6_inputs_absent_defaults_manifest() -> None:
    dates = pd.bdate_range("2024-01-03", periods=1, name="date")
    raw, sectors = _builder_raw(dates)
    inputs = V4InputBundle(
        raw_weights=raw,
        prices=pd.DataFrame(index=dates),
        sectors=sectors,
        betas=pd.DataFrame(1.0, index=dates, columns=raw.columns),
    )

    result = build_v4_weights(inputs, _builder_config())

    assert result.manifest["pit_audit_overall_status"] is None
    assert result.manifest["adv20_blocked_count"] == 0
    assert result.manifest["slippage_total_modeled_bps"] is None


def _adv20_records(symbols: list[str], *, observations_used: int = 20) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": symbols,
            "adv20_usd": [1_000_000.0] * len(symbols),
            "as_of_date": ["2024-01-03"] * len(symbols),
            "observations_used": [observations_used] * len(symbols),
            "feed_timestamp_utc": ["2024-01-03T20:00:00Z"] * len(symbols),
        }
    )


def _pit_records(datasets: list[str], *, audit_status: str = PASS) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-03"] * len(datasets),
            "dataset": datasets,
            "max_asof_timestamp_utc": ["2024-01-03T20:00:00Z"] * len(datasets),
            "missing_symbol_count": [0] * len(datasets),
            "future_timestamp_count": [0] * len(datasets),
            "stale_field_count": [0] * len(datasets),
            "corporate_action_audit_pass": [True] * len(datasets),
            "audit_status": [audit_status] * len(datasets),
        }
    )


def _builder_raw(dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.Series]:
    raw = pd.DataFrame({"AAA": 0.5, "BBB": 0.5, "CCC": -0.5, "DDD": -0.5}, index=dates)
    sectors = pd.Series({"AAA": "Tech", "BBB": "Health", "CCC": "Tech", "DDD": "Health"})
    return raw, sectors


def _builder_config() -> V4Config:
    return V4Config(
        sector_net_cap=1.0,
        gross_target=2.0,
        turnover_penalty=0.0,
        no_trade_band_bps=0.0,
        short_top10_cap=1.0,
        single_short_cap=0.60,
    )
