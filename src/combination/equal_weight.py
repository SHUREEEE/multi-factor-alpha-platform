"""Equal-weight multi-factor combiner."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.combination.base import BaseCombiner
from src.factors.utils import validate_multiindex_frame


class EqualWeightCombiner(BaseCombiner):
    """Combine standardized factors with a simple equal-weight average."""

    name = "equal_weight"

    def combine(self, factors: pd.DataFrame) -> pd.DataFrame:
        """Average factor columns and re-zscore the composite by date.

        Parameters
        ----------
        factors:
            Sign-adjusted standardized factor panel indexed by ``(date, ticker)``.

        Returns
        -------
        pandas.DataFrame
            Single-column composite alpha signal.
        """
        _validate_input(factors)
        raw_composite = factors.replace([np.inf, -np.inf], np.nan).mean(axis=1, skipna=True)
        composite_frame = raw_composite.to_frame("composite_alpha_equal_weight")
        standardized = composite_frame.groupby(level="date", group_keys=False).apply(_zscore_daily)
        assert standardized.index.equals(composite_frame.index)
        return standardized.sort_index()


def _validate_input(factors: pd.DataFrame) -> None:
    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a pandas DataFrame.")
    validate_multiindex_frame(factors, "factors")
    if factors.shape[1] < 2:
        raise ValueError("equal-weight combination needs at least two factors.")
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
