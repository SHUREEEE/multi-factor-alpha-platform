"""Abstract base classes for factor combination."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseCombiner(ABC):
    """Abstract interface shared by all multi-factor combiners.

    Notes
    -----
    Inputs are expected to be point-in-time factor panels indexed by
    ``(date, ticker)``. Portfolio code must still shift the final composite
    signal by one trading day before turning it into holdings.
    """

    name: str

    @abstractmethod
    def combine(self, factors: pd.DataFrame) -> pd.DataFrame:
        """Combine multiple factors into one composite alpha signal.

        Parameters
        ----------
        factors:
            Multi-column factor panel indexed by ``(date, ticker)``.

        Returns
        -------
        pandas.DataFrame
            Single-column composite signal indexed by ``(date, ticker)``.
        """
