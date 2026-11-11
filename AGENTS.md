# Working with AI agents in this repository

These instructions apply to any AI assistant working here (Claude Code or others). They
replace FreeCAD's upstream agent policy, which is kept as [AGENTS.FreeCAD.md](AGENTS.FreeCAD.md)
and applies **only** when preparing a change to send back to the FreeCAD project.

## What this project is

A fork of FreeCAD that becomes a fast, fully local, lightweight CAD/CAM app with a much
cleaner, single-environment UI. Read these before starting work:

| File | What it tells you |
|---|---|
| [README.md](README.md) | Goals, principles, feature roadmap and the gap analysis against FreeCAD |
| [docs/PLAN.md](docs/PLAN.md) | Phases, system architecture, TDD rules, performance budgets |
| [docs/CORE_PATCHES.md](docs/CORE_PATCHES.md) | Every change we have made to upstream FreeCAD files |

Check which phase is current in `docs/PLAN.md` and stay inside it unless the user says otherwise.

## Architecture rules

Our code lives in **`src/Mod/Studio`** (working codename). Layers, top to bottom:

| Layer | Location | May use | Must not use |
|---|---|---|---|
| Shell (Qt widgets) | `src/Mod/Studio/Gui/` | view-models, FreeCAD Gui | domain logic |
| View-models | `studio/viewmodels/` | interaction, services | Qt widgets |
| Interaction (tools, keymap, navigation) | `studio/interaction/` | services, abstract view/preview interfaces | Qt widgets |
| Domain services | `studio/services/` | FreeCAD App/Part/… APIs | Qt, Gui, views |
| Kernel | FreeCAD `src/Base`, `src/App`, `src/Mod/*` | — | anything in Studio |

- Dependencies point **down only**. If a lower layer needs something from a higher one, add an
  interface in the lower layer and implement it above.
- Put new behavior in Studio. Touch FreeCAD files only when there is no extension point
  (`WorkbenchManipulator`, command registration, navigation-style registration, preference
  pages, overlays), and record each such edit in `docs/CORE_PATCHES.md`.
- When editing FreeCAD core code, follow FreeCAD's engineering guides in
  [contrib/guidelines](contrib/guidelines/README.md), especially
  [architecture](contrib/guidelines/architecture.md) and
  [documents and geometry](contrib/guidelines/documents-and-geometry.md).
- Python first. Use C++ for hot paths (navigation, CAM simulation, rendering) or when profiling shows it's needed.
- Product code makes **no network calls** except explicit, user-started actions (update check,
  part download). No telemetry.
- Significant design decisions get an ADR in `docs/adr/`.

## Test-driven development (required)

1. **Red:** write the test first, run it, and confirm it fails *for the expected reason*. Show the user the failure.
2. **Green:** write the minimum code to pass.
3. **Refactor** with tests green.

- Domain services and view-models are tested **headless** (`FreeCADCmd -t ...`); interaction
  logic with synthetic events; widgets with QTest smoke tests; visuals with reviewed baselines in `tests/visual`.
- Never weaken a test to get it passing: no loosened tolerances, skipped cases, deleted
  assertions or regenerated snapshots without telling the user why the old expectation was wrong.
- Pre-existing upstream failures are listed in `docs/BASELINE.md`. Don't count them as ours; don't count new failures as theirs.
- Report what actually ran. Compiling is not testing, and reading the source doesn't prove the code works.
- The full definition of done is in `docs/PLAN.md` §1.1. A human must try the feature in the running app before it counts as done.

## Build and test

Environment: Windows 11, repo at `C:\dev\CAD` (the toolchain breaks on paths with spaces, so
never build from under `C:\Users\Blaine Morgan`). Smart App Control is off so unsigned builds can
load. 16 GB RAM: keep `CMAKE_BUILD_PARALLEL_LEVEL` at 6 or below.

```powershell
pixi run configure            # CMake configure (RelWithDebInfo, Ninja) -> build/relWithDebInfo
pixi run build                # compile
pixi run test                 # ctest (C++ suites)
pixi run freecad              # install and launch
# Python suites, headless and GUI:
build\relWithDebInfo\bin\FreeCADCmd.exe -t Studio
build\relWithDebInfo\bin\FreeCAD.exe -t StudioGui
```

Run the narrowest suite that covers your change while iterating, then the Studio suites before
committing. Use `pixi run <cmd>` so the right Python, Qt and compilers are on PATH.

## Git and GitHub

- `origin` = our repo (`morganbnjrotc-lang/CAD-`). `upstream` = FreeCAD. **Never push to
  upstream, and never open, comment on or react to FreeCAD's issues or PRs.**
- Commit and push only when the user asks or has already approved it for the current task. Keep commits small and focused.
- Write clear commit messages (imperative summary line, body explains why). AI-assisted
  commits end with a `Co-Authored-By:` trailer naming the model.
- Upstream merges happen on a branch (`git fetch upstream && git merge upstream/main`), get a
  full test run, and then merge to `main`. Don't rebase or rewrite published history.
- Very large pushes over SSH can drop. Push in batches of about 200 commits if that happens.

## Keep docs current

When scope, phase status or architecture changes, update `README.md` / `docs/PLAN.md` in the same
change. Log core edits in `docs/CORE_PATCHES.md`.
