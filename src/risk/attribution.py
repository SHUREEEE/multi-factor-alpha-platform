"""Factor return attribution and risk decomposition helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_factor_exposure(weights: pd.DataFrame, factor_exposures: dict) -> pd.DataFrame:
    """Portfolio factor exposure = sum(w_i * exposure_i) per date."""
    if not isinstance(weights, pd.DataFrame):
        raise TypeError("weights must be a pandas DataFrame.")
    if not factor_exposures:
        return pd.DataFrame(index=weights.index)

    clean_weights = weights.astype(float).sort_index()
    exposure_rows = {}
    for factor_name, exposure_panel in factor_exposures.items():
        if not isinstance(exposure_panel, pd.DataFrame):
            raise TypeError(f"factor_exposures[{factor_name!r}] must be a pandas DataFrame.")
        aligned_weights, aligned_exposures = clean_weights.align(exposure_panel.astype(float), join="inner", axis=0)
        aligned_weights, aligned_exposures = aligned_weights.align(aligned_exposures, join="inner", axis=1)
        exposure_rows[factor_name] = aligned_weights.fillna(0.0).mul(aligned_exposures).sum(axis=1, min_count=1)

    exposures = pd.DataFrame(exposure_rows).reindex(clean_weights.index)
    exposures.index.name = weights.index.name
    return exposures


def decompose_portfolio_return(
    weights: pd.DataFrame,
    factor_exposures: dict,
    factor_returns: pd.DataFrame,
    stock_returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Decompose realized portfolio return into factor contribution and pure alpha.

    Uses the Pillar 6 convention: weights decided at t-1 earn stock returns at t.
    """
    if not isinstance(factor_returns, pd.DataFrame):
        raise TypeError("factor_returns must be a pandas DataFrame.")
    if not isinstance(stock_returns, pd.DataFrame):
        raise TypeError("stock_returns must be a pandas DataFrame.")

    shifted_weights = weights.astype(float).sort_index().shift(1)
    aligned_weights, aligned_returns = shifted_weights.align(stock_returns.astype(float), join="inner", axis=0)
    aligned_weights, aligned_returns = aligned_weights.align(aligned_returns, join="inner", axis=1)
    total = aligned_weights.fillna(0.0).mul(aligned_returns.fillna(0.0)).sum(axis=1).rename("total")

    aligned_factor_exposures = {
        name: panel.reindex(index=aligned_weights.index, columns=aligned_weights.columns)
        for name, panel in factor_exposures.items()
    }
    portfolio_exposures = compute_factor_exposure(aligned_weights, aligned_factor_exposures)
    common_factors = [factor for factor in portfolio_exposures.columns if factor in factor_returns.columns]
    aligned_factor_returns = factor_returns.astype(float).reindex(index=total.index, columns=common_factors)

    output = pd.DataFrame(index=total.index)
    for factor in common_factors:
        output[f"{factor}_contrib"] = portfolio_exposures[factor] * aligned_factor_returns[factor]

    factor_total = output.sum(axis=1) if not output.empty else pd.Series(0.0, index=total.index)
    output["pure_alpha"] = total - factor_total
    output["total"] = total
    output.index.name = stock_returns.index.name
    return output


def risk_decomposition(
    weights: pd.Series,
    factor_exposures: dict,
    factor_cov: pd.DataFrame,
    idio_var: pd.Series,
) -> dict:
    """Decompose one-date portfolio variance into factor and idiosyncratic risk."""
    if not isinstance(weights, pd.Series):
        raise TypeError("weights must be a pandas Series.")
    if not isinstance(factor_cov, pd.DataFrame):
        raise TypeError("factor_cov must be a pandas DataFrame.")
    if not isinstance(idio_var, pd.Series):
        raise TypeError("idio_var must be a pandas Series.")

    clean_weights = weights.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    factor_names = [factor for factor in factor_cov.index if factor in factor_cov.columns and factor in factor_exposures]
    portfolio_exposures = pd.Series(index=factor_names, dtype=float)
    for factor in factor_names:
        exposure = pd.Series(factor_exposures[factor], dtype=float).reindex(clean_weights.index)
        portfolio_exposures.loc[factor] = float(clean_weights.mul(exposure).sum())

    cov = factor_cov.reindex(index=factor_names, columns=factor_names).astype(float).fillna(0.0)
    exposure_values = portfolio_exposures.fillna(0.0).to_numpy(dtype=float)
    factor_variance = float(exposure_values @ cov.to_numpy(dtype=float) @ exposure_values)

    aligned_idio_var = idio_var.astype(float).reindex(clean_weights.index).fillna(0.0)
    idiosyncratic_variance = float(clean_weights.pow(2.0).mul(aligned_idio_var).sum())
    total_variance = factor_variance + idiosyncratic_variance
    factor_pct = factor_variance / total_variance if total_variance != 0.0 else np.nan
    idio_pct = idiosyncratic_variance / total_variance if total_variance != 0.0 else np.nan

    diagonal = pd.Series(np.diag(cov), index=factor_names, dtype=float)
    per_factor_variance = portfolio_exposures.pow(2.0).mul(diagonal).to_dict()
    return {
        "factor_variance": factor_variance,
        "idiosyncratic_variance": idiosyncratic_variance,
        "total_variance": total_variance,
        "factor_pct": float(factor_pct),
        "idio_pct": float(idio_pct),
        "per_factor_variance": {key: float(value) for key, value in per_factor_variance.items()},
    }


def summarize_attribution(decomp: pd.DataFrame) -> dict:
    """Return aggregate contribution totals from a decomposition DataFrame."""
    if not isinstance(decomp, pd.DataFrame):
        raise TypeError("decomp must be a pandas DataFrame.")
    if "total" not in decomp.columns or "pure_alpha" not in decomp.columns:
        raise ValueError("decomp must contain total and pure_alpha columns.")

    contribution_columns = [column for column in decomp.columns if column.endswith("_contrib")]
    breakdown = {
        column.removesuffix("_contrib"): float(decomp[column].fillna(0.0).sum())
        for column in contribution_columns
    }
    factor_contribution_total = float(sum(breakdown.values()))
    transaction_cost_total = float(decomp["transaction_cost"].fillna(0.0).sum()) if "transaction_cost" in decomp.columns else 0.0
    pure_alpha_total = float(decomp["pure_alpha"].fillna(0.0).sum())
    pure_alpha_gross_total = (
        float(decomp["gross_pure_alpha"].fillna(0.0).sum())
        if "gross_pure_alpha" in decomp.columns
        else pure_alpha_total - transaction_cost_total
    )
    total_return = float(decomp["total"].fillna(0.0).sum())
    gross_total_return = float(decomp["gross_total"].fillna(0.0).sum()) if "gross_total" in decomp.columns else total_return
    pure_alpha_pct = pure_alpha_total / total_return if total_return != 0.0 else np.nan
    return {
        "total_return": total_return,
        "gross_total_return": gross_total_return,
        "factor_contribution_total": factor_contribution_total,
        "pure_alpha_total": pure_alpha_total,
        "pure_alpha_gross_total": pure_alpha_gross_total,
        "transaction_cost_total": transaction_cost_total,
        "pure_alpha_pct_of_total": float(pure_alpha_pct),
        "factor_contribution_breakdown": breakdown,
    }
