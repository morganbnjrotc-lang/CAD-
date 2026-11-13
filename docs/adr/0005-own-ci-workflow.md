# 0005 — Our own CI; upstream FreeCAD's automation removed from the fork

- **Status:** accepted
- **Date:** 2026-11-12

## Context

The fork inherited FreeCAD's 26 GitHub workflows and its Dependabot config. On our repo they:

- ran FreeCAD's checks on every push (`CI_primary`/`CI_approved`: about 20 minutes of Ubuntu build and lint)
  while never running our Studio tests;
- opened daily Dependabot PRs about FreeCAD's dependencies (#5–#10 by 2026-11-12), each triggering
  more workflows (Labeler, Backport, Dependency Review; some failed);
- ran no-op scheduled jobs (stale bots, CodeQL, Crowdin, release builds) that exit early on the
  `github.repository_owner == 'FreeCAD'` guard but still clutter the Actions page.

The repo is public, so GitHub-hosted runner minutes are free; noise and wrong signal were the
problem, not cost. ([PLAN.md](../PLAN.md) risk table: Windows minutes cost 2× if the repo goes private.)

Options considered:

1. **Disable the upstream workflows in GitHub settings.** No merge conflicts, but the state isn't in
   the repo, and any new workflow an upstream merge adds would start running unnoticed. Dependabot
   can't be turned off this way.
2. **Delete them in the fork (chosen).** Versioned and reviewable. Costs modify/delete conflicts
   during upstream merges.

## Decision

- Delete every top-level `.github/workflows/*.yml` from upstream and `.github/dependabot.yml`. Keep the
  composite actions (`.github/workflows/actions/`), problem matchers and other `.github` files: they
  only run when a workflow calls them, and keeping them avoids merge conflicts.
- Add one workflow, [`.github/workflows/studio-ci.yml`](../../.github/workflows/studio-ci.yml):
  - every push to `main` and every PR: Windows Release build (pixi + ccache in the Actions cache), then
    `TestStudioApp`, `TestStudioGui` and the startup smoke test;
  - nightly and on manual runs: also every headless FreeCAD suite, CAM in batches;
  - a fast Ubuntu job runs `tools/repo_tests` (no build needed).
- CI builds **Release**, not RelWithDebInfo: MSVC `/Z7` debug info (needed for ccache) makes objects
  several times larger, which the 10 GB per-repo Actions cache can't usefully hold.
- `tools/repo_tests/test_ci_workflows.py` enforces: only our workflow files exist, no Dependabot
  config, read-only default token, every job has a timeout, every action is pinned to a commit SHA,
  and the Windows job runs the Studio suites through our isolating runners.

## Consequences

- Upstream merges: `git rm` any deleted workflow that upstream modified (modify/delete conflict). If
  upstream adds a new workflow, `tools/repo_tests` fails on the merge branch; delete it there. Run
  `pixi run python -m unittest discover -s tools/repo_tests` before pushing a merge branch.
- First CI run has no compiler cache and may take hours on a 4-vCPU runner (job limit 345 min). The
  cache is saved even when the build fails or times out, so each run starts further along. The slim
  build (Phase 1.5) will cut this further.
- No more Dependabot updates. Our workflow pins actions by SHA; bump them by hand when needed.
- Lesson: a bare `FreeCAD.exe -t` uses the real profile. When the dev build's profile doesn't exist
  yet but an older FreeCAD's does, FreeCAD opens the modal settings-migration dialog and the tests
  hang behind it (a fresh CI runner has the same problem). GUI suites go through
  `tools/test/run_gui_suites.py`, which isolates the profile and kills the app on timeout.
