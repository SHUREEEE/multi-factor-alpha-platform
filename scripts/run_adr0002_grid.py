"""ADR-0002 one-pass optimizer reparameterization grid."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_v4_full_sample_replay import replay_v4_full_sample
from src.portfolio.v4.acceptance_gates import evaluate_v4_acceptance_gates


FAILED_E1_GATES = {
    "G-REQ-F-001-tail-turnover",
    "G-Preserve-HighVol-Sharpe",
    "G-Preserve-2022-Sharpe",
}
BASELINE_PARAMS = {
    "turnover_penalty": 4.0,
    "no_trade_band_bps": 100.0,
    "lambda_beta": 10.0,
    "sector_net_cap": 0.10,
}


@dataclass(frozen=True)
class ADR0002GridManifest:
    decision: str
    pre_registration_path: str
    pre_registration_sha256: str
    generated_at_utc: str
    points: list[dict[str, object]]
    limitation: str
    sanity_probe: dict[str, object] | None = None


def parse_pre_registered_grid(pre_registration_path: Path) -> list[dict[str, float]]:
    """Return the frozen 16-point ADR-0002 grid."""
    text = Path(pre_registration_path).read_text(encoding="utf-8")
    required = [
        "`turnover_penalty`: `4.0`, `8.0`, `20.0`, `40.0`",
        "`no_trade_band_bps`: `100.0`, `300.0`",
        "`lambda_beta`: `10.0`, `5.0`",
        "`sector_net_cap`: `0.10`",
        "Total grid size: `4 x 2 x 2 x 1 = 16` points",
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise ValueError(f"ADR-0002 pre-registration grid markers missing: {missing}")
    grid = []
    for turnover_penalty in [4.0, 8.0, 20.0, 40.0]:
        for no_trade_band_bps in [100.0, 300.0]:
            for lambda_beta in [10.0, 5.0]:
                grid.append(
                    {
                        "turnover_penalty": turnover_penalty,
                        "no_trade_band_bps": no_trade_band_bps,
                        "lambda_beta": lambda_beta,
                        "sector_net_cap": 0.10,
                    }
                )
    return grid


def run_adr0002_grid(
    pre_registration_path: Path,
    v3_cache_dir: Path,
    output_dir: Path,
    *,
    max_minutes_per_point: float,
) -> ADR0002GridManifest:
    """Run the frozen 16-point ADR-0002 grid and write decision artifacts."""
    pre_registration_path = Path(pre_registration_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pre_hash = _sha256_file(pre_registration_path)
    grid = parse_pre_registered_grid(pre_registration_path)
    sanity_probe = run_sanity_probe(grid, Path(v3_cache_dir), output_dir, max_minutes_per_point=max_minutes_per_point)
    if not sanity_probe["pass_fail"]:
        manifest = ADR0002GridManifest(
            decision="WIRING-PROBE-FAIL",
            pre_registration_path=str(pre_registration_path),
            pre_registration_sha256=pre_hash,
            generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            points=[],
            limitation="Sanity probe found no parameter-sensitive replay output; full grid was not run.",
            sanity_probe=sanity_probe,
        )
        (output_dir / "adr0002_manifest.json").write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
        pd.DataFrame().to_parquet(output_dir / "adr0002_summary.parquet", index=False)
        return manifest
    points = []
    for idx, params in enumerate(grid):
        point_dir = output_dir / f"point_{idx:02d}"
        if point_dir.exists():
            shutil.rmtree(point_dir)
        point_dir.mkdir(parents=True)
        config_path = point_dir / "config_used.yaml"
        _write_config(config_path, params)
        started = time.perf_counter()
        try:
            replay_dir = point_dir / "replay"
            replay_manifest = replay_v4_full_sample(Path(v3_cache_dir), config_path, replay_dir)
            elapsed_minutes = (time.perf_counter() - started) / 60.0
            if elapsed_minutes > max_minutes_per_point:
                raise TimeoutError(f"point exceeded {max_minutes_per_point} minutes")
            gates = evaluate_v4_acceptance_gates(Path(v3_cache_dir), replay_dir)
            gates_payload = [_gate_payload(gate) for gate in gates]
            (point_dir / "acceptance_gates.json").write_text(json.dumps(gates_payload, indent=2, sort_keys=True), encoding="utf-8")
            shutil.copyfile(replay_dir / "v4_replay_manifest.json", point_dir / "replay_manifest.json")
            classification = classify_point(gates_payload)
            point = {
                "point_id": f"point_{idx:02d}",
                "params": params,
                "classification": classification,
                "elapsed_minutes": elapsed_minutes,
                "weights_panel_hash": replay_manifest.weights_panel_hash,
                "config_hash": replay_manifest.config_hash,
                "gate_statuses": {gate["gate_id"]: gate["status"] for gate in gates_payload},
                "gate_observed": {gate["gate_id"]: gate["observed_value"] for gate in gates_payload},
                "output_dir": str(point_dir),
            }
        except Exception as exc:  # noqa: BLE001 - CRASH/TIMEOUT points are recorded as rejected.
            point = {
                "point_id": f"point_{idx:02d}",
                "params": params,
                "classification": "REJECTED",
                "elapsed_minutes": (time.perf_counter() - started) / 60.0,
                "error": type(exc).__name__,
                "message": str(exc),
                "gate_statuses": {},
                "gate_observed": {},
                "output_dir": str(point_dir),
            }
        points.append(point)
    decision = decide(points)
    manifest = ADR0002GridManifest(
        decision=decision,
        pre_registration_path=str(pre_registration_path),
        pre_registration_sha256=pre_hash,
        generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        points=points,
        limitation="ADR-0002 A-prime wiring repair makes the E1 replay scaffold consume frozen calibration parameters without changing D2-D7 algorithm modules.",
        sanity_probe=sanity_probe,
    )
    (output_dir / "adr0002_manifest.json").write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
    _summary(points).to_parquet(output_dir / "adr0002_summary.parquet", index=False)
    return manifest


def classify_point(gates_payload: list[dict[str, object]]) -> str:
    statuses = {str(gate["gate_id"]): str(gate["status"]) for gate in gates_payload}
    failed_gate_passes = sum(statuses.get(gate_id) == "PASS" for gate_id in FAILED_E1_GATES)
    other_regressed_fail = any(
        status == "FAIL" for gate_id, status in statuses.items() if gate_id not in FAILED_E1_GATES
    )
    if failed_gate_passes == 3 and not other_regressed_fail:
        return "GO-CANDIDATE"
    if failed_gate_passes >= 2 and not other_regressed_fail:
        return "PARTIAL-CANDIDATE"
    return "REJECTED"


def run_sanity_probe(
    grid: list[dict[str, float]],
    v3_cache_dir: Path,
    output_dir: Path,
    *,
    max_minutes_per_point: float,
) -> dict[str, object]:
    """Run point_00 vs point_15 before spending the full grid budget."""
    probe_dir = Path(output_dir) / "sanity_probe"
    if probe_dir.exists():
        shutil.rmtree(probe_dir)
    probe_dir.mkdir(parents=True)
    results = []
    for idx, params in [(0, grid[0]), (15, grid[-1])]:
        point_dir = probe_dir / f"point_{idx:02d}"
        point_dir.mkdir()
        config_path = point_dir / "config_used.yaml"
        _write_config(config_path, params)
        started = time.perf_counter()
        replay_manifest = replay_v4_full_sample(v3_cache_dir, config_path, point_dir / "replay")
        elapsed_minutes = (time.perf_counter() - started) / 60.0
        if elapsed_minutes > max_minutes_per_point:
            return {"pass_fail": False, "reason": "TIMEOUT", "points": results}
        gates = evaluate_v4_acceptance_gates(v3_cache_dir, point_dir / "replay")
        gates_payload = [_gate_payload(gate) for gate in gates]
        (point_dir / "acceptance_gates.json").write_text(json.dumps(gates_payload, indent=2, sort_keys=True), encoding="utf-8")
        results.append(
            {
                "point_id": f"point_{idx:02d}",
                "params": params,
                "weights_panel_hash": replay_manifest.weights_panel_hash,
                "gate_observed": {gate["gate_id"]: gate["observed_value"] for gate in gates_payload},
            }
        )
    first, second = results
    gate_differences = {
        gate_id: float(second["gate_observed"].get(gate_id, float("nan"))) - float(first["gate_observed"].get(gate_id, float("nan")))
        for gate_id in sorted(FAILED_E1_GATES)
    }
    hash_differs = first["weights_panel_hash"] != second["weights_panel_hash"]
    gate_differs = any(abs(value) > 1e-12 for value in gate_differences.values())
    return {
        "pass_fail": bool(hash_differs or gate_differs),
        "reason": "PARAMETER_SENSITIVE" if hash_differs or gate_differs else "DEAD_WIRING",
        "hash_differs": hash_differs,
        "gate_differences": gate_differences,
        "points": results,
    }


def decide(points: list[dict[str, object]]) -> str:
    return "GO-A" if any(point["classification"] == "GO-CANDIDATE" for point in points) else "ESCALATE-B"


def _gate_payload(gate: object) -> dict[str, object]:
    try:
        return asdict(gate)
    except TypeError:
        return dict(vars(gate))


def generate_adr0002_decision_report(manifest_path: Path, output_path: Path) -> Path:
    """Write the ADR-0002 decision report."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    points = manifest["points"]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "| point | turnover_penalty | no_trade_band_bps | lambda_beta | sector_net_cap | tail_turnover | highvol_sharpe | shock_2022 | classification |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for point in points:
        observed = point.get("gate_observed", {})
        params = point["params"]
        rows.append(
            f"| {point['point_id']} | {params['turnover_penalty']:.2f} | {params['no_trade_band_bps']:.2f} | "
            f"{params['lambda_beta']:.2f} | {params['sector_net_cap']:.2f} | "
            f"{float(observed.get('G-REQ-F-001-tail-turnover', float('nan'))):.6f} | "
            f"{float(observed.get('G-Preserve-HighVol-Sharpe', float('nan'))):.6f} | "
            f"{float(observed.get('G-Preserve-2022-Sharpe', float('nan'))):.6f} | {point['classification']} |"
        )
    best = _best_gap(points)
    probe = manifest.get("sanity_probe") or {}
    probe_lines = [
        "## Sanity Probe",
        "",
        f"Probe status: `{probe.get('reason', 'NOT_RECORDED')}`.",
        f"Probe pass: `{probe.get('pass_fail', False)}`.",
        f"Weight hash differs: `{probe.get('hash_differs', False)}`.",
        "",
    ]
    text = "\n".join(
        [
            "# ADR-0002 Decision Report",
            "",
            "A-prime note: the initial ADR-0002 grid exposed dead calibration wiring in the E1 replay scaffold. This report reflects the rerun after minimal replay-path wiring repair and a passing two-point sanity probe.",
            "",
            "Hypothesis reference: `docs/adr/ADR-0002-turnover-optimizer-reparam.md` Section A.",
            "",
            f"Evidence root: `{Path(manifest_path).parent}`.",
            "",
            "## Grid Results",
            "",
            *probe_lines,
            *rows,
            "",
            "## Decision",
            "",
            f"Decision: **{manifest['decision']}**.",
            "",
            "Applied ADR-0002 Section D mechanically: no GO-CANDIDATE points were present, so the decision is ESCALATE-B."
            if manifest["decision"] == "ESCALATE-B"
            else "Applied ADR-0002 Section D mechanically: at least one GO-CANDIDATE was present, so the decision is GO-A.",
            "",
            "## Best Observed Gaps",
            "",
            f"- Tail turnover: best `{best['tail_turnover']:.6f}` vs threshold `0.750000`, gap `{best['tail_turnover'] - 0.75:.6f}`.",
            f"- High-vol Sharpe: best `{best['highvol_sharpe']:.6f}` vs threshold `1.458000`, gap `{best['highvol_sharpe'] - 1.458:.6f}`.",
            f"- 2022 Sharpe: best `{best['shock_2022']:.6f}` vs threshold `1.026000`, gap `{best['shock_2022'] - 1.026:.6f}`.",
            "",
            "No threshold relaxation is proposed here. ADR-0002 is a grid evaluation record, not a design revision.",
        ]
    )
    output_path.write_text(text + "\n", encoding="utf-8")
    return output_path


