# Pillar 4 Baseline Equal-Weight Composite

## Design
- Inputs come from `data/factor_data/factors_sector_neutral.parquet`.
- Baseline version is `baseline_4f`; `include_optional_default` is `True`.
- Negative-signal factors are multiplied by `-1`, then each factor is re-zscored by date.
- Composite signal is the equal-weight mean of the four adjusted factors, then re-zscored by date.
- Portfolio is long top decile and short bottom decile, equal-weighted, rebalanced daily.
- Trading uses a 1-day lag: holdings on date T use the composite signal from T-1.
- No transaction costs and no optimized weights are included in this baseline.

## Factor Universe
| factor | sign | interpretation |
| --- | --- | --- |
| short_term_reversal | 1 | higher score = expected higher return |
| idiosyncratic_vol | -1 | higher score = expected higher return |
| realized_vol | -1 | higher score = expected higher return |
| week_52_high | -1 | higher score = expected higher return |

## Coverage
| factor | non_null_ratio |
| --- | --- |
| short_term_reversal | 0.9523590480351302 |
| idiosyncratic_vol | 0.9454948861854192 |
| realized_vol | 0.9454948861854192 |
| week_52_high | 0.91478679369987 |

## Correlation Flags
| factor_1 | factor_2 | average_rank_correlation | abs_average_rank_correlation | deduplication_flag |
| --- | --- | --- | --- | --- |
| idiosyncratic_vol | realized_vol | 0.9166717291011439 | 0.9166717291011439 | True |

## Backtest Summary
| metric | value |
| --- | --- |
| start_date | 2014-02-05 |
| end_date | 2024-12-31 |
| n_days | 2745 |
| annualized_return | 0.14746506209330712 |
| annualized_sharpe | 0.773378095668468 |
| max_drawdown | -0.30604372333759733 |
| average_daily_turnover | 0.19629464136798105 |
| hit_rate | 0.5074681238615665 |
| average_long_count | 49.84663023679417 |
| average_short_count | 49.90819672131148 |

## Data Limitation
Yahoo/free-data universes can contain survivorship bias; treat this baseline as research infrastructure, not live-trading evidence.
