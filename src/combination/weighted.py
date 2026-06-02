"""Weighted multi-factor combiner."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.combination.base import BaseCombiner
from src.factors.utils import validate_multiindex_frame


class WeightedCombiner(BaseCombiner):
    """Combine standardized factors with explicit research weights."""

    name = "weighted"

    def __init__(self, weights: dict[str, float]) -> None:
        """Store normalized non-negative factor weights."""
        if not weights:
            raise ValueError("weights must not be empty.")
        clean_weights = {name: float(value) for name, value in weights.items()}
        if any(value < 0.0 or pd.isna(value) for value in clean_weights.values()):
            raise ValueError("weights must be non-negative finite numbers.")
        total_weight = sum(clean_weights.values())
        if total_weight <= 0.0:
            raise ValueError("weights must sum to a positive value.")
        self.weights = {name: value / total_weight for name, value in clean_weights.items()}

    def combine(self, factors: pd.DataFrame) -> pd.DataFrame:
        """Compute a weighted average and re-zscore the composite by date."""
        _validate_input(factors, self.weights)
        ordered_weights = pd.Series(self.weights, dtype=float).reindex(factors.columns)
        weighted_values = factors.replace([np.inf, -np.inf], np.nan).mul(ordered_weights, axis=1)
        raw_composite = weighted_values.sum(axis=1, min_count=1).rename("composite_alpha_weighted")
        composite_frame = raw_composite.to_frame()
        standardized = composite_frame.groupby(level="date", group_keys=False).apply(_zscore_daily)
        assert standardized.index.equals(composite_frame.index)
        return standardized.sort_index()


def _validate_input(factors: pd.DataFrame, weights: dict[str, float]) -> None:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame.")
    validate_multiindex_frame(factors, "factors")
    missing_names = sorted(set(weights) - set(factors.columns))
    if missing_names:
        raise ValueError(f"weights reference missing factor columns: {missing_names}")
    if factors.index.has_duplicates:
        raise ValueError("factors index contains duplicate (date, ticker) rows.")


def _zscore_daily(daily_frame: pd.DataFrame) -> pd.DataFrame:
    column_name = daily_frame.columns[0]
    values = daily_frame[column_name].astype(float)
    mean_value = values.mean(skipna=True)
    std_value = values.std(skipna=True, ddof=0)
    if pd.isna(std_value) or std_value == 0.0:
        return pd.DataFrame({column_name: np.nan}, index=daily_frame.index)
    return pd.DataFrame({column_name: (values - mean_value) / std_value}, index=daily_frame.index)
