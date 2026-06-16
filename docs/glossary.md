# Glossary

Short definitions for reviewer-facing terms used across the project.

| Term | Meaning in this repo |
| --- | --- |
| ADV20 | Twenty-day average dollar volume, used for participation and liquidity checks. |
| ADR | Architecture Decision Record documenting why a design path changed. |
| Barra-style attribution | Cross-sectional factor attribution inspired by Barra workflows, using factor exposures and weighted least squares. |
| Borrow feed | Prime-broker availability, locate, and borrow-cost data required before short-side live launch claims. |
| Capacity | Estimated AUM or order size that can be traded without breaching participation or impact assumptions. |
| Fail-closed | A control that blocks output when required inputs are missing instead of silently falling back. |
| Gross PnL | Strategy profit and loss before transaction costs and implementation drag. |
| Implementation drag | Difference between gross and net performance after costs, turnover, and trading constraints. |
| Net PnL | Strategy profit and loss after transaction costs and implementation assumptions. |
| PIT | Point-in-time data discipline: only information available at the decision timestamp is allowed. |
| Quarantine | A documented block on using a result or claim until required evidence is restored. |
| T+1 | Backtest alignment where today's portfolio decision earns tomorrow's return. |
| Turnover | Amount of portfolio weight traded over a period; high turnover usually increases costs. |
| WLS | Weighted least squares; here used for cross-sectional factor-return estimation. |

