"""Base interface for all style factors."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseFactor(ABC):
    """Abstract base class shared by every factor implementation.

    Notes
    -----
    Every factor returns a single-column DataFrame indexed by ``(date, ticker)``.
    Trading code must shift the final factor signal by one trading day before
    using it for orders, because same-day close data is not known before close.
    """

    name: str
    category: str
    reference: str

    @abstractmethod
    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute one raw factor before preprocessing.

        Parameters
        ----------
        data:
            Dictionary containing input panels such as prices, fundamentals,
            market cap, industry labels, or market returns.

        Returns
        -------
        pandas.DataFrame
            Single-column factor frame indexed by MultiIndex ``(date, ticker)``.
        """
