# GitHub Release Checklist

These items cannot all be done from the local repository, but they should be
completed before sending the link in applications.

## Repository Settings

- Short description: `End-to-end US equity multi-factor research and risk-engineering platform with T+1 backtesting, attribution diagnostics, and launch gates.`
- Topics:
  - `quantitative-finance`
  - `factor-investing`
  - `risk-attribution`
  - `portfolio-construction`
  - `backtesting`
  - `python`
- Pin the repository on the GitHub profile.
- Confirm the default branch name is acceptable (`main` is preferred on GitHub).

## Reviewer Path

- README first screen explains the v1 research track, v4 engineering candidate,
  and live-launch blocker.
- `docs/PROJECT_BRIEF.md` can be read in under five minutes and links to the
  most important evidence artifacts.
- `docs/career/elevator_pitch.md` is consistent with README language and does
  not claim live readiness.
- V4 acceptance-gate language is presented as local engineering evidence, not
  out-of-sample proof or a production launch claim.

## Pre-Send Checks

- `python -m pip install -r requirements.txt` works in a fresh environment.
- `python -m pytest` passes.
- `git status --short` is clean.
- No local absolute paths such as `F:/project/...` appear in tracked files.
- Large Parquet panels and generated images are not committed.
- No README, brief, resume, or pitch text claims publishable Barra attribution
  until a real market-cap panel is restored.

## Link Placement

- Resume project line should link to the repo.
- LinkedIn project entry should use the 30-second project positioning.
- Do not describe the project as live-ready; describe it as v1 research-complete
  with a v4 engineering candidate and live-readiness blockers documented.
