# Merging upstream FreeCAD

We merge FreeCAD's `main` into ours **once a month** ([PLAN §1.4](PLAN.md#14-staying-mergeable-with-upstream))
to keep getting the kernel and bug fixes. Small, regular merges stay cheap; skipped months add up.
Every merge goes through a branch and a full test run before it reaches `main`.

## One-time setup (per clone)

```powershell
git remote add upstream https://github.com/FreeCAD/FreeCAD.git
git remote set-url --push upstream DISABLED-never-push-to-FreeCAD   # pushing to upstream must fail
gh repo set-default morganbnjrotc-lang/CAD-                       # gh never targets FreeCAD's repo
```

We never push to FreeCAD, and we never open, comment on or react to its issues or PRs (see
[AGENTS.md](../AGENTS.md)). Without `gh repo set-default`, `gh pr create` in a clone with an `upstream`
remote can pick FreeCAD's repo.

## 1. Before merging

Start from a clean `main` with CI green. Take the "before" numbers now: the build folder gets
rebuilt by step 3, so they can't be measured afterwards.

```powershell
git switch main; git status                      # nothing to commit
git fetch upstream
# On a quiet machine (no build, test run or heavy app running):
pixi run python tools/bench/bench_startup.py --runs 6 --label before-merge
pixi run python tools/bench/bench_open.py --runs 6 --label before-merge
```

The last full test log in `build/test-logs/` (from `run_headless_suites.py --exclude TestCAMApp`)
is the "before" for tests. If there isn't a recent one, run it now.

**Preview** what's coming in (bash):

```bash
B=$(git merge-base main upstream/main)
git rev-list --count main..upstream/main                 # commits
git diff --stat $B upstream/main | tail -1               # files
git merge-tree --write-tree --name-only main upstream/main   # exit 0 = no conflicts; else lists them
# Upstream changes to files we patch (the list in CORE_PATCHES.md):
git diff --name-only $B upstream/main -- README.md AGENTS.md CMakePresets.json pixi.toml \
    cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake src/Mod/CMakeLists.txt \
    tests/CMakeLists.txt src/Mod/Start/StartMigrator.py .github
# New Python files: check for network access (product code makes no network calls):
git diff --name-only --diff-filter=A $B upstream/main -- '*.py'
```

## 2. Merge on a branch

```bash
git switch -c upstream-merge/YYYY-MM-DD main
git merge --no-ff upstream/main -m "Merge upstream FreeCAD main (<short sha>)"
```

Merge, never rebase or squash. The merge commit keeps upstream's history in ours, so the next
merge only brings new commits and `git blame` still points at FreeCAD's authors.

**Conflicts:** each patched file has merge notes in [CORE_PATCHES.md](CORE_PATCHES.md). The usual ones:

| Conflict | Resolution |
|---|---|
| Upstream edits a file we deleted (`.github/workflows/*`, `.github/dependabot.yml`) | `git rm` it |
| Upstream edits `README.md` / `AGENTS.md` | Ours are new files; apply their change to `README.FreeCAD.md` / `AGENTS.FreeCAD.md` |
| `CMakePresets.json`, `pixi.toml` | Keep both sides; copy any new flags upstream adds to its `configure-*` tasks into ours |
| A patch upstream made unnecessary | Drop our patch and remove its row from CORE_PATCHES.md |

## 3. Build and test

```powershell
pixi run python -m unittest discover -s tools/repo_tests -v   # new upstream workflows, renamed BUILD_* options
$env:CMAKE_BUILD_PARALLEL_LEVEL = '6'; pixi run build          # CMake re-runs by itself if upstream changed it
pixi run test                                                  # C++
pixi run python tools/test/run_headless_suites.py --exclude TestCAMApp --log merge-noCAM.log
pixi run python tools/test/run_cam_batches.py
pixi run python tools/test/run_gui_suites.py TestStudioGui
pixi run python tools/test/startup_smoke.py
pixi run python tools/test/compare_test_logs.py build/test-logs/<before>.log build/test-logs/merge-noCAM.log
```

- **0 tests worse** is the bar. Upstream adding or removing tests is fine; `compare_test_logs.py`
  lists them.
- A test that fails after the merge: if our code or a patch is involved, fix it on the branch. If it's
  purely upstream's, record it in [BASELINE.md](BASELINE.md) as a known upstream failure, with the
  upstream commit that broke it.
- Run the two benchmarks again (quiet machine) and compare with the "before" numbers from step 1.
- Try it: `pixi run freecad`, open a reference file.

## 4. CI, then `main`

```bash
git push -u origin upstream-merge/YYYY-MM-DD
gh workflow run studio-ci.yml --ref upstream-merge/YYYY-MM-DD -f full=true   # slim Release + every suite
```

When CI is green: `git switch main && git merge --ff-only upstream-merge/YYYY-MM-DD && git push`
(if `main` got new commits meanwhile, use a plain `git merge` instead), add a row to the log
below, and delete the branch.

## Log

| Date | Upstream commit | Commits | Conflicts | Tests | Notes |
|---|---|---|---|---|---|
| 2026-11-14 | `00cb280454` | 19 (142 files) | none | Local full build, **0 worse**: C++ 26/26; headless 1,642 = 1,642; CAM 2,077 (11 new upstream), 0 failures; GUI 2/2; startup smoke pass | First (practice) merge. Upstream touched one patched file, `src/Mod/CMakeLists.txt` (SPDX header only). Incremental rebuild 4.5 min. New `src/Ext/freecad/content_provider.py` is a registry with no network code yet; watch what registers providers. Startup and file open unchanged within noise (2.05 s vs 1.97 s with ±0.15 s between batches; files +0.01–0.02 s); the first startup right after the rebuild measured 2.25 s. Full CI on the branch: all suites green; the new reference-file check first failed on the runner's "Invalid OpenGL Version" warning (no GPU, OpenGL 1.1), fixed in `a10a2cd3c9` before landing. |
