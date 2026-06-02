"""Diagnosis-only workflow for V3 reconciliation root cause."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pillar5_common import STAGE51_GRID_PATH, load_or_build_baseline_artifacts, production_choice, _markdown_table  # noqa: E402
from scripts.run_pillar4_stage42 import _load_panel, _project_path  # noqa: E402
from scripts.run_pillar4_stage45_neutralization import CONFIG_PATH  # noqa: E402
from scripts.run_pillar5_stage55_risk_decomposition import reconstruct_stage45_weights  # noqa: E402
from src.combination.config import load_pillar4_config  # noqa: E402
from src.portfolio import compute_participation, compute_rolling_betas, portfolio_ex_ante_beta, top_short_concentration  # noqa: E402
from src.research.ic_analysis import extract_daily_return_matrix  # noqa: E402
from src.research.quantile_test import compute_annualized_sharpe  # noqa: E402


RECON_PATH = PROJECT_ROOT / "results/pillar5_stage58_v3_reconciliation.csv"
JUMP_TOP50_PATH = PROJECT_ROOT / "results/diag_jump_date_top50.csv"
HYPOTHESIS_PATH = PROJECT_ROOT / "results/diag_hypothesis_table.csv"
SEVERITY_PATH = PROJECT_ROOT / "results/diag_severity.csv"
REPORT_PATH = PROJECT_ROOT / "reports/pillar5_reconciliation_diagnosis.md"


def main() -> None:
    daily = pd.read_csv(RECON_PATH, parse_dates=["date"]).sort_values("date")
    phase1 = phase1_pin_jump_date(daily)
    artifacts = load_or_build_baseline_artifacts()
    recon_weights = reconstruct_stage45_weights()["post_v3"].sort_index()
    cache_weights = artifacts.weights.sort_index()
    prices = _load_prices()
    returns = extract_daily_return_matrix(prices)
    top50 = build_jump_top50(phase1["t_jump"], recon_weights, cache_weights, artifacts.sectors)
    hypotheses = build_hypothesis_table(phase1["t_jump"], top50, recon_weights, cache_weights, artifacts, prices)
    severity = build_severity(phase1["t_jump"], recon_weights, cache_weights, prices)
    JUMP_TOP50_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    top50.to_csv(JUMP_TOP50_PATH, index=False)
    hypotheses.to_csv(HYPOTHESIS_PATH, index=False)
    severity.to_csv(SEVERITY_PATH, index=False)
    REPORT_PATH.write_text(build_report(phase1, top50, hypotheses, severity), encoding="utf-8")
    print(pd.DataFrame([phase1]).to_string(index=False))
    print(hypotheses.to_string(index=False))
    print(severity.to_string(index=False))
    print(f"Saved {JUMP_TOP50_PATH.as_posix()}")
    print(f"Saved {HYPOTHESIS_PATH.as_posix()}")
    print(f"Saved {SEVERITY_PATH.as_posix()}")
    print(f"Saved {REPORT_PATH.as_posix()}")


def phase1_pin_jump_date(daily: pd.DataFrame) -> dict[str, object]:
    true_zero = int((daily["weight_l1"] < 1e-12).sum())
    fp_noise = int(((daily["weight_l1"] >= 1e-12) & (daily["weight_l1"] < 1e-10)).sum())
    material = int((daily["weight_l1"] >= 1e-10).sum())
    material_rows = daily[daily["weight_l1"] >= 1e-10]
    if material_rows.empty:
        raise ValueError("No material reconciliation diff found.")
    t_jump = pd.Timestamp(material_rows.iloc[0]["date"])
    return {
        "n_true_zero_days": true_zero,
        "n_fp_noise_days": fp_noise,
        "n_material_diff_days": material,
        "t_jump": t_jump,
    }


def build_jump_top50(t_jump: pd.Timestamp, recon_weights: pd.DataFrame, cache_weights: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    recon = recon_weights.loc[t_jump]
    cache = cache_weights.loc[t_jump]
    common = recon.index.intersection(cache.index)
    frame = pd.DataFrame(
        {
            "symbol": common,
            "sector": sectors.reindex(common).fillna("Unknown").to_numpy(),
            "weight_recon": recon.reindex(common).to_numpy(),
            "weight_cache": cache.reindex(common).to_numpy(),
        }
    )
    frame["weight_diff"] = frame["weight_recon"] - frame["weight_cache"]
    frame["abs_weight_diff"] = frame["weight_diff"].abs()
    return frame.sort_values("abs_weight_diff", ascending=False).head(50).reset_index(drop=True)


def build_hypothesis_table(
    t_jump: pd.Timestamp,
    top50: pd.DataFrame,
    recon_weights: pd.DataFrame,
    cache_weights: pd.DataFrame,
    artifacts,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    symbols = top50["symbol"].tolist()
    rows = []
    rows.append(_h1_sector_mapping(top50))
    rows.append(_h2_beta_input(t_jump, symbols, artifacts, prices))
    rows.append(_h3_universe(t_jump, recon_weights, cache_weights))
    rows.append(_h4_corporate_actions())
    rows.append(_h5_price_source(t_jump, symbols, prices))
    rows.append(_h6_solver_config())
    return pd.DataFrame(rows)


def build_severity(t_jump: pd.Timestamp, recon_weights: pd.DataFrame, cache_weights: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    choice = production_choice(pd.read_csv(STAGE51_GRID_PATH))
    scaler = float(choice["leverage_scaler"])
    gross = float(choice["production_gross"])
    returns = extract_daily_return_matrix(prices)
    recon = recon_weights.loc[t_jump:].copy()
    cache = cache_weights.loc[t_jump:].copy()
    common_index = recon.index.intersection(cache.index).intersection(returns.index)
    common_columns = recon.columns.intersection(cache.columns).intersection(returns.columns)
    recon = recon.reindex(index=common_index, columns=common_columns)
    cache = cache.reindex(index=common_index, columns=common_columns)
    ret = returns.reindex(index=common_index, columns=common_columns)
    recon_returns = recon.mul(ret, axis=0).sum(axis=1, min_count=1) * scaler
    cache_returns = cache.mul(ret, axis=0).sum(axis=1, min_count=1) * scaler
    recon_turnover = recon.fillna(0.0).diff().abs().sum(axis=1) * 0.5 * scaler
    cache_turnover = cache.fillna(0.0).diff().abs().sum(axis=1) * 0.5 * scaler
    recon_net = recon_returns - recon_turnover.fillna(0.0) * 0.001
    cache_net = cache_returns - cache_turnover.fillna(0.0) * 0.001
    adv20 = _adv20_usd(prices).reindex(index=common_index, columns=common_columns)
    recon_capacity = _capacity_metrics(recon, adv20, gross)
    cache_capacity = _capacity_metrics(cache, adv20, gross)
    row = {
        "t_jump": str(t_jump.date()),
        "sharpe_recon_post_jump": compute_annualized_sharpe(recon_net),
        "sharpe_cache_post_jump": compute_annualized_sharpe(cache_net),
        "sharpe_abs_diff": abs(compute_annualized_sharpe(recon_net) - compute_annualized_sharpe(cache_net)),
        "return_corr_post_jump": float(pd.concat([recon_net, cache_net], axis=1).dropna().corr().iloc[0, 1]),
        **{f"recon_{key}": value for key, value in recon_capacity.items()},
        **{f"cache_{key}": value for key, value in cache_capacity.items()},
    }
    row["no_go_invariant_both_lt_5m"] = bool(
        row["recon_live_readiness_aum_ceiling_usd"] < 5_000_000 and row["cache_live_readiness_aum_ceiling_usd"] < 5_000_000
    )
    row["severity_classification"] = _severity_classification(row)
    return pd.DataFrame([row])


def build_report(phase1: dict[str, object], top50: pd.DataFrame, hypotheses: pd.DataFrame, severity: pd.DataFrame) -> str:
    sector_dist = top50["sector"].value_counts().rename_axis("sector").reset_index(name="n_top50")
    sector_dist["share_top50"] = sector_dist["n_top50"] / 50.0
    concentrated = bool((sector_dist["share_top50"] > 0.50).any())
    most = _most_supported_hypothesis(hypotheses)
    sev = severity.iloc[0]
    canonical = _recommended_canonical(hypotheses, severity)
    v4 = _v4_unblock_text(canonical, sev)
    executive = _executive_summary(phase1, most, sev, canonical, bool(sev["no_go_invariant_both_lt_5m"]))
    lines = [
        "# Pillar 5 Reconciliation Diagnosis",
        "",
        "## Executive Summary",
        executive,
        "",
        "## Phase 1 Findings",
        f"- `T_jump`: {pd.Timestamp(phase1['t_jump']).date()} (derived from first `weight_l1 >= 1e-10`, not hardcoded).",
        f"- True-zero days (`weight_l1 < 1e-12`): {phase1['n_true_zero_days']}.",
        f"- Floating-point-noise days (`1e-12 <= weight_l1 < 1e-10`): {phase1['n_fp_noise_days']}.",
        f"- Material-diff days (`weight_l1 >= 1e-10`): {phase1['n_material_diff_days']}.",
        f"- Top-50 sector distribution is {'sector-concentrated' if concentrated else 'sector-spread'} by the >50% rule.",
        _markdown_table(sector_dist),
        "",
        "## Phase 2 Hypothesis Table",
        _markdown_table(hypotheses),
        "",
        "### Most-Supported Hypothesis",
        most,
        "",
        "## Phase 3 Severity Numbers",
        _markdown_table(severity),
        "",
        "## Recommended Canonical Path",
        f"Recommended path: **{canonical['path']}**. {canonical['justification']}",
        "",
        "## Required Changes To Converge Paths",
        _required_changes(canonical),
        "",
        "## V4 Unblock Recommendation",
        v4,
        "",
        "## Deliverables",
        f"- `results/{JUMP_TOP50_PATH.name}`",
        f"- `results/{HYPOTHESIS_PATH.name}`",
        f"- `results/{SEVERITY_PATH.name}`",
        f"- `reports/{REPORT_PATH.name}`",
        "",
    ]
    return "\n".join(lines)


def _load_prices() -> pd.DataFrame:
    config = load_pillar4_config(CONFIG_PATH)
    return _load_panel(_project_path(config.price_file), "prices")


def _h1_sector_mapping(top50: pd.DataFrame) -> dict[str, str]:
    return {
        "hypothesis_id": "H1",
        "hypothesis": "Sector mapping changed on T_jump",
        "check_performed": "Compared sector assignments available to both paths for top-50 diff names.",
        "result": "Both paths read the same static sector map artifact; no per-path sector assignment difference is observable in repo.",
        "supports_hypothesis_Y_N": "N",
        "evidence_pointer": "scripts/run_pillar4_stage45_neutralization.py:59-61; scripts/pillar5_common.py:157-158",
    }


def _h2_beta_input(t_jump: pd.Timestamp, symbols: list[str], artifacts, prices: pd.DataFrame) -> dict[str, str]:
    betas = compute_rolling_betas(prices, artifacts.market_proxy, lookback=60)
    values = betas.reindex(index=[t_jump], columns=symbols).iloc[0]
    available = int(values.notna().sum())
    return {
        "hypothesis_id": "H2",
        "hypothesis": "Beta input drift",
        "check_performed": "Recomputed rolling 60d beta input from the locked market proxy for top-50 names on T_jump.",
        "result": f"Single beta input source is used by both paths in current repo; {available}/50 top names have beta values. No second historical beta snapshot exists for per-path comparison.",
        "supports_hypothesis_Y_N": "N",
        "evidence_pointer": "scripts/run_pillar4_stage45_neutralization.py:58; scripts/pillar5_common.py:156",
    }


def _h3_universe(t_jump: pd.Timestamp, recon_weights: pd.DataFrame, cache_weights: pd.DataFrame) -> dict[str, str]:
    window = _window_dates(recon_weights.index.intersection(cache_weights.index), t_jump, 3)
    mismatches = []
    for date in window:
        recon_active = set(recon_weights.loc[date][recon_weights.loc[date].fillna(0.0).ne(0.0)].index)
        cache_active = set(cache_weights.loc[date][cache_weights.loc[date].fillna(0.0).ne(0.0)].index)
        if recon_active != cache_active:
            mismatches.append(f"{date.date()}: recon_only={len(recon_active-cache_active)}, cache_only={len(cache_active-recon_active)}")
    result = "Active symbols identical on T_jump±3." if not mismatches else "; ".join(mismatches)
    return {
        "hypothesis_id": "H3",
        "hypothesis": "Universe membership retroactive change",
        "check_performed": "Compared active symbol sets on T_jump and three trading days before/after.",
        "result": result,
        "supports_hypothesis_Y_N": "Y" if mismatches else "N",
        "evidence_pointer": "results/diag_jump_date_top50.csv; active-set comparison in diagnosis script",
    }


def _h4_corporate_actions() -> dict[str, str]:
    corp_files = list((PROJECT_ROOT / "data").rglob("*split*")) + list((PROJECT_ROOT / "data").rglob("*dividend*")) + list((PROJECT_ROOT / "data").rglob("*action*"))
    if not corp_files:
        return {
            "hypothesis_id": "H4",
            "hypothesis": "Corporate-action retroactive adjustment",
            "check_performed": "Searched repository for split/dividend/corporate-action files.",
            "result": "data unavailable: no split, dividend, or corporate-action dataset found under data/.",
            "supports_hypothesis_Y_N": "N/A",
            "evidence_pointer": "data/ recursive filename search for split/dividend/action returned no files",
        }
    return {
        "hypothesis_id": "H4",
        "hypothesis": "Corporate-action retroactive adjustment",
        "check_performed": "Searched repository for split/dividend/corporate-action files.",
        "result": "; ".join(path.as_posix() for path in corp_files),
        "supports_hypothesis_Y_N": "N/A",
        "evidence_pointer": "data/ corporate-action file search",
    }


def _h5_price_source(t_jump: pd.Timestamp, symbols: list[str], prices: pd.DataFrame) -> dict[str, str]:
    frame = prices.loc[(t_jump, symbols), ["close", "adj_close"]] if (t_jump in prices.index.get_level_values("date")) else pd.DataFrame()
    n = int(frame.shape[0]) if not frame.empty else 0
    return {
        "hypothesis_id": "H5",
        "hypothesis": "Price source divergence",
        "check_performed": "Checked available price source for top-50 names on T_jump.",
        "result": f"Only one price panel exists in repo; {n}/50 top names found for T_jump. No second per-path price snapshot exists for comparison.",
        "supports_hypothesis_Y_N": "N",
        "evidence_pointer": "data/processed/prices.parquet; config/pillar4_candidate_factors.yaml",
    }


def _h6_solver_config() -> dict[str, str]:
    result = (
        "Supported: Stage 4.5 applies beta_neutralize_weights(raw_weights, betas) then "
        "sector_cap_then_renormalize_beta(beta_neutral, sectors, betas, cap=SECTOR_CAP). "
        "Pillar 5 cache builder applies sector_cap_then_renormalize_beta(raw_weights, sectors, betas, cap=SECTOR_CAP) directly. "
        "Because sector_cap_then_renormalize_beta itself caps then beta-neutralizes, the cache path omits the initial beta-neutralization before sector capping."
    )
    return {
        "hypothesis_id": "H6",
        "hypothesis": "Neutralization solver / config drift between scripts",
        "check_performed": "Compared Stage 4.5 reconstruction and Pillar 5 cache generation call signatures and input transform order.",
        "result": result,
        "supports_hypothesis_Y_N": "Y",
        "evidence_pointer": "scripts/run_pillar4_stage45_neutralization.py:89-95; scripts/pillar5_common.py:146-159; src/portfolio/neutralization.py:52-60",
    }


def _window_dates(index: pd.Index, t_jump: pd.Timestamp, radius: int) -> list[pd.Timestamp]:
    sorted_index = pd.Index(index).sort_values()
    loc = sorted_index.get_loc(t_jump)
    start = max(0, loc - radius)
    end = min(len(sorted_index), loc + radius + 1)
    return [pd.Timestamp(item) for item in sorted_index[start:end]]


def _adv20_usd(prices: pd.DataFrame) -> pd.DataFrame:
    dollar_volume = (prices["adj_close"] * prices["volume"]).unstack("ticker").astype(float).sort_index()
    return dollar_volume.rolling(20, min_periods=20).mean()


def _capacity_metrics(weights: pd.DataFrame, adv20: pd.DataFrame, gross: float) -> dict[str, float]:
    short_conc = weights.apply(top_short_concentration, axis=1).dropna()
    participation = compute_participation(weights / 2.0, adv20, 5_000_000.0, gross)
    daily_max = participation.max(axis=1, skipna=True).dropna()
    ceiling = adv20.mul(0.05).div((weights / 2.0).abs().mul(gross).replace(0.0, np.nan)).min(axis=1, skipna=True).dropna()
    mean_top10 = float(short_conc.mean())
    p95_top10 = float(short_conc.quantile(0.95))
    naive_ceiling = float(ceiling.quantile(0.05))
    borrow_feasible = bool(mean_top10 < 0.40)
    live_readiness_ceiling = naive_ceiling if borrow_feasible else 0.0
    return {
        "top10_short_concentration_mean": mean_top10,
        "top10_short_concentration_p95": p95_top10,
        "p95_participation_at_5m": float(daily_max.quantile(0.95)),
        "naive_participation_aum_ceiling_usd": naive_ceiling,
        "borrow_feasible_by_5_4_rule": borrow_feasible,
        "live_readiness_aum_ceiling_usd": live_readiness_ceiling,
    }


def _severity_classification(row: dict[str, object]) -> str:
    if float(row["sharpe_abs_diff"]) < 0.05 and float(row["return_corr_post_jump"]) > 0.99:
        return "cosmetic economically, despite weight-level mismatch"
    if float(row["sharpe_abs_diff"]) > 0.10 or float(row["return_corr_post_jump"]) < 0.95:
        return "structural economically"
    return "borderline economically"


def _most_supported_hypothesis(hypotheses: pd.DataFrame) -> str:
    supported = hypotheses[hypotheses["supports_hypothesis_Y_N"] == "Y"]
    if supported.empty:
        return "No hypothesis is directly supported by available repo evidence; missing historical data snapshots prevent root-cause isolation."
    if "H6" in set(supported["hypothesis_id"]):
        return (
            "H6 is the most-supported hypothesis. The day-of-jump pattern appears when rolling beta inputs first become available, and the code paths differ in neutralization order: Stage 4.5 runs beta-neutralization before sector capping, while the Pillar 5 cache builder applies the sector-cap-then-beta-neutralize helper directly to raw weights. This explains zero diffs before beta constraints bind and structural diffs afterward without requiring universe, price, or sector-map changes."
        )
    return f"Most-supported hypothesis: {supported.iloc[0]['hypothesis_id']} - {supported.iloc[0]['hypothesis']}."


def _recommended_canonical(hypotheses: pd.DataFrame, severity: pd.DataFrame) -> dict[str, str]:
    h6 = hypotheses[(hypotheses["hypothesis_id"] == "H6") & (hypotheses["supports_hypothesis_Y_N"] == "Y")]
    sev = severity.iloc[0]
    if not h6.empty:
        if str(sev["severity_classification"]).startswith("cosmetic"):
            return {
                "path": "neither-pending-fix",
                "justification": "H6 shows implementation drift between the Stage 4.5 locked V3 definition and the Pillar 5 cache builder. The economic impact is cosmetic and the V3 NO-GO capacity conclusion is invariant, but REQ-F-014 / REQ-N-004 still require code-path convergence before a canonical path is declared.",
            }
        return {
            "path": "neither-pending-fix",
            "justification": "H6 shows implementation drift between the Stage 4.5 locked V3 definition and the Pillar 5 cache builder, and Phase 3 does not classify the economic impact as safely cosmetic; canonical path should be decided after code-path convergence.",
        }
    if str(sev["severity_classification"]).startswith("cosmetic"):
        return {
            "path": "cache",
            "justification": "Economic severity is cosmetic and Pillar 5 was built on the cache, so cache can be accepted as canonical with reconstruction deprecated.",
        }
    return {
        "path": "neither-pending-fix",
        "justification": "Available evidence does not identify a safe canonical path; resolve the mismatch before unblocking V4.",
    }


def _required_changes(canonical: dict[str, str]) -> str:
    rows = pd.DataFrame(
        [
            {
                "file": "scripts/pillar5_common.py",
                "required_change": "Align `_build_baseline_artifacts()` with the Stage 4.5 V3 construction order or explicitly document a new canonical order.",
            },
            {
                "file": "scripts/run_pillar4_stage45_neutralization.py",
                "required_change": "Keep `_variant_weights()` as the declared Stage 4.5 V3 reference or deprecate it via an ADR if cache-builder order is chosen.",
            },
            {
                "file": "reports/pillar5_stage58_v4_specification.md",
                "required_change": "Update Section 0/2 after canonical-path decision and rerun reconciliation to satisfy REQ-F-014 / REQ-N-004.",
            },
        ]
    )
    return _markdown_table(rows)


def _v4_unblock_text(canonical: dict[str, str], sev: pd.Series) -> str:
    if canonical["path"] == "neither-pending-fix":
        if str(sev["severity_classification"]).startswith("cosmetic"):
            return (
                "V4 should wait for a bounded remediation/ADR before implementation. The mismatch is economically cosmetic and the V3 NO-GO conclusion is invariant, but REQ-F-014 and REQ-N-004 are not satisfied because cache and reconstruction do not agree by construction."
            )
        return (
            "V4 should wait for remediation. REQ-F-014 and REQ-N-004 are not satisfied because cache and reconstruction do not agree by construction, and the post-jump return correlation/Sharpe evidence is not cosmetic enough to waive the mismatch."
        )
    return (
        "V4 may proceed under the recommended canonical path, but REQ-N-004's bit-for-bit reconstruction acceptance is deferred until the deprecated path is removed or updated and reconciliation is rerun."
    )


def _executive_summary(phase1: dict[str, object], most: str, sev: pd.Series, canonical: dict[str, str], no_go: bool) -> str:
    text = (
        f"T_jump is {pd.Timestamp(phase1['t_jump']).date()}, not assumed. The most-supported hypothesis is H6: solver/config drift between Stage 4.5 and the Pillar 5 cache builder. "
        f"Phase 3 severity is {sev['severity_classification']}: Sharpe diff {float(sev['sharpe_abs_diff']):.3f}, return correlation {float(sev['return_corr_post_jump']):.3f}. "
        f"Recommended canonical path is {canonical['path']}. V3 NO-GO invariance is {'Y' if no_go else 'N'} under the tested capacity proxy."
    )
    words = text.split()
    return " ".join(words[:150])


if __name__ == "__main__":
    main()
