"""Value factor implementations."""

from __future__ import annotations

import pandas as pd

from src.factors.base import BaseFactor
from src.factors.utils import divide_panel, get_panel


class BookToMarket(BaseFactor):
    """Book-to-market factor from Fama and French (1992)."""

    name = "book_to_market"
    category = "value"
    reference = "Fama and French (1992), The Cross-Section of Expected Stock Returns."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute book value divided by market capitalization."""
        book_value = get_panel(data, "book_value")  # 中文：账面价值来自 PIT 财报，避免使用未来财报。
        market_cap = get_panel(data, "market_cap")  # 中文：市值是分母，缺失时不能用价格伪造。
        factor = divide_panel(book_value, market_cap, self.name)  # 中文：统一除法会处理 0 和无穷值。
        return factor


class EarningsYield(BaseFactor):
    """Earnings yield factor from Basu (1977)."""

    name = "earnings_yield"
    category = "value"
    reference = "Basu (1977), Investment Performance of Common Stocks in Relation to Their P/E Ratios."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute net income divided by market capitalization."""
        net_income = get_panel(data, "net_income")  # 中文：利润必须使用已可得的 PIT 数据。
        market_cap = get_panel(data, "market_cap")  # 中文：用市值归一化，方便不同公司横向比较。
        factor = divide_panel(net_income, market_cap, self.name)  # 中文：盈利收益率越高，估值越便宜。
        return factor


class SalesToPrice(BaseFactor):
    """Sales-to-price value factor commonly used in cross-sectional equity models."""

    name = "sales_to_price"
    category = "value"
    reference = "Lakonishok, Shleifer, and Vishny (1994), Contrarian Investment, Extrapolation, and Risk."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute revenue divided by market capitalization."""
        revenue = get_panel(data, "revenue")  # 中文：收入比利润更稳定，但仍需 PIT 对齐。
        market_cap = get_panel(data, "market_cap")  # 中文：市值缺失时返回 NaN，避免错误替代。
        factor = divide_panel(revenue, market_cap, self.name)  # 中文：销售市值比越高，估值通常越低。
        return factor
