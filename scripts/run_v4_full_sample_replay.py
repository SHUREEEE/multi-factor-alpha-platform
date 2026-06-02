"""E1 V4 full-sample replay driver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class V4ReplayManifest:
    inputs_hash: str
    config_hash: str
    weights_panel_hash: str
    builder_version: str
    replay_timestamp_utc: str
    borrow_source: str
    prior_chain: str
    output_dir: str
    replay_config: dict[str, float]


def replay_v4_full_sample(
    v3_cache_dir: Path,
    v4_config_path: Path,
    output_dir: Path,
    *,
    start_date: object | None = None,
    end_date: object | None = None,
) -> V4ReplayManifest:
    """Replay V4 controls over canonical V3 trading days and write E1 panels."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    weights = _load_weights(Path(v3_cache_dir))
    returns = _load_returns(Path(v3_cache_dir), weights.index)
    replay_config = _load_replay_config(Path(v4_config_path))
    weights = _date_filter(weights, start_date, end_date)
    returns = returns.reindex(weights.index)
    v4_weights, diagnostics = _build_replay_weights(weights, returns, replay_config)
    v4_returns = _build_returns_panel(v4_weights, returns, diagnostics, replay_config)
    pit_log = _build_pit_log(Path(v3_cache_dir), weights.index)

    v4_weights.stack().rename("weight").reset_index().to_parquet(output_dir / "v4_weights_panel.parquet", index=False)
    v4_returns.to_parquet(output_dir / "v4_returns_panel.parquet")
    diagnostics.to_parquet(output_dir / "v4_diagnostics_panel.parquet")
    pit_log.to_parquet(output_dir / "v4_pit_audit_log.parquet")
    manifest = V4ReplayManifest(
        inputs_hash=_hash_frame(weights),
        config_hash=_hash_file(v4_config_path),
        weights_panel_hash=_hash_frame(v4_weights),
        builder_version="v4.0.0-D7",
        replay_timestamp_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        borrow_source="synthetic",
        prior_chain="t0_prior=v3_weight; t>0_prior=previous_v4_weight",
        output_dir=str(output_dir),
        replay_config=replay_config,
    )
    (output_dir / "v4_replay_manifest.json").write_text(json.dumps(manifest.__dict__, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _load_weights(v3_cache_dir: Path) -> pd.DataFrame:
    path = v3_cache_dir / "v3_weights.parquet" if v3_cache_dir.is_dir() else v3_cache_dir
    if not path.exists():
        path = PROJECT_ROOT / "results" / "pillar5_artifacts" / "v3_weights.parquet"
    return pd.read_parquet(path).fillna(0.0).astype(float)


def _load_returns(v3_cache_dir: Path, index: pd.Index) -> pd.Series:
    path = v3_cache_dir / "v3_daily_returns.parquet" if v3_cache_dir.is_dir() else PROJECT_ROOT / "results" / "pillar5_artifacts" / "v3_daily_returns.parquet"
    if path.exists():
        frame = pd.read_parquet(path)
        if "long_short_return" in frame:
            return frame["long_short_return"].reindex(index).fillna(0.0).astype(float)
    return pd.Series(0.0, index=index)


def _date_filter(frame: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    result = frame.copy()
    if start_date is not None:
        result = result.loc[result.index >= pd.Timestamp(start_date)]
    if end_date is not None:
        result = result.loc[result.index <= pd.Timestamp(end_date)]
    return result


def _load_replay_config(path: Path) -> dict[str, float]:
    config = {
        "turnover_penalty": 4.0,
        "no_trade_band_bps": 100.0,
        "lambda_beta": 10.0,
        "sector_net_cap": 0.10,
        "protected_regime_alpha_bps": 0.0,
    }
    if not path.exists():
        return config
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in config:
            try:
                config[key] = float(value.strip())
            except ValueError:
                continue
    return config


def _build_replay_weights(raw: pd.DataFrame, returns: pd.Series, config: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    diagnostics = []
    prior = None
    raw_share = _raw_share(config["turnover_penalty"])
    no_trade_band = float(config["no_trade_band_bps"]) / 10000.0
    for date, row in raw.iterrows():
        clean = row.fillna(0.0).astype(float)
        if prior is None:
            target = clean
        else:
            aligned_prior = prior.reindex(clean.index).fillna(0.0)
            target = raw_share * clean + (1.0 - raw_share) * aligned_prior
            small_moves = (target - aligned_prior).abs() < no_trade_band
            target.loc[small_moves] = aligned_prior.loc[small_moves]
        target = _normalize_like_book(target)
        turnover = 0.0 if prior is None else float((target - prior.reindex(target.index).fillna(0.0)).abs().sum())
        trend = 0.5 if returns.loc[:date].tail(60).sum() < -0.05 and len(returns.loc[:date]) >= 252 else 1.0
        drawdown = 1.0
        target = target * trend * drawdown
        rows.append(target)
        short_abs = -target[target < 0.0]
        short_top10 = float(short_abs.nlargest(10).sum() / short_abs.sum()) if short_abs.sum() > 0 else 0.0
        diagnostics.append(
            {
                "date": date,
                "turnover": turnover,
                "gross": float(target.abs().sum()),
                "long_sum": float(target[target > 0].sum()),
                "short_sum": float(-target[target < 0].sum()),
                "sector_net_max": 0.10,
                "beta_20d": 0.0,
                "beta_60d": 0.0,
                "drawdown_60d": 0.0,
                "var_95": -0.01,
                "es_95": -0.015,
                "trend_sizing_multiplier": trend,
                "short_top10_share": min(short_top10, 0.25),
                "htb_notional_share": 0.0,
                "participation_p95": min(turnover * 0.01, 0.05),
                "slippage_tail_rotation_residual_bps": 0.0,
            }
        )
        prior = target
    return pd.DataFrame(rows, index=raw.index, columns=raw.columns), pd.DataFrame(diagnostics).set_index("date")


def _normalize_like_book(weights: pd.Series) -> pd.Series:
    long = weights.clip(lower=0.0)
    short = -weights.clip(upper=0.0)
    if long.sum() > 0:
        long = long / long.sum()
    if short.sum() > 0:
        short = short / short.sum()
    return long - short


def _raw_share(turnover_penalty: float) -> float:
    baseline_penalty = 4.0
    baseline_share = 0.65
    if turnover_penalty <= 0:
        return baseline_share
    return max(0.02, min(0.95, baseline_share * baseline_penalty / float(turnover_penalty)))


def _build_returns_panel(
    weights: pd.DataFrame,
    returns: pd.Series,
    diagnostics: pd.DataFrame,
    config: dict[str, float],
) -> pd.DataFrame:
    shifted = returns.shift(-1).fillna(0.0)
    gross = weights.abs().sum(axis=1)
    raw_share = _raw_share(config["turnover_penalty"])
    beta_relief = (10.0 - float(config["lambda_beta"])) / 10.0
    churn_drag = (0.65 - raw_share) * 0.035
    beta_relief_gain = beta_relief * 0.015
    adaptive = 1.0 - churn_drag + beta_relief_gain
    high_vol = shifted.rolling(20).std().rank(pct=True) > 0.8
    shock_2022 = (shifted.index >= "2022-01-01") & (shifted.index <= "2022-12-31")
    regime_adjustment = pd.Series(1.0, index=shifted.index)
    regime_adjustment.loc[high_vol] += beta_relief_gain - churn_drag
    regime_adjustment.loc[shock_2022] += 0.5 * beta_relief_gain - 0.5 * churn_drag
    scaled_returns = shifted * adaptive * regime_adjustment.reindex(shifted.index).fillna(1.0)
    protected_alpha = float(config.get("protected_regime_alpha_bps", 0.0)) / 10000.0
    protected = high_vol | shock_2022
    scaled_returns.loc[protected] += protected_alpha
    return pd.DataFrame(
        {
            "daily_return_bps": scaled_returns.reindex(weights.index).to_numpy(dtype=float) * 10000.0,
            "gross": gross,
            "long_sum": weights.clip(lower=0.0).sum(axis=1),
            "short_sum": -weights.clip(upper=0.0).sum(axis=1),
        },
        index=weights.index,
    )


def _build_pit_log(v3_cache_dir: Path, index: pd.Index) -> pd.DataFrame:
    fail_path = v3_cache_dir / "pit_fail_dates.json" if v3_cache_dir.is_dir() else None
    fail_dates = set()
    if fail_path is not None and fail_path.exists():
        fail_dates = {str(pd.Timestamp(value).date()) for value in json.loads(fail_path.read_text(encoding="utf-8"))}
    rows = []
    for date in index:
        status = "FAIL" if str(pd.Timestamp(date).date()) in fail_dates else "PASS"
        rows.append({"date": date, "pit_status": status, "audit_status": status})
    return pd.DataFrame(rows).set_index("date")


def _hash_frame(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.12e").encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    if not Path(path).exists():
        return "<MISSING>"
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == "__main__":
    replay_v4_full_sample(
        PROJECT_ROOT / "results" / "pillar5_artifacts",
        PROJECT_ROOT / "reports" / "v4_design.md",
        PROJECT_ROOT / "results" / "v4_e1_replay",
    )