def _summary(points: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    for point in points:
        observed = point.get("gate_observed", {})
        params = point["params"]
        rows.append(
            {
                "point_id": point["point_id"],
                "classification": point["classification"],
                **params,
                "tail_turnover": observed.get("G-REQ-F-001-tail-turnover"),
                "highvol_sharpe": observed.get("G-Preserve-HighVol-Sharpe"),
                "shock_2022": observed.get("G-Preserve-2022-Sharpe"),
                "elapsed_minutes": point.get("elapsed_minutes"),
            }
        )
    return pd.DataFrame(rows)


def _best_gap(points: list[dict[str, object]]) -> dict[str, float]:
    def best(gate_id: str) -> float:
        values = [
            float(point.get("gate_observed", {}).get(gate_id))
            for point in points
            if gate_id in point.get("gate_observed", {})
        ]
        return max(values) if values else float("nan")

    return {
        "tail_turnover": best("G-REQ-F-001-tail-turnover"),
        "highvol_sharpe": best("G-Preserve-HighVol-Sharpe"),
        "shock_2022": best("G-Preserve-2022-Sharpe"),
    }


def _write_config(path: Path, params: dict[str, float]) -> None:
    lines = [f"{key}: {value}\n" for key, value in params.items()]
    path.write_text("".join(lines), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ADR-0002 frozen 16-point grid.")
    parser.add_argument("--pre-registration", required=True, type=Path)
    parser.add_argument("--v3-cache-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-minutes-per-point", type=float, default=10.0)
    args = parser.parse_args(argv)
    manifest = run_adr0002_grid(
        args.pre_registration,
        args.v3_cache_dir,
        args.output,
        max_minutes_per_point=args.max_minutes_per_point,
    )
    generate_adr0002_decision_report(args.output / "adr0002_manifest.json", PROJECT_ROOT / "reports" / "adr0002_decision.md")
    print(json.dumps({"decision": manifest.decision, "points": len(manifest.points)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
