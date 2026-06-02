# V4 Implementation Charter

## Purpose
This charter governs V4 implementation after the V4 design gate. It exists to keep each change reviewable, requirement-scoped, and test-backed. The canonical V3 baseline remains ADR-0001 Option 1, cache order / single-pass.

## PR Split Rules
- Default rule: one `REQ-F` per PR.
- Exception: tightly coupled requirements may be grouped in one PR, with a maximum of three `REQ-F` items per PR.
- Every PR must declare the exact `REQ-F` and `REQ-N` ids it touches before code review.
- Every PR must avoid modifying production code outside its declared requirement scope.
- Every PR must preserve the V4 source-of-truth rule: all weight construction must route through the shared V4 builder once the builder exists.

## Test Discipline
- Every PR must include the corresponding `REQ-N-002` automated test coverage.
- New tests must fail without the implementation they validate, unless the PR is an explicit skeleton PR with documented `pytest.skip`.
- Tests must assert the measurable acceptance criteria in `reports/pillar5_stage58_v4_specification.md` and `reports/v4_design.md`.
- `python -m pytest tests/` must pass before merge.

## Documentation Discipline
- Every PR must update `reports/v4_design.md` Section 15, "Implementation Status Tracker".
- Status values are limited to `NOT-STARTED`, `IN-PROGRESS`, and `MERGED`.
- `PR-ref` may be a workflow name or review id until a real PR id exists.
- `test-ref` must name the test file that enforces the requirement, or state the approved skip reason for a skeleton PR.

## Scope Control
- V4 implementation must not introduce new alpha signals.
- V4 implementation must not modify ADR-0001, Pillar 5 locked artifacts, or the V3 cache unless a separate owner-approved workflow explicitly authorizes it.
- V4 implementation must not change unrelated Pillar 4 or Pillar 5 conclusions.
- V4 implementation must not use Sharpe improvement as a substitute for passing live-readiness requirements.

## Merge Checklist
- Declared `REQ` ids match the code and tests touched.
- Requirement acceptance criteria have automated tests or an approved skeleton skip.
- `reports/v4_design.md` Section 15 is updated.
- Source-of-truth builder path is respected.
- `python -m pytest tests/` is green.
