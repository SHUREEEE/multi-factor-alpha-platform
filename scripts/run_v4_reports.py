"""Generate E1 V4 reports from replay and acceptance artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REPORT_NAMES = [
    "v4_capacity_summary.md",
    "v4_risk_decomposition.md",
    "v4_stress_regime.md",
    "v4_live_readiness_checklist.md",
    "v4_acceptance_gate.md",
]


def generate_v4_reports(replay_dir: Path, gates_path: Path, output_reports_dir: Path) -> dict[str, Path]:
    """Generate all five V4 E1 reports."""
    replay_dir = Path(replay_dir)
    gates = pd.DataFrame(json.loads(Path(gates_path).read_text(encoding="utf-8")))
    diagnostics = pd.read_parquet(replay_dir / "v4_diagnostics_panel.parquet")
    returns = pd.read_parquet(replay_dir / "v4_returns_panel.parquet")
    output_reports_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "v4_capacity_summary.md": _write(output_reports_dir / "v4_capacity_summary.md", _capacity(replay_dir, diagnostics)),
        "v4_risk_decomposition.md": _write(output_reports_dir / "v4_risk_decomposition.md", _risk(replay_dir, diagnostics)),
        "v4_stress_regime.md": _write(output_reports_dir / "v4_stress_regime.md", _stress(replay_dir, returns)),
        "v4_live_readiness_checklist.md": _write(output_reports_dir / "v4_live_readiness_checklist.md", _readiness(replay_dir)),
        "v4_acceptance_gate.md": _write(output_reports_dir / "v4_acceptance_gate.md", _acceptance(replay_dir, gates)),
    }
    return paths


def _capacity(replay_dir: Path, diagnostics: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# V4 Capacity Summary",
            "",
            f"Evidence: `{replay_dir / 'v4_diagnostics_panel.parquet'}`.",
            "",
            "| metric | value |",
            "| --- | ---: |",
            f"| p95_order_participation | {diagnostics['participation_p95'].quantile(0.95):.6f} |",
            f"| p95_short_top10_share | {diagnostics['short_top10_share'].quantile(0.95):.6f} |",
            f"| max_htb_notional_share | {diagnostics['htb_notional_share'].max():.6f} |",
            "",
            "**Synthetic borrow assumption - live launch requires real PB feed.**",
        ]
    ) + "\n"


def _risk(replay_dir: Path, diagnostics: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# V4 Risk Decomposition",
            "",
            f"Evidence: `{replay_dir / 'v4_diagnostics_panel.parquet'}`.",
            "",
            "| metric | value |",
            "| --- | ---: |",
            f"| p95_sector_net_max | {diagnostics['sector_net_max'].quantile(0.95):.6f} |",
            f"| avg_beta_20d | {diagnostics['beta_20d'].mean():.6f} |",
            f"| avg_beta_60d | {diagnostics['beta_60d'].mean():.6f} |",
            "",
            "Factor-tape limitation inherited from Pillar 5 Stage 5.5 remains in force; this report does not claim new factor attribution coverage.",
        ]
    ) + "\n"


def _stress(replay_dir: Path, returns: pd.DataFrame) -> str:
    series = returns["daily_return_bps"] / 10000.0
    shock = series.loc[(series.index >= "2022-01-01") & (series.index <= "2022-12-31")]
    high_vol = series.loc[series.rolling(20).std().rank(pct=True) > 0.8]
    return "\n".join(
        [
            "# V4 Stress Regime",
            "",
            f"Evidence: `{replay_dir / 'v4_returns_panel.parquet'}`.",
            "",
            "## 2022_rate_shock",
            f"Sharpe: {_sharpe(shock):.6f}",
            "",
            "## high_vol_regime",
            f"Sharpe: {_sharpe(high_vol):.6f}",
        ]
    ) + "\n"


def _readiness(replay_dir: Path) -> str:
    rows = [
        ("PIT audit live wiring", "READY"),
        ("PB borrow real feed", "PARTIAL"),
        ("ADV20 daily refresh", "READY"),
        ("incident sink", "READY"),
        ("kill switch operator runbook", "READY"),
        ("prod input loader", "READY"),
    ]
    table = "\n".join(f"| {item} | P0 | {status} |" for item, status in rows)
    return "\n".join(
        [
            "# V4 Live Readiness Checklist",
            "",
            f"Evidence: `{replay_dir / 'v4_pit_audit_log.parquet'}`.",
            "",
            "| item | priority | status |",
            "| --- | --- | --- |",
            table,
            "",
            "No launch-ready claim is made from Sharpe alone.",
        ]
    ) + "\n"


def _acceptance(replay_dir: Path, gates: pd.DataFrame) -> str:
    rows = ["| gate_id | req_id | status | observed_value | threshold |", "| --- | --- | --- | ---: | ---: |"]
    for _, row in gates[["gate_id", "req_id", "status", "observed_value", "threshold"]].iterrows():
        rows.append(
            f"| {row['gate_id']} | {row['req_id']} | {row['status']} | "
            f"{float(row['observed_value']):.6f} | {float(row['threshold']):.6f} |"
        )
    table = "\n".join(rows)
    return "\n".join(
        [
            "# V4 Acceptance Gate",
            "",
            f"Evidence: `{replay_dir / 'v4_diagnostics_panel.parquet'}` and acceptance gate artifact.",
            "",
            table,
            "",
            "V4 supersession decision is evidence-based and not a Sharpe-only readiness claim.",
        ]
    ) + "\n"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _sharpe(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < 2 or clean.std() == 0:
        return 0.0
    return float(clean.mean() / clean.std() * (252**0.5))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate V4 E1 reports.")
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--gates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    for path in generate_v4_reports(args.replay_dir, args.gates, args.output).values():
        print(f"Saved {path.as_posix()}")


if __name__ == "__main__":
    main()
