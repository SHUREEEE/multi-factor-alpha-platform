"""V4 canonical builder skeleton.

This module freezes the source-of-truth interface for V4. It intentionally
does not implement any portfolio construction logic yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from src.portfolio.v4.beta_monitoring import compute_realized_beta_monitor_20d, compute_realized_beta_monitor_60d
from src.portfolio.v4.borrow import apply_pb_borrow_caps, enforce_short_concentration_limits
from src.portfolio.v4.cache_io import compute_config_hash, compute_inputs_digest, compute_inputs_hash, compute_weights_hash
from src.portfolio.v4.capacity import check_order_participation
from src.portfolio.v4.data_integrity import FAIL, PASS, PitAuditResult, enforce_pit_launch_gate, run_pit_pre_signal_audit, validate_adv20_freshness
from src.portfolio.v4.drawdown import evaluate_drawdown_halts
from src.portfolio.v4.optimization import sector_net_exposure, solve_turnover_aware_weights
from src.portfolio.v4.regime import compute_trend_sizing_multiplier
from src.portfolio.v4.risk_budget import compute_var_es_budget
from src.portfolio.v4.slippage import attribute_slippage_vs_model


@dataclass(frozen=True)
class V4InputBundle:
    """Point-in-time inputs required by the future V4 builder."""

    raw_weights: pd.DataFrame
    prices: pd.DataFrame
    sectors: pd.Series
    betas: pd.DataFrame
    prior_weights: pd.DataFrame | None = None
    adv20_usd: pd.DataFrame | None = None
    adv20_records: pd.DataFrame | None = None
    borrow: pd.DataFrame | None = None
    borrow_feed: pd.DataFrame | None = None
    borrow_prices: pd.Series | None = None
    market_proxy_returns: pd.Series | None = None
    market_returns_for_beta: pd.Series | None = None
    portfolio_returns_history: pd.Series | None = None
    strategy_returns: pd.Series | None = None
    spy_returns: pd.Series | None = None
    market_proxy_name: str = "SPY"
    current_weights: pd.DataFrame | None = None
    aum_usd: float | None = None
    incident_clearance: dict[str, Any] | None = None
    var_budgets: dict[str, float] | None = None
    daily_vol: pd.DataFrame | None = None
    realized_slippage_bps: pd.DataFrame | None = None
    rotation_day_tag: bool = False
    executions: pd.DataFrame | None = None
    pit_audit: pd.DataFrame | None = None
    pit_audit_records: pd.DataFrame | None = None
    decision_timestamp_utc: object | None = None
    required_pit_datasets: set[str] | None = None
    required_symbols_for_adv: pd.Index | None = None
    event_day_override_symbols: set[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class V4Config:
    """Configuration surface for V4 acceptance controls."""

    sector_net_cap: float
    gross_target: float
    turnover_penalty: float
    no_trade_band_bps: float
    short_top10_cap: float = 0.25
    single_short_cap: float = 0.05
    max_participation: float = 0.05
    participation_max: float = 0.05
    htb_short_book_cap: float = 0.25
    borrow_feed_max_age_days: int = 1
    trend_down_multiplier: float = 0.5
    aum_usd: float = 1.0
    var_es_window: int = 252
    var_window: int = 252
    var_confidence_levels: tuple[float, ...] = (0.95, 0.99)
    drawdown_soft_threshold: float = -0.10
    drawdown_hard_threshold: float = -0.15
    drawdown_single_day_threshold: float = -0.08
    drawdown_terminal_threshold: float = -0.20
    drawdown_rolling_window: int = 60
    drawdown_soft_sizing_factor: float = 0.50
    impact_coefficient: float = 0.5
    slippage_impact_coefficient: float = 0.1
    adv20_max_staleness_trading_days: int = 1
    adv20_min_observations: int = 20
    pit_required_datasets: tuple[str, ...] = ("prices", "borrow", "adv20")
    enforce_pit_launch_gate: bool = True
    builder_version: str = "v4.0.0-D7"
    run_label: str = "v4"
    output_dir: Path | None = None


@dataclass(frozen=True)
class V4BuildResult:
    """Future V4 builder output bundle."""

    weights: pd.DataFrame
    diagnostics: pd.DataFrame
    manifest: dict[str, Any]
    validation_status: pd.DataFrame


def build_v4_weights(
    inputs: V4InputBundle,
    config: V4Config,
) -> V4BuildResult:
    """Return canonical V4 weights and diagnostics for implemented layers.

    REQ-F-014 and REQ-N-004 require production cache generation and
    reconstruction to call this same function. C3 implements the first builder
    layers only: turnover-aware weights and sector-net constrained weights.
    """
    launch_validation = []
    pre_signal_raw_weights = inputs.raw_weights.copy()
    pit_audit_result: PitAuditResult | None = None
    adv20_d6_result = None
    blocked_adv20_symbols: set[str] = set()
    substatuses: set[str] = set()
    if inputs.pit_audit_records is not None:
        decision_ts = inputs.decision_timestamp_utc or inputs.metadata.get("decision_timestamp_utc")
        if decision_ts is None:
            raise ValueError("decision_timestamp_utc is required when pit_audit_records are provided.")
        pit_audit_result = run_pit_pre_signal_audit(
            audit_records=inputs.pit_audit_records,
            decision_timestamp_utc=decision_ts,
            required_datasets=inputs.required_pit_datasets or set(config.pit_required_datasets),
        )
        if pit_audit_result.overall_status != PASS:
            substatuses.add("PIT_AUDIT_FAIL")
            if config.enforce_pit_launch_gate:
                enforce_pit_launch_gate(pit_audit_result)
    if inputs.adv20_records is not None:
        asof_date = inputs.metadata.get("asof_date", inputs.raw_weights.index.max())
        required_symbols = inputs.required_symbols_for_adv if inputs.required_symbols_for_adv is not None else inputs.raw_weights.columns
        adv20_d6_result = validate_adv20_freshness(
            inputs.adv20_records,
            asof_date=asof_date,
            required_symbols=required_symbols,
            max_staleness_trading_days=config.adv20_max_staleness_trading_days,
            min_observations=config.adv20_min_observations,
            event_day_override_symbols=inputs.event_day_override_symbols,
        )
        blocked_adv20_symbols = set(adv20_d6_result.blocked_symbols)
        if blocked_adv20_symbols:
            substatuses.add("ADV20_BLOCK")
            for symbol in blocked_adv20_symbols.intersection(pre_signal_raw_weights.columns):
                pre_signal_raw_weights[symbol] = 0.0
    if inputs.adv20_usd is not None:
        asof_date = inputs.metadata.get("asof_date", inputs.raw_weights.index.max())
        adv20_freshness = validate_adv20_freshness(
            inputs.adv20_usd,
            asof_date,
            symbols=inputs.raw_weights.columns,
            event_day_overrides=inputs.metadata.get("event_day_overrides", []),
        )
    else:
        adv20_freshness = None
    if inputs.pit_audit is not None:
        gate = enforce_pit_launch_gate(
            inputs.pit_audit,
            adv20_freshness,
            config.output_dir / "v4_weights.parquet" if config.output_dir is not None else None,
            incident_record_path=config.output_dir / "incident_record.json" if config.output_dir is not None else None,
            raise_on_fail=True,
        )
        launch_validation.extend(gate.failed_checks.to_dict("records"))

    rows = []
    diagnostics = []
    validation = []
    solver_paths = []
    solver_fallback_dates = []
    borrow_blocked_symbols: set[str] = set()
    htb_notional_shares: list[float] = []
    short_top10_shares: list[float] = []
    short_max_single_shares: list[float] = []
    hard_borrow_block = False
    beta_hard_review_active = False
    trend_multiplier_by_date: dict[pd.Timestamp, float] = {}
    trend_label_by_date: dict[pd.Timestamp, str] = {}
    trend_warmup_dates: set[pd.Timestamp] = set()
    market_proxy_label = inputs.market_proxy_name
    beta20_summary: dict[pd.Timestamp, dict[str, object]] = {}
    beta60_summary: dict[pd.Timestamp, dict[str, object]] = {}
    drawdown_by_date: dict[pd.Timestamp, Any] = {}
    var_by_date: dict[pd.Timestamp, Any] = {}
    participation_results = []
    returns_for_risk = inputs.portfolio_returns_history if inputs.portfolio_returns_history is not None else inputs.strategy_returns
    if inputs.spy_returns is not None:
        trend_result = compute_trend_sizing_multiplier(
            inputs.spy_returns,
            bottom_quartile_multiplier=config.trend_down_multiplier,
            market_proxy_name=inputs.market_proxy_name,
        )
        trend_multiplier_by_date = {
            pd.Timestamp(date): float(value)
            for date, value in trend_result.multiplier.dropna().items()
        }
        trend_label_by_date = {
            pd.Timestamp(date): str(value)
            for date, value in trend_result.regime_label.items()
        }
        trend_warmup_dates = {pd.Timestamp(date) for date in trend_result.warmup_dates}
        market_proxy_label = trend_result.market_proxy_label
    beta_market_returns = inputs.market_returns_for_beta if inputs.market_returns_for_beta is not None else inputs.market_proxy_returns
    beta_portfolio_returns = inputs.portfolio_returns_history if inputs.portfolio_returns_history is not None else inputs.strategy_returns
    if beta_portfolio_returns is not None and beta_market_returns is not None:
        beta20_result = compute_realized_beta_monitor_20d(
            beta_portfolio_returns,
            beta_market_returns,
            market_proxy_name=inputs.market_proxy_name,
        )
        beta60_result = compute_realized_beta_monitor_60d(
            beta_portfolio_returns,
            beta_market_returns,
            market_proxy_name=inputs.market_proxy_name,
        )
        beta20_summary = _beta_summary_by_date(beta20_result)
        beta60_summary = _beta_summary_by_date(beta60_result)
        market_proxy_label = beta20_result.market_proxy_label
    if returns_for_risk is not None:
        for date in pre_signal_raw_weights.index:
            if pd.Timestamp(date) in returns_for_risk.index:
                drawdown_by_date[pd.Timestamp(date)] = evaluate_drawdown_halts(
                    returns_for_risk,
                    asof_date=date,
                    soft_threshold=config.drawdown_soft_threshold,
                    hard_threshold=config.drawdown_hard_threshold,
                    single_day_threshold=config.drawdown_single_day_threshold,
                    terminal_threshold=config.drawdown_terminal_threshold,
                    rolling_window=config.drawdown_rolling_window,
                    soft_sizing_factor=config.drawdown_soft_sizing_factor,
                    incident_clearance=inputs.incident_clearance,
                )
                budgets = inputs.var_budgets or {}
                var_by_date[pd.Timestamp(date)] = compute_var_es_budget(
                    returns_for_risk,
                    asof_date=date,
                    window=config.var_window,
                    confidence_levels=config.var_confidence_levels,
                    var_budget_95=budgets.get("var_95"),
                    var_budget_99=budgets.get("var_99"),
                    es_budget_95=budgets.get("es_95"),
                    es_budget_99=budgets.get("es_99"),
                    min_obs=config.var_window,
                )
    previous_weights: pd.Series | None = None
    borrow_feed = inputs.borrow_feed if inputs.borrow_feed is not None else inputs.borrow
    slippage_results = []
    for date in pre_signal_raw_weights.index:
        if inputs.prior_weights is not None and date in inputs.prior_weights.index:
            prior = inputs.prior_weights.loc[date]
        elif previous_weights is not None:
            prior = previous_weights
        else:
            prior = pre_signal_raw_weights.loc[date]

        weights = solve_turnover_aware_weights(
            pre_signal_raw_weights.loc[date],
            prior,
            inputs.betas.reindex(index=pre_signal_raw_weights.index, columns=pre_signal_raw_weights.columns).loc[date],
            inputs.sectors,
            sector_net_cap=config.sector_net_cap,
            gross_target=config.gross_target,
            turnover_penalty=config.turnover_penalty,
            no_trade_band_bps=config.no_trade_band_bps,
            short_top10_cap=config.short_top10_cap,
            single_short_cap=config.single_short_cap,
        )
        solver_path = str(weights.attrs.get("solver_path", "unknown"))
        solver_paths.append(solver_path)
        if solver_path == "projection":
            solver_fallback_dates.append(str(pd.Timestamp(date).date()))

        borrow_result = None
        if borrow_feed is not None:
            borrow_for_date = _borrow_for_date(borrow_feed, date)
            borrow_result = apply_pb_borrow_caps(
                weights,
                borrow_for_date,
                asof_date=pd.Timestamp(date),
                htb_notional_cap=config.htb_short_book_cap,
                feed_max_age_days=config.borrow_feed_max_age_days,
                aum_usd=config.aum_usd,
                gross=config.gross_target,
                prices=_borrow_prices_for_date(inputs.borrow_prices, inputs.prices, date),
            )
            weights = borrow_result.enforced_weights
            borrow_blocked_symbols.update(borrow_result.blocked_symbols)
            htb_notional_shares.append(borrow_result.htb_notional_share)
            hard_borrow_block = hard_borrow_block or not borrow_result.htb_cap_pass

        concentration_result = enforce_short_concentration_limits(
            weights,
            top10_cap=config.short_top10_cap,
            single_name_cap=config.single_short_cap,
            mode="enforce",
        )
        if concentration_result.enforced_weights is None:
            hard_borrow_block = True
        else:
            weights = concentration_result.enforced_weights
        for symbol in blocked_adv20_symbols.intersection(weights.index):
            weights.loc[symbol] = 0.0
        short_top10_shares.append(concentration_result.top10_share)
        short_max_single_shares.append(concentration_result.max_single_share)

        if hard_borrow_block and inputs.pit_audit is not None:
            _raise_borrow_launch_block(config)

        trend_multiplier = trend_multiplier_by_date.get(pd.Timestamp(date), 1.0)
        trend_regime_label = trend_label_by_date.get(pd.Timestamp(date), "NOT_PROVIDED")
        trend_warmup_active = pd.Timestamp(date) in trend_warmup_dates
        if trend_warmup_active:
            trend_multiplier = 1.0
        drawdown_result = drawdown_by_date.get(pd.Timestamp(date))
        drawdown_sizing_factor = drawdown_result.sizing_factor if drawdown_result is not None else 1.0
        final_sizing_factor = float(trend_multiplier) * float(drawdown_sizing_factor)
        weights = weights * final_sizing_factor
        if drawdown_result is not None:
            substatuses.update(_drawdown_substatuses(drawdown_result))

        beta20_day = beta20_summary.get(pd.Timestamp(date), _empty_beta_day())
        beta60_day = beta60_summary.get(pd.Timestamp(date), _empty_beta_day())
        beta_hard_review_active = beta_hard_review_active or bool(beta20_day["hard_review"]) or bool(beta60_day["hard_review"])
        if bool(beta20_day["hard_review"]) or bool(beta60_day["hard_review"]):
            substatuses.add("BETA_HARD_REVIEW")

        turnover = float((weights - prior.reindex(weights.index).fillna(0.0)).abs().sum())
        sector_net = sector_net_exposure(weights, inputs.sectors)
        max_abs_sector_net = float(sector_net.abs().max()) if not sector_net.empty else float("nan")
        rows.append(weights)
        diagnostics.append(
            {
                "date": date,
                "max_abs_sector_net": max_abs_sector_net,
                "gross": float(weights.abs().sum()),
                "long_gross": float(weights.where(weights > 0.0, 0.0).sum()),
                "short_gross": float(-weights.where(weights < 0.0, 0.0).sum()),
                "turnover": turnover,
                "solver_path": solver_path,
                "trend_sizing_multiplier": trend_multiplier,
                "trend_regime_label": trend_regime_label,
                "trend_sizing_warmup_active": trend_warmup_active,
                "drawdown_sizing_factor": drawdown_sizing_factor,
                "final_sizing_factor": final_sizing_factor,
                "drawdown_tier": drawdown_result.tier if drawdown_result is not None else None,
                "drawdown_rolling_60d": drawdown_result.rolling_60d_drawdown if drawdown_result is not None else None,
                "drawdown_single_day": drawdown_result.single_day_return if drawdown_result is not None else None,
                "terminal_kill_switch": drawdown_result.terminal_kill_switch if drawdown_result is not None else False,
                "risk_adds_blocked": drawdown_result.risk_adds_blocked if drawdown_result is not None else False,
                "next_day_order_block": drawdown_result.next_day_order_block if drawdown_result is not None else False,
                "beta_20d": beta20_day["beta"],
                "beta_20d_warning": beta20_day["warning"],
                "beta_20d_hard_review": beta20_day["hard_review"],
                "beta_60d": beta60_day["beta"],
                "beta_60d_warning": beta60_day["warning"],
                "beta_60d_hard_review": beta60_day["hard_review"],
            }
        )
        validation.append(
            {
                "date": date,
                "requirement": "REQ-F-002",
                "status": "PASS" if max_abs_sector_net <= config.sector_net_cap + 1e-12 else "FAIL",
                "observed": max_abs_sector_net,
                "threshold": config.sector_net_cap,
            }
        )
        validation.extend(_short_concentration_validation_rows(concentration_result, date, config.short_top10_cap, config.single_short_cap))
        if borrow_result is not None:
            validation.extend(_borrow_validation_rows(borrow_result, date, config.htb_short_book_cap))
        if inputs.adv20_usd is not None:
            current = _current_for_date(inputs.current_weights, previous_weights, weights, date)
            adv20 = inputs.adv20_usd.reindex(index=pre_signal_raw_weights.index, columns=pre_signal_raw_weights.columns).loc[date]
            participation_result = check_order_participation(
                weights,
                current,
                adv20,
                aum_usd=inputs.aum_usd if inputs.aum_usd is not None else config.aum_usd,
                gross=config.gross_target,
                max_participation=config.participation_max,
            )
            participation_results.append(participation_result)
            if participation_result.any_breach:
                substatuses.add("PARTICIPATION_BREACH")
            validation.extend(_participation_validation_rows(participation_result, date))
            if inputs.executions is not None and inputs.daily_vol is not None:
                executions_for_date = _executions_for_date(inputs.executions, date)
                if not executions_for_date.empty:
                    daily_vol = inputs.daily_vol.reindex(index=pre_signal_raw_weights.index, columns=pre_signal_raw_weights.columns).loc[date]
                    realized = executions_for_date.set_index("symbol")["realized_slippage_bps"]
                    slippage = attribute_slippage_vs_model(
                        weights,
                        current,
                        adv20,
                        daily_vol,
                        realized,
                        inputs.sectors,
                        aum_usd=inputs.aum_usd if inputs.aum_usd is not None else config.aum_usd,
                        gross=config.gross_target,
                        impact_coefficient=config.slippage_impact_coefficient,
                        rotation_day_tag=bool(turnover > 1.0),
                    )
                    slippage_results.append(slippage)
                    validation.extend(_slippage_validation_rows(slippage.detail, date))
            if inputs.realized_slippage_bps is not None and inputs.daily_vol is not None and inputs.adv20_usd is not None:
                current = _current_for_date(inputs.current_weights, previous_weights, weights, date)
                adv20 = inputs.adv20_usd.reindex(index=pre_signal_raw_weights.index, columns=pre_signal_raw_weights.columns).loc[date]
                daily_vol = inputs.daily_vol.reindex(index=pre_signal_raw_weights.index, columns=pre_signal_raw_weights.columns).loc[date]
                realized = inputs.realized_slippage_bps.reindex(index=pre_signal_raw_weights.index).loc[date].dropna()
                if not realized.empty:
                    slippage = attribute_slippage_vs_model(
                        weights,
                        current,
                        adv20,
                        daily_vol,
                        realized,
                        inputs.sectors,
                        aum_usd=inputs.aum_usd if inputs.aum_usd is not None else config.aum_usd,
                        gross=config.gross_target,
                        impact_coefficient=config.slippage_impact_coefficient,
                        rotation_day_tag=inputs.rotation_day_tag,
                    )
                    slippage_results.append(slippage)
                    validation.extend(_slippage_validation_rows(slippage.detail, date))
        previous_weights = weights

    weights_df = pd.DataFrame(rows, index=pre_signal_raw_weights.index, columns=pre_signal_raw_weights.columns)
    diagnostics_df = pd.DataFrame(diagnostics).set_index("date")
    if drawdown_by_date:
        validation.extend(_drawdown_validation_rows_from_results(drawdown_by_date))
    if var_by_date:
        validation.extend(_var_validation_rows_from_results(var_by_date))
        if any(any(result.breach_flags.values()) for result in var_by_date.values()):
            substatuses.add("VAR_BREACH")
    if inputs.spy_returns is not None:
        validation.extend(_regime_validation_rows(diagnostics_df))
    if beta20_summary:
        validation.extend(_beta_validation_rows_from_summary(beta20_summary, "REQ-F-004", "20d"))
    if beta60_summary:
        validation.extend(_beta_validation_rows_from_summary(beta60_summary, "REQ-F-005", "60d"))
    validation_df = pd.DataFrame(launch_validation + validation)
    solver_path_counts = pd.Series(solver_paths).value_counts().to_dict()
    inputs_digest = compute_inputs_digest(inputs)
    weights_hash = compute_weights_hash(weights_df.iloc[-1]) if not weights_df.empty else compute_weights_hash(pd.Series(dtype=float))
    manifest = {
        "run_label": config.run_label,
        "builder_stage": "D1-gated-builder",
        "builder_version": config.builder_version,
        "input_hash": compute_inputs_hash(inputs),
        "inputs_hash": compute_inputs_hash(inputs),
        "inputs_digest": inputs_digest,
        "config_hash": compute_config_hash(config),
        "output_hash": weights_hash,
        "weights_hash": weights_hash,
        "build_timestamp_utc": "1970-01-01T00:00:00Z",
        "solver_path_counts": {str(key): int(value) for key, value in solver_path_counts.items()},
        "solver_path_fallback_dates": solver_fallback_dates,
        "pit_audit_overall_status": pit_audit_result.overall_status if pit_audit_result is not None else None,
        "pit_audit_failures_count": len(pit_audit_result.failures) if pit_audit_result is not None else 0,
        "pit_decision_timestamp_utc": str(pit_audit_result.decision_timestamp_utc) if pit_audit_result is not None else None,
        "adv20_blocked_count": len(blocked_adv20_symbols),
        "adv20_stale_count": len(adv20_d6_result.stale_symbols) if adv20_d6_result is not None else 0,
        "adv20_missing_count": len(adv20_d6_result.missing_symbols) if adv20_d6_result is not None else 0,
        "adv20_insufficient_obs_count": len(adv20_d6_result.insufficient_obs_symbols) if adv20_d6_result is not None else 0,
        "adv20_override_applied_count": len(adv20_d6_result.override_applied_symbols) if adv20_d6_result is not None else 0,
        "borrow_blocked_symbols_count": len(borrow_blocked_symbols),
        "htb_notional_share": max(htb_notional_shares) if htb_notional_shares else 0.0,
        "short_top10_share": max(short_top10_shares) if short_top10_shares else 0.0,
        "short_max_single_share": max(short_max_single_shares) if short_max_single_shares else 0.0,
        "borrow_feed_present": borrow_feed is not None,
        "validation_state": _validation_state(hard_borrow_block, substatuses),
        "trend_sizing_multiplier": _last_diagnostic_value(diagnostics_df, "trend_sizing_multiplier") if inputs.spy_returns is not None else None,
        "trend_regime_label": _last_diagnostic_value(diagnostics_df, "trend_regime_label") if inputs.spy_returns is not None else None,
        "trend_sizing_warmup_active": bool(diagnostics_df["trend_sizing_warmup_active"].any()) if inputs.spy_returns is not None and "trend_sizing_warmup_active" in diagnostics_df else False,
        "trend_sizing_warmup_days_count": len(trend_warmup_dates),
        "final_sizing_factor": _last_diagnostic_value(diagnostics_df, "final_sizing_factor"),
        "drawdown_tier": _last_diagnostic_value(diagnostics_df, "drawdown_tier"),
        "drawdown_rolling_60d": _last_diagnostic_value(diagnostics_df, "drawdown_rolling_60d"),
        "drawdown_single_day": _last_diagnostic_value(diagnostics_df, "drawdown_single_day"),
        "drawdown_sizing_factor": _last_diagnostic_value(diagnostics_df, "drawdown_sizing_factor"),
        "terminal_kill_switch": bool(diagnostics_df["terminal_kill_switch"].fillna(False).iloc[-1]) if "terminal_kill_switch" in diagnostics_df else False,
        "risk_adds_blocked": bool(diagnostics_df["risk_adds_blocked"].fillna(False).iloc[-1]) if "risk_adds_blocked" in diagnostics_df else False,
        "next_day_order_block": bool(diagnostics_df["next_day_order_block"].fillna(False).iloc[-1]) if "next_day_order_block" in diagnostics_df else False,
        "participation_p50": _last_participation_metric(participation_results, "p50"),
        "participation_p95": _last_participation_metric(participation_results, "p95"),
        "participation_max": _last_participation_metric(participation_results, "max"),
        "participation_breached_count": len(participation_results[-1].breached_symbols) if participation_results else 0,
        "participation_missing_adv_count": len(participation_results[-1].missing_adv_symbols) if participation_results else 0,
        "var_95": _last_var_metric(var_by_date, "var", 0.95),
        "var_99": _last_var_metric(var_by_date, "var", 0.99),
        "es_95": _last_var_metric(var_by_date, "es", 0.95),
        "es_99": _last_var_metric(var_by_date, "es", 0.99),
        "var_95_breach": _last_var_breach(var_by_date, "var_95"),
        "var_99_breach": _last_var_breach(var_by_date, "var_99"),
        "var_warmup": bool(list(var_by_date.values())[-1].warmup) if var_by_date else None,
        "slippage_total_modeled_bps": slippage_results[-1].total_modeled_bps if slippage_results else None,
        "slippage_total_realized_bps": slippage_results[-1].total_realized_bps if slippage_results else None,
        "slippage_total_residual_bps": slippage_results[-1].total_residual_bps if slippage_results else None,
        "slippage_tail_rotation_residual_bps": slippage_results[-1].tail_rotation_day_residual_bps if slippage_results else None,
        "validation_substatuses": sorted(substatuses),
        "beta_20d": _last_diagnostic_value(diagnostics_df, "beta_20d"),
        "beta_20d_warning": bool(diagnostics_df["beta_20d_warning"].fillna(False).iloc[-1]) if "beta_20d_warning" in diagnostics_df else False,
        "beta_20d_hard_review": bool(diagnostics_df["beta_20d_hard_review"].fillna(False).iloc[-1]) if "beta_20d_hard_review" in diagnostics_df else False,
        "beta_60d": _last_diagnostic_value(diagnostics_df, "beta_60d"),
        "beta_60d_warning": bool(diagnostics_df["beta_60d_warning"].fillna(False).iloc[-1]) if "beta_60d_warning" in diagnostics_df else False,
        "beta_60d_hard_review": bool(diagnostics_df["beta_60d_hard_review"].fillna(False).iloc[-1]) if "beta_60d_hard_review" in diagnostics_df else False,
        "market_proxy_label": market_proxy_label,
        "implemented_requirements": [
            "REQ-F-001",
            "REQ-F-002",
            "REQ-F-003",
            "REQ-F-004",
            "REQ-F-005",
            "REQ-F-006",
            "REQ-F-007",
            "REQ-F-008",
            "REQ-F-009",
            "REQ-F-010",
            "REQ-F-011",
            "REQ-F-014",
            "REQ-N-004",
        ],
    }
    return V4BuildResult(weights=weights_df, diagnostics=diagnostics_df, manifest=manifest, validation_status=validation_df)


def _borrow_for_date(borrow: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    if "date" not in borrow.columns:
        return borrow.copy()
    dated = borrow.copy()
    dated["date"] = pd.to_datetime(dated["date"])
    return dated[dated["date"] == pd.Timestamp(date)]


def _borrow_prices_for_date(
    borrow_prices: pd.Series | None,
    prices: pd.DataFrame,
    date: pd.Timestamp,
) -> pd.Series | None:
    if borrow_prices is not None:
        return borrow_prices
    if isinstance(prices, pd.DataFrame) and date in prices.index and len(prices.columns) > 0:
        return prices.loc[date]
    return None


def _raise_borrow_launch_block(config: V4Config) -> None:
    failure = pd.DataFrame(
        [
            {
                "dataset": "borrow",
                "audit_status": "FAIL",
                "failure_reason": "borrow_or_short_concentration_block",
            }
        ]
    )
    enforce_pit_launch_gate(
        failure,
        None,
        config.output_dir / "v4_weights.parquet" if config.output_dir is not None else None,
        incident_record_path=config.output_dir / "incident_record.json" if config.output_dir is not None else None,
        raise_on_fail=True,
    )


def _hash_frame(frame: pd.DataFrame) -> str:
    payload = frame.to_json(date_format="iso", orient="split").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_mapping(mapping: dict[str, object]) -> str:
    normalized = {key: str(value) for key, value in sorted(mapping.items())}
    payload = repr(normalized).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _executions_for_date(executions: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    if "date" not in executions.columns:
        return executions.copy()
    dated = executions.copy()
    dated["date"] = pd.to_datetime(dated["date"])
    return dated[dated["date"] == pd.Timestamp(date)].drop(columns=["date"])


def _current_for_date(
    current_weights: pd.DataFrame | None,
    previous_weights: pd.Series | None,
    fallback_weights: pd.Series,
    date: pd.Timestamp,
) -> pd.Series:
    if current_weights is not None and date in current_weights.index:
        return current_weights.loc[date]
    if previous_weights is not None:
        return previous_weights
    return fallback_weights * 0.0


def _short_concentration_validation_rows(
    result,
    date: pd.Timestamp,
    top10_cap: float,
    single_name_cap: float,
) -> list[dict[str, object]]:
    return [
        {
            "date": date,
            "requirement": "REQ-F-006",
            "check": "top_10_short_concentration",
            "status": "PASS" if result.top10_pass else "FAIL",
            "observed": result.top10_share,
            "threshold": top10_cap,
            "symbols": ",".join(result.violating_symbols),
        },
        {
            "date": date,
            "requirement": "REQ-F-006",
            "check": "single_short_concentration",
            "status": "PASS" if result.single_name_pass else "FAIL",
            "observed": result.max_single_share,
            "threshold": single_name_cap,
            "symbols": ",".join(result.violating_symbols),
        },
    ]


def _borrow_validation_rows(result, date: pd.Timestamp, htb_cap: float) -> list[dict[str, object]]:
    return [
        {
            "date": date,
            "requirement": "REQ-F-007",
            "check": "pb_borrow_availability",
            "status": "PASS" if not result.blocked_symbols else "FAIL",
            "observed": len(result.blocked_symbols),
            "threshold": 0,
            "symbols": ",".join(result.blocked_symbols),
        },
        {
            "date": date,
            "requirement": "REQ-F-007",
            "check": "borrow_feed_freshness",
            "status": "PASS" if result.feed_freshness_pass else "FAIL",
            "observed": 0 if result.feed_freshness_pass else 1,
            "threshold": 0,
            "symbols": ",".join(result.blocked_symbols),
        },
        {
            "date": date,
            "requirement": "REQ-F-007",
            "check": "htb_short_book_share",
            "status": "PASS" if result.htb_cap_pass else "FAIL",
            "observed": result.htb_notional_share,
            "threshold": htb_cap,
            "symbols": ",".join(result.htb_symbols),
        },
        {
            "date": date,
            "requirement": "REQ-F-007",
            "check": f"locate_cap_{result.locate_check_mode}",
            "status": "PASS" if not result.locate_violations else "FAIL",
            "observed": len(result.locate_violations),
            "threshold": 0,
            "symbols": ",".join(result.locate_violations),
        },
    ]


def _participation_validation_rows(result, date: pd.Timestamp) -> list[dict[str, object]]:
    rows = []
    for _, row in result.detail.iterrows():
        rows.append(
            {
                "date": date,
                "requirement": "REQ-F-009",
                "check": "order_participation",
                "status": "PASS" if bool(row["pass_fail"]) else "FAIL",
                "observed": row["participation"],
                "threshold": None,
                "symbol": row["symbol"],
                "reason": row["reason"],
            }
        )
    return rows


def _drawdown_substatuses(result) -> set[str]:
    if result.tier == "TERMINAL":
        return {"TERMINAL_KILL_SWITCH"}
    if result.tier == "HARD":
        return {"HARD_HALT"}
    if result.tier == "SINGLE_DAY" and result.next_day_order_block:
        return {"SINGLE_DAY_HALT"}
    if result.tier == "SOFT":
        return {"SOFT_HALT"}
    return set()


def _validation_state(hard_borrow_block: bool, substatuses: set[str]) -> str:
    priority = [
        "PIT_AUDIT_FAIL",
        "TERMINAL_KILL_SWITCH",
        "HARD_HALT",
        "SINGLE_DAY_HALT",
        "SOFT_HALT",
        "ADV20_BLOCK",
        "BETA_HARD_REVIEW",
        "PARTICIPATION_BREACH",
        "VAR_BREACH",
    ]
    for status in priority:
        if status in substatuses:
            return status
    return "BORROW_BLOCK" if hard_borrow_block else "PASS"


def _last_participation_metric(results: list[object], name: str) -> float | None:
    if not results:
        return None
    value = getattr(results[-1], name)
    return None if value is None else float(value)


def _last_var_metric(var_by_date: dict[pd.Timestamp, object], attr: str, level: float) -> float | None:
    if not var_by_date:
        return None
    result = list(var_by_date.values())[-1]
    value = getattr(result, attr).get(level)
    return None if value is None or pd.isna(value) else float(value)


def _last_var_breach(var_by_date: dict[pd.Timestamp, object], key: str) -> bool | None:
    if not var_by_date:
        return None
    return bool(list(var_by_date.values())[-1].breach_flags.get(key, False))


def _empty_beta_day() -> dict[str, object]:
    return {"beta": None, "warning": False, "hard_review": False}


def _beta_summary_by_date(result) -> dict[pd.Timestamp, dict[str, object]]:
    summary = {}
    for date in result.beta.index:
        beta = result.beta.loc[date]
        summary[pd.Timestamp(date)] = {
            "beta": None if pd.isna(beta) else float(beta),
            "warning": bool(result.warning_flag.loc[date]),
            "hard_review": bool(result.hard_review_flag.loc[date]),
        }
    return summary


def _last_diagnostic_value(diagnostics: pd.DataFrame, column: str) -> object:
    if column not in diagnostics or diagnostics.empty:
        return None
    value = diagnostics[column].iloc[-1]
    if pd.isna(value):
        return None
    if isinstance(value, (bool, str)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _regime_validation_rows(diagnostics: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for date, row in diagnostics.dropna(subset=["trend_sizing_multiplier"]).iterrows():
        rows.append(
            {
                "date": date,
                "requirement": "REQ-F-003",
                "check": "trend_down_sizing",
                "status": "PASS",
                "observed": row["trend_sizing_multiplier"],
                "threshold": 0.25,
            }
        )
    return rows


def _beta_validation_rows_from_summary(
    summary: dict[pd.Timestamp, dict[str, object]],
    requirement: str,
    window_label: str,
) -> list[dict[str, object]]:
    rows = []
    for date, row in summary.items():
        if row["beta"] is None:
            continue
        rows.append(
            {
                "date": date,
                "requirement": requirement,
                "check": f"beta_{window_label}_monitor",
                "status": "HARD_REVIEW" if row["hard_review"] else "WARN" if row["warning"] else "PASS",
                "observed": abs(float(row["beta"])),
                "threshold": 0.50 if window_label == "20d" else 0.40,
            }
        )
    return rows


def _drawdown_validation_rows_from_results(drawdown: dict[pd.Timestamp, object]) -> list[dict[str, object]]:
    rows = []
    for date, result in drawdown.items():
        rows.append(
            {
                "date": date,
                "requirement": "REQ-F-008",
                "check": "multi_tier_drawdown_halt",
                "status": "PASS" if result.tier == "NONE" else "WARN",
                "observed": result.rolling_60d_drawdown,
                "threshold": -0.10,
                "tier": result.tier,
            }
        )
    return rows


def _var_validation_rows_from_results(var_by_date: dict[pd.Timestamp, object]) -> list[dict[str, object]]:
    rows = []
    for date, result in var_by_date.items():
        for level, value in result.var.items():
            label = int(round(level * 100))
            rows.append(
                {
                    "date": date,
                    "requirement": "REQ-F-010",
                    "check": f"var_es_{label}",
                    "status": "WARN" if result.breach_flags.get(f"var_{label}", False) or result.breach_flags.get(f"es_{label}", False) else "PASS",
                    "observed": value,
                    "threshold": None,
                }
            )
    return rows


def _slippage_validation_rows(slippage: pd.DataFrame, date: pd.Timestamp) -> list[dict[str, object]]:
    rows = []
    for _, row in slippage.iterrows():
        residual = row["residual_bps"] if "residual_bps" in row.index else row["slippage_residual_bps"]
        rows.append(
            {
                "date": date,
                "requirement": "REQ-F-011",
                "check": "slippage_vs_square_root_impact",
                "status": row["status"],
                "observed": residual,
                "threshold": row["modeled_impact_bps"],
                "symbol": row["symbol"],
            }
        )
    return rows
