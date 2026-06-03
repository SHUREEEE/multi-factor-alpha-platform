# V4 Walk-Forward Parameter Selection

- V3 cache: `results\pillar5_artifacts`
- Train years: 5
- Test years: 1
- Grid size: 3
- Windows: 6
- Interpretation: Parameter-selected test windows are mixed; inspect weak windows and avoid full-sample claims.

## Summary

| metric | value |
| --- | ---: |
| test_sharpe_mean | 0.9491 |
| test_sharpe_min | -0.0426 |
| test_positive_sharpe_ratio | 0.8333 |

## Selected Test Windows

| window_id | point_id | start_date | end_date | n_days | sharpe | annual_return | max_drawdown | avg_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014_2018_to_2019_2019 | point_02 | 2019-01-02 | 2019-12-31 | 252 | 1.1222 | 0.1173 | 0.1011 | 0.0000 |
| 2015_2019_to_2020_2020 | point_01 | 2020-01-02 | 2020-12-31 | 253 | 2.0705 | 0.5593 | 0.1644 | 0.0007 |
| 2016_2020_to_2021_2021 | point_02 | 2021-01-04 | 2021-12-31 | 252 | -0.0426 | -0.0223 | 0.1565 | 0.0000 |
| 2017_2021_to_2022_2022 | point_01 | 2022-01-03 | 2022-12-30 | 251 | 1.1520 | 0.2081 | 0.0759 | 0.0184 |
| 2018_2022_to_2023_2023 | point_01 | 2023-01-03 | 2023-12-29 | 250 | 1.3709 | 0.1957 | 0.1447 | 0.0098 |
| 2019_2023_to_2024_2024 | point_01 | 2024-01-02 | 2024-12-31 | 252 | 0.0214 | -0.0067 | 0.0980 | 0.0013 |
