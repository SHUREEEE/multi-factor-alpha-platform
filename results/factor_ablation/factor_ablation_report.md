# Factor Leave-One-Out Ablation

## Scope

- This is a Pillar 4 combination-layer diagnostic.
- It uses sign-adjusted equal-weight composites and a no-cost top/bottom decile backtest.
- It is not a replacement for V4 optimizer-level retraining.

## Summary

- Portfolio: `baseline_4f_equal_weight`
- Full Sharpe: 0.7734
- Full annualized return: 0.1475
- Interpretation: Dropping week_52_high improves the no-cost combination Sharpe, so this factor should be reviewed before promotion.

## Ablation Table

| scenario | removed_factor | factor_count | annualized_sharpe | delta_sharpe_vs_full | annualized_return | average_daily_turnover | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full |  | 4 | 0.7734 | 0.0000 | 0.1475 | 0.1963 | -0.3060 |
| drop_short_term_reversal | short_term_reversal | 3 | 0.7233 | -0.0501 | 0.1347 | 0.0887 | -0.3469 |
| drop_idiosyncratic_vol | idiosyncratic_vol | 3 | 0.7476 | -0.0258 | 0.1477 | 0.2571 | -0.3515 |
| drop_realized_vol | realized_vol | 3 | 0.8154 | 0.0420 | 0.1527 | 0.2603 | -0.3163 |
| drop_week_52_high | week_52_high | 3 | 0.8400 | 0.0666 | 0.1518 | 0.2037 | -0.3041 |
