"""Universe management for equity research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable


@dataclass(frozen=True)
class Universe:
    """Manage active tickers through time.

    Notes
    -----
    This basic implementation uses the current S&P 500 and NASDAQ-100 members
    for all dates. That creates survivorship bias because delisted historical
    constituents are missing. A production-grade platform should use a
    point-in-time constituent database.
    """

    tickers: tuple[str, ...]
    name: str = "current_static_universe"

    @classmethod
    def from_tickers(cls, tickers: Iterable[str], name: str = "current_static_universe") -> "Universe":
        """Create a deduplicated static universe."""
        cleaned_tickers = tuple(sorted({str(ticker).strip() for ticker in tickers if str(ticker).strip()}))
        # 中文：去重和排序可以让每次运行的 universe 顺序稳定，便于复现。
        if not cleaned_tickers:
            raise ValueError("Universe requires at least one ticker.")
        return cls(tickers=cleaned_tickers, name=name)

    def get_active_tickers(self, as_of_date: str | date | datetime) -> list[str]:
        """Return active tickers for a date.

        Parameters
        ----------
        as_of_date:
            Date requested by downstream research code.

        Returns
        -------
        list[str]
            Full static ticker list for now.
        """
        _validate_date(as_of_date)  # 中文：即使当前版本不用日期，也要提前约束接口契约。
        return list(self.tickers)  # 中文：当前基础版使用静态名单，后续可替换成 PIT 成分股表。


def _validate_date(as_of_date: str | date | datetime) -> None:
    """Validate user-supplied universe query date."""
    if isinstance(as_of_date, str):
        datetime.fromisoformat(as_of_date)
        return
    if isinstance(as_of_date, (date, datetime)):
        return
    raise TypeError("as_of_date must be str, date, or datetime.")
