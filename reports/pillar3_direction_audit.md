# Pillar 3 Price Factor Direction Audit

This report checks sign conventions for the active price-only factors.

**No automatic sign flip applied.** All metrics use the saved factor scores as-is.

Conventions audited:
- Q1 is the lowest factor score and Q10 is the highest factor score.
- Long-short return is Q10 minus Q1.
- IC is corr(factor_score_T, future_return_T+1), with no extra sign flip.

| factor | mean_ic_1d | ic_sign | long_short_mean_return_1d | long_short_sign | monotonicity | monotonicity_sign | directions_consistent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| momentum_12_1 | 0.01243756 | positive | 0.00008221 | positive | -0.11515152 | negative | no |
| short_term_reversal | 0.00530170 | positive | 0.00040715 | positive | 0.80606061 | positive | yes |
| week_52_high | 0.00428670 | positive | -0.00063110 | negative | -0.92727273 | negative | no |
| idiosyncratic_vol | 0.00133905 | positive | -0.00060746 | negative | -0.89090909 | negative | no |
| beta_inverse | 0.00002127 | positive | -0.00049946 | negative | -0.76969697 | negative | no |
| realized_vol | 0.00082846 | positive | -0.00058766 | negative | -0.93939394 | negative | no |

## Factors Requiring Review

### momentum_12_1
- IC sign: positive
- Long-short sign: positive
- Monotonicity sign: negative
- Plausible explanation: Likely weak signal with noisy tails; inspect quantile curve before any sign decision.
- Proposed fix: do not flip sign automatically; first re-test after sector neutralization.

### week_52_high
- IC sign: positive
- Long-short sign: negative
- Monotonicity sign: negative
- Plausible explanation: Likely regime or tail effect: broad rank IC is mildly positive, while extreme high-score stocks underperform low-score stocks.
- Proposed fix: do not flip sign automatically; first re-test after sector neutralization.

### idiosyncratic_vol
- IC sign: positive
- Long-short sign: negative
- Monotonicity sign: negative
- Plausible explanation: Likely sector/universe/tail effect: low-vol definitions are correct, but sector tilts and top-decile tails dominate the average spread.
- Proposed fix: do not flip sign automatically; first re-test after sector neutralization.

### beta_inverse
- IC sign: positive
- Long-short sign: negative
- Monotonicity sign: negative
- Plausible explanation: Likely sector/universe/tail effect: low-vol definitions are correct, but sector tilts and top-decile tails dominate the average spread.
- Proposed fix: do not flip sign automatically; first re-test after sector neutralization.

### realized_vol
- IC sign: positive
- Long-short sign: negative
- Monotonicity sign: negative
- Plausible explanation: Likely sector/universe/tail effect: low-vol definitions are correct, but sector tilts and top-decile tails dominate the average spread.
- Proposed fix: do not flip sign automatically; first re-test after sector neutralization.

