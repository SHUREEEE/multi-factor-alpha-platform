"""Tests for SEC shares outstanding normalization."""

from __future__ import annotations

import pandas as pd

from scripts.download_sec_shares_outstanding import parse_shares_outstanding


def test_parse_sec_companyfacts_shares_outstanding() -> None:
    payload = {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"filed": "2024-02-01", "form": "10-K", "val": 1000},
                            {"filed": "2024-05-01", "form": "8-K", "val": 9999},
                            {"end": "2024-08-01", "form": "10-Q", "val": 1200},
                        ]
                    }
                }
            }
        }
    }

    frame = parse_shares_outstanding(payload, "ABC")

    assert frame.shape[0] == 2
    assert frame["field"].unique().tolist() == ["shares_outstanding"]
    assert frame["value"].tolist() == [1000, 1200]
    assert pd.Timestamp("2024-02-01") in set(frame["date"])
