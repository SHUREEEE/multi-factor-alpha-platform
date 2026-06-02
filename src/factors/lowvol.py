"""Low-volatility factor implementations."""

from __future__ import annotations

import pandas as pd

from src.factors.base import BaseFactor
from src.factors.utils import get_market_returns, get_returns, single_column_frame, stack_wide_panel


class IdiosyncraticVol(BaseFactor):
    """Idiosyncratic volatility factor from Ang et al. (2006)."""

    name = "idiosyncratic_vol"
    category = "lowvol"
    reference = "Ang, Hodrick, Xing, and Zhang (2006), The Cross-Section of Volatility and Expected Returns."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative CAPM residual volatility over a 60-day window."""
        returns = get_returns(data)  # 中文：使用日收益做 CAPM 回归输入。
        market_returns = get_market_returns(data, returns)  # 中文：优先用外部市场收益，否则用股票池等权收益。
        volatility = _rolling_residual_volatility(returns, market_returns)  # 中文：向量化 rolling covariance 比逐股票循环快很多。
        factor_values = -1.0 * volatility  # 中文：低特异波动应得高分，所以对波动率取负。
        return single_column_frame(stack_wide_panel(factor_values), self.name)


class BetaInverse(BaseFactor):
    """Betting-against-beta style factor from Frazzini and Pedersen (2014)."""

    name = "beta_inverse"
    category = "lowvol"
    reference = "Frazzini and Pedersen (2014), Betting Against Beta."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative rolling CAPM beta over a 60-day window."""
        returns = get_returns(data)  # 中文：个股收益是 CAPM 左侧变量。
        market_returns = get_market_returns(data, returns)  # 中文：市场收益是 CAPM 右侧变量。
        beta = _rolling_beta(returns, market_returns)  # 中文：beta = cov(stock, market) / var(market)。
        factor_values = -1.0 * beta  # 中文：低 beta 股票得分更高，符合 defensive factor 方向。
        return single_column_frame(stack_wide_panel(factor_values), self.name)


class RealizedVol(BaseFactor):
    """Realized volatility factor using past 60 trading days of returns."""

    name = "realized_vol"
    category = "lowvol"
    reference = "Blitz and van Vliet (2007), The Volatility Effect."

    def compute(self, data: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame:
        """Compute negative rolling 60-day standard deviation of returns."""
        returns = get_returns(data)  # 中文：波动率必须从收益率而不是价格水平计算。
        realized_vol = returns.rolling(window=60, min_periods=40).std()  # 中文：允许少量缺口，但样本太少则不给信号。
        factor_values = -1.0 * realized_vol  # 中文：低波动股票得分更高，所以取负号。
        return single_column_frame(stack_wide_panel(factor_values), self.name)


def _rolling_beta(returns: pd.DataFrame, market_returns: pd.Series) -> pd.DataFrame:
    """Estimate rolling CAPM beta for all stocks at once."""
    market_variance = market_returns.rolling(window=60, min_periods=40).var()  # 中文：市场方差是所有股票共用的 beta 分母。
    covariance = returns.rolling(window=60, min_periods=40).cov(market_returns)  # 中文：每列分别与市场收益算滚动协方差。
    beta = covariance.div(market_variance, axis=0)  # 中文：按日期对齐分母，得到每只股票的 rolling beta。
    return beta.where(market_variance > 0)


def _rolling_residual_volatility(returns: pd.DataFrame, market_returns: pd.Series) -> pd.DataFrame:
    """Estimate rolling CAPM residual volatility for all stocks at once."""
    stock_variance = returns.rolling(window=60, min_periods=40).var()  # 中文：个股总方差包含市场和特异两部分。
    market_variance = market_returns.rolling(window=60, min_periods=40).var()  # 中文：市场无波动时 CAPM 分解不可靠。
    covariance = returns.rolling(window=60, min_periods=40).cov(market_returns)  # 中文：协方差衡量股票与市场共同波动。
    beta = covariance.div(market_variance, axis=0)  # 中文：先估计 beta，才能扣掉市场解释的方差。
    residual_variance = stock_variance - beta * covariance  # 中文：OLS 残差方差等于总方差减去市场解释方差。
    residual_variance = residual_variance.clip(lower=0.0)  # 中文：浮点误差可能产生极小负数，需截到 0。
    return residual_variance.pow(0.5).where(market_variance > 0)
