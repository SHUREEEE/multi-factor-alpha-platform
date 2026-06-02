"""Size factor implementations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base import BaseFactor
from src.factors.utils import get_panel, single_column_frame


class LogMarketCap(BaseFactor):
    """Size factor from Banz (1981), with sign reversed."""

    name = "log_market_cap"
    category = "size"
    reference = "Banz (1981), The Relationship Between Return and Market Value of Common Stocks."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative log market capitalization."""
        market_cap = get_panel(data, "market_cap")  # 中文：市值越小，size premium 理论得分越高。
        factor_values = -1.0 * np.log(market_cap.where(market_cap > 0))  # 中文：只对正数取 log，避免数学错误。
        return single_column_frame(factor_values, self.name)


class LogTotalAssets(BaseFactor):
    """Asset-size factor using total assets, with sign reversed."""

    name = "log_total_assets"
    category = "size"
    reference = "Fama and French (2015), A Five-Factor Asset Pricing Model."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative log total assets."""
        total_assets = get_panel(data, "total_assets")  # 中文：资产规模是公司规模的基本面代理。
        factor_values = -1.0 * np.log(total_assets.where(total_assets > 0))  # 中文：负号让小资产公司得分更高。
        return single_column_frame(factor_values, self.name)


class LogRevenue(BaseFactor):
    """Revenue-size factor using total revenue, with sign reversed."""

    name = "log_revenue"
    category = "size"
    reference = "Berk (1995), A Critique of Size-Related Anomalies."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative log revenue."""
        revenue = get_panel(data, "revenue")  # 中文：收入规模可作为公司规模的经营代理。
        factor_values = -1.0 * np.log(revenue.where(revenue > 0))  # 中文：负号确保收入越小分数越高。
        return single_column_frame(factor_values, self.name)
