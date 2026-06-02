"""Momentum factor implementations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.base import BaseFactor
from src.factors.utils import get_prices, single_column_frame, stack_wide_panel


class Momentum12_1(BaseFactor):
    """Twelve-minus-one momentum from Jegadeesh and Titman (1993)."""

    name = "momentum_12_1"
    category = "momentum"
    reference = "Jegadeesh and Titman (1993), Returns to Buying Winners and Selling Losers."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute 12-month return while skipping the most recent month."""
        prices = get_prices(data)  # 中文：动量使用复权价，避免分红拆股造成虚假收益。
        adj_close = prices["adj_close"].unstack("ticker")  # 中文：宽表让 pct_change 按股票列计算。
        momentum = adj_close.pct_change(252).shift(21)  # 中文：回看 252 日，并跳过最近 21 日反转期。
        return single_column_frame(stack_wide_panel(momentum), self.name)  # 中文：转回 MultiIndex 供后续统一处理。


class ShortTermReversal(BaseFactor):
    """Short-term reversal factor from Jegadeesh (1990)."""

    name = "short_term_reversal"
    category = "momentum"
    reference = "Jegadeesh (1990), Evidence of Predictable Behavior of Security Returns."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative past one-month return."""
        prices = get_prices(data)  # 中文：短期反转同样基于复权价收益。
        adj_close = prices["adj_close"].unstack("ticker")  # 中文：每个 ticker 独立计算过去收益。
        one_month_return = adj_close.pct_change(21)  # 中文：21 个交易日近似一个交易月。
        reversal = -1.0 * one_month_return  # 中文：过去跌得多的股票在反转因子中得分更高。
        return single_column_frame(stack_wide_panel(reversal), self.name)


class Week52High(BaseFactor):
    """52-week high factor from George and Hwang (2004)."""

    name = "week_52_high"
    category = "momentum"
    reference = "George and Hwang (2004), The 52-Week High and Momentum Investing."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute current adjusted close divided by rolling 52-week high."""
        prices = get_prices(data)  # 中文：使用复权价保证历史高点口径一致。
        adj_close = prices["adj_close"].unstack("ticker")  # 中文：宽表 rolling 会按列独立滚动。
        rolling_high = adj_close.rolling(window=252, min_periods=126).max()  # 中文：至少半年数据才认为高点可靠。
        factor_values = adj_close / rolling_high  # 中文：越接近 52 周高点，动量得分越高。
        factor_values = factor_values.replace([np.inf, -np.inf], np.nan)  # 中文：防止除以异常高点产生无穷值。
        return single_column_frame(stack_wide_panel(factor_values), self.name)
