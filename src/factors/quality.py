"""Quality factor implementations."""

from __future__ import annotations

import pandas as pd

from src.factors.base import BaseFactor
from src.factors.utils import divide_panel, get_panel


class ROE(BaseFactor):
    """Return-on-equity quality factor inspired by classic DuPont analysis."""

    name = "roe"
    category = "quality"
    reference = "Fama and French (2015), A Five-Factor Asset Pricing Model."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute net income divided by book value."""
        net_income = get_panel(data, "net_income")  # 中文：净利润衡量股东权益带来的收益。
        book_value = get_panel(data, "book_value")  # 中文：权益账面价值来自 PIT 财报。
        factor = divide_panel(net_income, book_value, self.name)  # 中文：ROE 越高，盈利质量通常越好。
        return factor


class GrossProfitability(BaseFactor):
    """Gross profitability factor from Novy-Marx (2013)."""

    name = "gross_profitability"
    category = "quality"
    reference = "Novy-Marx (2013), The Other Side of Value: The Gross Profitability Premium."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute gross profit divided by total assets."""
        gross_profit = get_panel(data, "gross_profit")  # 中文：若 Pillar 1 没有该字段，结果应保持 NaN。
        total_assets = get_panel(data, "total_assets")  # 中文：用资产规模归一化，便于公司间比较。
        factor = divide_panel(gross_profit, total_assets, self.name)  # 中文：单位资产毛利越高，经营质量越好。
        return factor


class Accruals(BaseFactor):
    """Accruals quality factor from Sloan (1996), with sign reversed."""

    name = "accruals"
    category = "quality"
    reference = "Sloan (1996), Do Stock Prices Fully Reflect Information in Accruals and Cash Flows?"

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative accruals divided by total assets."""
        net_income = get_panel(data, "net_income")  # 中文：净利润包含现金和非现金会计项目。
        operating_cashflow = get_panel(data, "operating_cashflow")  # 中文：经营现金流缺失时不应臆造。
        total_assets = get_panel(data, "total_assets")  # 中文：资产规模用于横向归一化。
        accrual_amount = net_income - operating_cashflow  # 中文：利润减现金流代表应计项目。
        factor = divide_panel(-1.0 * accrual_amount, total_assets, self.name)  # 中文：应计越低越好，所以取负号。
        return factor
