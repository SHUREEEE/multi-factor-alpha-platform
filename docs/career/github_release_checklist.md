# GitHub Release Checklist

These items cannot all be done from the local repository, but they should be
completed before sending the link in applications.

## Repository Settings

- Short description: `End-to-end US equity multi-factor research platform with T+1 backtesting, risk attribution, and fail-closed diagnostics.`
- Topics:
  - `quantitative-finance`
  - `factor-investing`
  - `risk-attribution`
  - `portfolio-construction`
  - `backtesting`
  - `python`
- Pin the repository on the GitHub profile.
- Confirm the default branch name is acceptable (`main` is preferred on GitHub).

## Pre-Send Checks

- `python -m pip install -r requirements.txt` works in a fresh environment.
- `python -m pytest` passes.
- `git status --short` is clean.
- No local absolute paths such as `F:/project/...` appear in tracked files.
- Large Parquet panels and generated images are not committed.

## Link Placement

- Resume project line should link to the repo.
- LinkedIn project entry should use the 30-second project positioning.
- Do not describe the project as live-ready; describe it as v1 research-complete
  with live-readiness blockers documented.
