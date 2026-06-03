# Walk-Forward Validation

- Input: `results\v4_e1_replay\v4_returns_panel.parquet`
- Train years: 5
- Test years: 1
- Test windows: 6
- Interpretation: Test windows are broadly positive, but this is still a time-split diagnostic rather than proof of live alpha.

## Summary

| metric | value |
| --- | ---: |
| overall_sharpe | 0.8320 |
| first_half_sharpe | 0.4788 |
| second_half_sharpe | 1.0810 |
| test_sharpe_mean | 0.9865 |
| test_sharpe_min | 0.0454 |
| test_positive_sharpe_ratio | 1.0000 |

## Windows

| window_id | split | start_date | end_date | n_days | sharpe | annual_return | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2014_2018_to_2019_2019 | train | 2014-01-02 | 2018-12-31 | 1258 | 0.5085 | 0.0441 | 0.2134 |
| 2014_2018_to_2019_2019 | test | 2019-01-02 | 2019-12-31 | 252 | 1.0538 | 0.1091 | 0.1034 |
| 2015_2019_to_2020_2020 | train | 2015-01-02 | 2019-12-31 | 1258 | 0.6905 | 0.0655 | 0.2134 |
| 2015_2019_to_2020_2020 | test | 2020-01-02 | 2020-12-31 | 253 | 2.1066 | 0.5675 | 0.1621 |
| 2016_2020_to_2021_2021 | train | 2016-01-04 | 2020-12-31 | 1259 | 1.3200 | 0.1844 | 0.1621 |
| 2016_2020_to_2021_2021 | test | 2021-01-04 | 2021-12-31 | 252 | 0.1160 | 0.0051 | 0.1524 |
| 2017_2021_to_2022_2022 | train | 2017-01-03 | 2021-12-31 | 1259 | 1.0591 | 0.1564 | 0.1621 |
| 2017_2021_to_2022_2022 | test | 2022-01-03 | 2022-12-30 | 251 | 1.1427 | 0.2042 | 0.0745 |
| 2018_2022_to_2023_2023 | train | 2018-01-02 | 2022-12-30 | 1259 | 1.0788 | 0.1761 | 0.2018 |
| 2018_2022_to_2023_2023 | test | 2023-01-03 | 2023-12-29 | 250 | 1.4545 | 0.2104 | 0.1447 |
| 2019_2023_to_2024_2024 | train | 2019-01-02 | 2023-12-29 | 1258 | 1.1943 | 0.2058 | 0.2018 |
| 2019_2023_to_2024_2024 | test | 2024-01-02 | 2024-12-31 | 252 | 0.0454 | -0.0033 | 0.0971 |
