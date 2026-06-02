"""Tools for combining multiple alpha factors into portfolio signals."""

from src.combination.baseline import (
    BaselineBacktestResult,
    FactorSpec,
    build_factor_correlation_report,
    build_sign_adjusted_panel,
)
from src.combination.equal_weight import EqualWeightCombiner
from src.combination.weighted import WeightedCombiner

__all__ = [
    "BaselineBacktestResult",
    "EqualWeightCombiner",
    "FactorSpec",
    "WeightedCombiner",
    "build_factor_correlation_report",
    "build_sign_adjusted_panel",
]
