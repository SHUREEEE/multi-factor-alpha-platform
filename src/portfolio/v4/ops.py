"""V4 local operations helpers for launch-readiness controls."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IncidentRecord:
    incident_type: str
    severity: str
    status: str
    created_at_utc: str
    payload: dict[str, Any]


def write_incident_record(
    incident: dict[str, Any],
    incident_dir: Path,
    *,
    severity: str = "P0",
) -> Path:
    """Write a local incident record for audit/review handoff."""
    incident_dir = Path(incident_dir)
    incident_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record = IncidentRecord(
        incident_type=str(incident.get("incident_type", "V4_INCIDENT")),
        severity=severity,
        status="OPEN",
        created_at_utc=now,
        payload=dict(incident),
    )
    safe_type = record.incident_type.lower().replace(" ", "_")
    path = incident_dir / f"{now.replace(':', '').replace('-', '')}_{safe_type}.json"
    path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_kill_switch_runbook(runbook_path: Path) -> Path:
    """Write the local V4 kill-switch operator runbook."""
    runbook_path = Path(runbook_path)
    runbook_path.parent.mkdir(parents=True, exist_ok=True)
    runbook_path.write_text(
        "\n".join(
            [
                "# V4 Kill Switch Operator Runbook",
                "",
                "## Trigger Conditions",
                "- PIT launch gate failure.",
                "- Terminal drawdown kill switch.",
                "- Hard halt or unresolved single-day halt.",
                "- PB borrow feed unavailable for affected order names.",
                "",
                "## Operator Actions",
                "1. Stop V4 order generation for the affected as-of date.",
                "2. Preserve `results/v4_e1_replay/` and the current run manifest.",
                "3. Open a P0 incident record using `write_incident_record`.",
                "4. Notify the owner that manual review is required before restart.",
                "5. Restart only after the incident record is closed outside this scaffold.",
                "",
                "## Non-Actions",
                "- Do not regenerate V3 cache.",
                "- Do not relax PIT, borrow, drawdown, or acceptance thresholds.",
                "- Do not claim live launch readiness from Sharpe alone.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return runbook_path
