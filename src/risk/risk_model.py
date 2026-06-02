"""Barra-style cross-sectional risk model."""

from __future__ import annotations

import numpy as np
import pandas as pd


class BarraStyleRiskModel:
    """Estimate daily factor returns and idiosyncratic residual risk."""

    def __init__(
        self,
        factor_names: list[str],
        use_sqrt_mcap_weight: bool = True,
        ridge_lambda: float = 1e-6,
    ):
        if not factor_names:
            raise ValueError("factor_names must contain at least one factor.")
        if ridge_lambda < 0.0:
            raise ValueError("ridge_lambda must be non-negative.")
        self.factor_names = list(factor_names)
        self.use_sqrt_mcap_weight = bool(use_sqrt_mcap_weight)
        self.ridge_lambda = float(ridge_lambda)
        self.factor_returns_: pd.DataFrame | None = None
        self.residuals_: pd.DataFrame | None = None

    def fit(
        self,
        returns: pd.DataFrame,
        factor_exposures: dict,
        market_caps: pd.DataFrame,
        industry_dummies: pd.DataFrame = None,
    ) -> "BarraStyleRiskModel":
        """
        Estimate cross-sectional factor returns date by date.

        ``returns``, every entry of ``factor_exposures``, and ``market_caps`` are
        expected to be T x N panels with dates on rows and tickers on columns.
        ``industry_dummies`` may be a date-indexed DataFrame with MultiIndex
        columns of (ticker, industry), or a stacked DataFrame indexed by
        (date, ticker) with industry dummy columns.
        """
        if not isinstance(returns, pd.DataFrame):
            raise TypeError("returns must be a pandas DataFrame.")
        if not isinstance(market_caps, pd.DataFrame):
            raise TypeError("market_caps must be a pandas DataFrame.")
        missing_factors = [name for name in self.factor_names if name not in factor_exposures]
        if missing_factors:
            raise ValueError(f"factor_exposures missing factors: {missing_factors}")

        returns_panel = returns.astype(float).sort_index()
        market_caps_panel = market_caps.astype(float).reindex_like(returns_panel)
        exposure_panels = {
            name: factor_exposures[name].astype(float).reindex_like(returns_panel)
            for name in self.factor_names
        }

        factor_return_rows: list[pd.Series] = []
        residual_rows: list[pd.Series] = []

        for date in returns_panel.index:
            y = returns_panel.loc[date].replace([np.inf, -np.inf], np.nan)
            caps = market_caps_panel.loc[date].replace([np.inf, -np.inf], np.nan)
            x = pd.DataFrame({name: exposure_panels[name].loc[date] for name in self.factor_names})
            x = x.replace([np.inf, -np.inf], np.nan)

            industry = self._industry_for_date(industry_dummies, date, returns_panel.columns)
            if industry is not None and not industry.empty:
                industry = industry.dropna(axis=1, how="all")
                if industry.shape[1] > 1:
                    industry = industry.iloc[:, 1:]
                elif industry.shape[1] == 1:
                    industry = industry.iloc[:, 0:0]
                x = pd.concat([x, industry], axis=1)

            regression_panel = pd.concat(
                [y.rename("__return__"), caps.rename("__market_cap__"), x],
                axis=1,
            ).dropna()
            regression_panel = regression_panel[regression_panel["__market_cap__"] > 0.0]
            if regression_panel.shape[0] < 30:
                continue

            y_values = regression_panel["__return__"].to_numpy(dtype=float)
            x_frame = regression_panel.drop(columns=["__return__", "__market_cap__"]).astype(float)
            x_values = x_frame.to_numpy(dtype=float)
            if self.use_sqrt_mcap_weight:
                weights = np.sqrt(regression_panel["__market_cap__"].to_numpy(dtype=float))
            else:
                weights = np.ones(regression_panel.shape[0], dtype=float)

            beta = self._weighted_ridge_fit(x_values, y_values, weights)
            factor_returns = pd.Series(beta, index=x_frame.columns, name=date)
            predicted = x_values @ beta
            residuals = pd.Series(np.nan, index=returns_panel.columns, name=date, dtype=float)
            residuals.loc[x_frame.index] = y_values - predicted

            factor_return_rows.append(factor_returns)
            residual_rows.append(residuals)

        self.factor_returns_ = pd.DataFrame(factor_return_rows)
        self.residuals_ = pd.DataFrame(residual_rows, columns=returns_panel.columns)
        if not self.factor_returns_.empty:
            self.factor_returns_.index.name = returns_panel.index.name
            self.residuals_.index.name = returns_panel.index.name
        return self

    @property
    def factor_returns_timeseries(self) -> pd.DataFrame:
        if self.factor_returns_ is None:
            raise ValueError("Model must be fit before accessing factor returns.")
        return self.factor_returns_.copy()

    @property
    def idiosyncratic_volatility(self) -> pd.Series:
        """Per-stock residual std with Bayesian shrinkage for short histories."""
        if self.residuals_ is None:
            raise ValueError("Model must be fit before accessing idiosyncratic volatility.")
        residuals = self.residuals_.replace([np.inf, -np.inf], np.nan)
        counts = residuals.count()
        sample_var = residuals.var(axis=0, ddof=1)
        fallback_var = residuals.var(axis=0, ddof=0)
        sample_var = sample_var.where(counts > 1, fallback_var)
        prior_var = float(sample_var.dropna().mean()) if not sample_var.dropna().empty else np.nan
        n0 = 20.0
        shrunk_var = sample_var.copy()
        short_history = counts < 60
        shrunk_var.loc[short_history] = (
            counts.loc[short_history] * sample_var.loc[short_history] + n0 * prior_var
        ) / (counts.loc[short_history] + n0)
        return np.sqrt(shrunk_var).rename("idiosyncratic_volatility")

    @property
    def factor_covariance(self) -> pd.DataFrame:
        """Exponentially weighted factor return covariance with 60-day half-life."""
        if self.factor_returns_ is None:
            raise ValueError("Model must be fit before accessing factor covariance.")
        factor_returns = self.factor_returns_.replace([np.inf, -np.inf], np.nan)
        if factor_returns.empty:
            return pd.DataFrame(index=self.factor_names, columns=self.factor_names, dtype=float)
        covariance = factor_returns.ewm(halflife=60, adjust=False).cov()
        if covariance.empty:
            return pd.DataFrame(index=factor_returns.columns, columns=factor_returns.columns, dtype=float)
        latest_date = covariance.index.get_level_values(0)[-1]
        return covariance.loc[latest_date].reindex(index=factor_returns.columns, columns=factor_returns.columns)

    def _weighted_ridge_fit(self, x_values: np.ndarray, y_values: np.ndarray, weights: np.ndarray) -> np.ndarray:
        lhs = x_values.T @ (x_values * weights[:, None])
        ridge = np.eye(lhs.shape[0], dtype=float)
        rhs = x_values.T @ (y_values * weights)
        return np.linalg.solve(lhs + ridge * self.ridge_lambda, rhs)

    def _industry_for_date(
        self,
        industry_dummies: pd.DataFrame | None,
        date: object,
        columns: pd.Index,
    ) -> pd.DataFrame | None:
        if industry_dummies is None:
            return None
        if not isinstance(industry_dummies, pd.DataFrame):
            raise TypeError("industry_dummies must be a pandas DataFrame when provided.")

        if isinstance(industry_dummies.columns, pd.MultiIndex):
            if date not in industry_dummies.index:
                return None
            row = industry_dummies.loc[date]
            if not isinstance(row.index, pd.MultiIndex):
                return None
            industry = row.unstack()
            if len(industry.index.intersection(columns)) == 0 and len(industry.columns.intersection(columns)) > 0:
                industry = industry.T
            return industry.reindex(columns).astype(float)

        if isinstance(industry_dummies.index, pd.MultiIndex):
            date_level = "date" if "date" in industry_dummies.index.names else 0
            try:
                industry = industry_dummies.xs(date, level=date_level)
            except KeyError:
                return None
            return industry.reindex(columns).astype(float)

        if date not in industry_dummies.index:
            return None
        row = industry_dummies.loc[date]
        if isinstance(row, pd.Series):
            return pd.DataFrame(row.reindex(columns), columns=["industry"]).astype(float)
        return row.reindex(columns).astype(float)
