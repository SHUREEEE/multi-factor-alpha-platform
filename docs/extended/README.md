# Extended: Production Engineering Layer

This directory contains production-engineering work built on top of Pillar 5 portfolio construction. It is bonus scope for interview review: useful evidence of launch discipline and operating controls, but not the main project narrative.

The core project remains the Pillar 1-7 multi-factor strategy pipeline described in the top-level README.

## Contents

| Item | Path | Purpose |
| --- | --- | --- |
| ADR-0001 | [adr/ADR-0001-v3-canonical-neutralization-order.md](adr/ADR-0001-v3-canonical-neutralization-order.md) | Canonical V3 neutralization order decision. |
| ADR-0002 | [adr/ADR-0002-turnover-optimizer-reparam.md](adr/ADR-0002-turnover-optimizer-reparam.md) | Turnover optimizer reparameterization decision. |
| ADR-0003 | [adr/ADR-0003-v4-turnover-design-revision.md](adr/ADR-0003-v4-turnover-design-revision.md) | V4 turnover design revision decision. |
| V4 design | [v4/reports/v4_design.md](v4/reports/v4_design.md) | Production-oriented V4 portfolio construction design. |
| PB feed contract | [v4/v4_pb_borrow_feed_contract.md](v4/v4_pb_borrow_feed_contract.md) | Prime broker borrow feed schema, validation, and live-readiness boundary. |
| Kill switch runbook | [v4/v4_kill_switch_runbook.md](v4/v4_kill_switch_runbook.md) | Operator actions for PIT, drawdown, halt, and borrow-feed failures. |
| Launch handoff | [v4/v4_launch_handoff.md](v4/v4_launch_handoff.md) | Engineering readiness summary and external PB-feed launch blocker. |

## Supporting V4 Reports

Copied V4 reports are preserved under [v4/reports/](v4/reports/), including acceptance gates, capacity, risk decomposition, stress regime, implementation charter, and live-readiness checklist material.

## Boundary

This layer documents production-engineering scaffolding only. It should be read after the core Pillar 1-7 strategy narrative, and it should not be treated as a new pillar, a required workflow, or the primary story of the repository.
