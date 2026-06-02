"""V4 optimization primitives.

D2 uses a cvxpy convex program when available, with the earlier deterministic
sector projection retained as a conservative fallback. Borrow, regime sizing,
and other V4 controls are intentionally handled in separate modules.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

try:  # pragma: no cover - exercised through solver behavior, not import branch.
    import cvxpy as cp
except Exception:  # pragma: no cover
    cp = None


def build_sector_net_constraints(
    symbols: Iterable[str],
    sectors: pd.Series,
    sector_net_cap: float | None = None,
) -> pd.DataFrame:
    """Build a sector one-hot matrix for signed net exposure constraints."""
    if sector_net_cap is not None and sector_net_cap < 0.0:
        raise ValueError("sector_net_cap must be non-negative.")
    symbol_index = pd.Index(list(symbols), name="symbol")
    sector_labels = sectors.reindex(symbol_index).fillna("Unknown").astype(str)
    matrix = pd.get_dummies(sector_labels).T.astype(float)
    matrix.columns = symbol_index
    matrix.index.name = "sector"
    return matrix


def solve_turnover_aware_weights(
    raw_weights: pd.Series,
    prior_weights: pd.Series,
    betas: pd.Series,
    sectors: pd.Series,
    *,
    sector_net_cap: float,
    gross_target: float,
    turnover_penalty: float,
    no_trade_band_bps: float,
    short_top10_cap: float,
    single_short_cap: float,
) -> pd.Series:
    """Return turnover-aware weights after the implemented risk constraints.

    C4 uses a no-trade band followed by a turnover penalty blend, then applies
    the C3 sector-net constraint. Beta, short concentration, and borrow inputs
    are accepted to keep the public signature stable for later workflows.
    """
    del short_top10_cap, single_short_cap
    if turnover_penalty < 0.0:
        raise ValueError("turnover_penalty must be non-negative.")
    if no_trade_band_bps < 0.0:
        raise ValueError("no_trade_band_bps must be non-negative.")

    raw, prior, beta = _prepare_solver_inputs(raw_weights, prior_weights, betas, gross_target)
    solved = _solve_cvxpy_qp(raw, prior, beta, sectors, sector_net_cap, gross_target, turnover_penalty)
    solver_path = "cvxpy"
    if solved is None:
        solver_path = "projection"
        raw_share = 1.0 / (1.0 + float(turnover_penalty))
        solved = solve_sector_net_weights(prior * (1.0 - raw_share) + raw * raw_share, sectors, sector_net_cap=sector_net_cap, gross_target=gross_target)
    output = _apply_no_trade_band(solved, raw, prior, sectors, sector_net_cap, gross_target, no_trade_band_bps)
    output.attrs["solver_path"] = solver_path
    return output


def solve_sector_net_weights(
    raw_weights: pd.Series,
    sectors: pd.Series,
    *,
    sector_net_cap: float,
    gross_target: float = 2.0,
) -> pd.Series:
    """Return weights with signed sector net exposure constrained by cap.

    The solver works at sector allocation level, then redistributes each
    sector's long and short allocations back to active names in proportion to
    the raw book. It preserves long/short side gross and does not introduce new
    active names.
    """
    if not 0.0 <= sector_net_cap:
        raise ValueError("sector_net_cap must be non-negative.")
    if gross_target <= 0.0:
        raise ValueError("gross_target must be positive.")

    clean = raw_weights.fillna(0.0).astype(float)
    if clean.empty or clean.abs().sum() == 0.0:
        return clean

    side_total = float(gross_target) / 2.0
    base = _normalize_to_side_gross(clean, side_total)
    sector_labels = sectors.reindex(base.index).fillna("Unknown").astype(str)

    long_by_sector = base.where(base > 0.0, 0.0).groupby(sector_labels).sum()
    short_by_sector = (-base.where(base < 0.0, 0.0)).groupby(sector_labels).sum()
    all_sectors = long_by_sector.index.union(short_by_sector.index)
    long_by_sector = long_by_sector.reindex(all_sectors, fill_value=0.0)
    short_by_sector = short_by_sector.reindex(all_sectors, fill_value=0.0)

    raw_net = long_by_sector - short_by_sector
    desired_net = _project_zero_sum_box(raw_net, sector_net_cap)
    target_long, target_short = _sector_side_allocations(desired_net, long_by_sector, short_by_sector, side_total)

    return _distribute_sector_allocations(base, sector_labels, target_long, target_short)


def sector_net_exposure(weights: pd.Series, sectors: pd.Series) -> pd.Series:
    """Compute signed sector net exposure for one date of weights."""
    clean = weights.fillna(0.0).astype(float)
    sector_labels = sectors.reindex(clean.index).fillna("Unknown").astype(str)
    return clean.groupby(sector_labels).sum().rename("sector_net")


def _normalize_to_side_gross(weights: pd.Series, side_total: float) -> pd.Series:
    long = weights.where(weights > 0.0, 0.0)
    short = -weights.where(weights < 0.0, 0.0)
    long_sum = float(long.sum())
    short_sum = float(short.sum())
    if long_sum <= 0.0 or short_sum <= 0.0:
        raise ValueError("raw_weights must include both long and short exposure.")
    return long / long_sum * side_total - short / short_sum * side_total


def _prepare_solver_inputs(
    raw_weights: pd.Series,
    prior_weights: pd.Series,
    betas: pd.Series,
    gross_target: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    side_total = float(gross_target) / 2.0
    raw = _normalize_to_side_gross(raw_weights.fillna(0.0).astype(float), side_total)
    prior = prior_weights.reindex(raw.index).fillna(0.0).astype(float)
    if prior.abs().sum() > 0.0:
        prior = _normalize_to_side_gross(prior, side_total)
    else:
        prior = raw.copy()
    beta = betas.reindex(raw.index).fillna(0.0).astype(float)
    return raw, prior, beta


def _solve_cvxpy_qp(
    raw: pd.Series,
    prior: pd.Series,
    betas: pd.Series,
    sectors: pd.Series,
    sector_net_cap: float,
    gross_target: float,
    turnover_penalty: float,
) -> pd.Series | None:
    if cp is None:
        return None
    n = len(raw)
    x_long = cp.Variable(n, nonneg=True)
    x_short = cp.Variable(n, nonneg=True)
    x = x_long - x_short
    raw_values = raw.to_numpy(dtype=float)
    prior_values = prior.to_numpy(dtype=float)
    beta_values = betas.to_numpy(dtype=float)
    sector_matrix = build_sector_net_constraints(raw.index, sectors).to_numpy(dtype=float)
    side_total = float(gross_target) / 2.0
    objective = cp.sum_squares(x - raw_values) + float(turnover_penalty) * cp.norm1(x - prior_values) + 10.0 * cp.square(beta_values @ x)
    constraints = [
        cp.sum(x_long) == side_total,
        cp.sum(x_short) == side_total,
        x_long <= side_total,
        x_short <= side_total,
        sector_matrix @ x <= float(sector_net_cap),
        sector_matrix @ x >= -float(sector_net_cap),
    ]
    problem = cp.Problem(cp.Minimize(objective), constraints)
    for solver in ("CLARABEL", "OSQP", "SCS"):
        try:
            problem.solve(solver=solver, verbose=False)
        except Exception:
            continue
        if problem.status in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} and x.value is not None:
            return pd.Series(np.asarray(x.value, dtype=float), index=raw.index).where(lambda s: s.abs() > 1e-12, 0.0)
    return None


def _apply_no_trade_band(
    solved: pd.Series,
    raw: pd.Series,
    prior: pd.Series,
    sectors: pd.Series,
    sector_net_cap: float,
    gross_target: float,
    no_trade_band_bps: float,
) -> pd.Series:
    band = float(no_trade_band_bps) / 10000.0
    if band <= 0.0:
        return solved
    candidate = solved.copy()
    tiny_names = raw.index[(raw - prior).abs() < band]
    if len(tiny_names) == 0:
        return solved
    candidate.loc[tiny_names] = prior.loc[tiny_names]
    try:
        candidate = solve_sector_net_weights(candidate, sectors, sector_net_cap=sector_net_cap, gross_target=gross_target)
    except ValueError:
        return solved
    if sector_net_exposure(candidate, sectors).abs().max() <= sector_net_cap + 1e-10:
        return candidate
    return solved


def _project_zero_sum_box(values: pd.Series, cap: float) -> pd.Series:
    projected = values.astype(float).clip(lower=-cap, upper=cap)
    for _ in range(len(projected) + 1):
        residual = float(projected.sum())
        if abs(residual) < 1e-12:
            break
        if residual > 0.0:
            room = projected + cap
            active = room > 1e-12
            if not active.any():
                break
            decrement = min(residual, float(room[active].sum()))
            projected.loc[active] -= decrement * room[active] / float(room[active].sum())
        else:
            room = cap - projected
            active = room > 1e-12
            if not active.any():
                break
            increment = min(-residual, float(room[active].sum()))
            projected.loc[active] += increment * room[active] / float(room[active].sum())
    if abs(float(projected.sum())) > 1e-9:
        raise ValueError("sector_net_cap is infeasible for zero-sum sector exposure.")
    return projected


def _sector_side_allocations(
    desired_net: pd.Series,
    raw_long: pd.Series,
    raw_short: pd.Series,
    side_total: float,
) -> tuple[pd.Series, pd.Series]:
    positive_net = desired_net.clip(lower=0.0)
    negative_net = (-desired_net).clip(lower=0.0)
    common_total = side_total - float(positive_net.sum())
    if common_total < -1e-10:
        raise ValueError("projected sector net requires more side gross than available.")
    common_total = max(common_total, 0.0)

    common_base = pd.concat([raw_long, raw_short], axis=1).min(axis=1).clip(lower=0.0)
    if float(common_base.sum()) <= 0.0:
        common_base = (raw_long + raw_short).clip(lower=0.0)
    if float(common_base.sum()) <= 0.0:
        common = pd.Series(0.0, index=desired_net.index)
    else:
        common = common_base / float(common_base.sum()) * common_total

    target_long = positive_net + common
    target_short = negative_net + common
    return target_long, target_short


def _distribute_sector_allocations(
    base: pd.Series,
    sector_labels: pd.Series,
    target_long: pd.Series,
    target_short: pd.Series,
) -> pd.Series:
    result = pd.Series(0.0, index=base.index, dtype=float)
    for sector in target_long.index:
        names = sector_labels[sector_labels == sector].index
        long_names = names[base.reindex(names).fillna(0.0) > 0.0]
        short_names = names[base.reindex(names).fillna(0.0) < 0.0]

        long_target = float(target_long.loc[sector])
        short_target = float(target_short.loc[sector])
        if long_target > 1e-12:
            if len(long_names) == 0:
                raise ValueError(f"sector {sector} has no long names for required allocation.")
            raw_long = base.loc[long_names].clip(lower=0.0)
            result.loc[long_names] = raw_long / float(raw_long.sum()) * long_target
        if short_target > 1e-12:
            if len(short_names) == 0:
                raise ValueError(f"sector {sector} has no short names for required allocation.")
            raw_short = (-base.loc[short_names]).clip(lower=0.0)
            result.loc[short_names] = -raw_short / float(raw_short.sum()) * short_target
    return result.replace([np.inf, -np.inf], np.nan)
