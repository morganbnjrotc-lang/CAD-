# Baseline

The state of **upstream FreeCAD** in our build, recorded before Studio adds any features. Use it to
tell pre-existing problems from ones we introduce, and as the reference for the performance budgets
in [PLAN.md §1.3](PLAN.md#13-performance-budgets).

| | |
|---|---|
| Date | 2026-11-11 |
| Upstream commit | `6f5da8998d` (FreeCAD `main`, 2026-11-11) |
| Build | RelWithDebInfo, pixi `conda-windows` preset, Ninja, MSVC 19.44, Python 3.13.18, Qt/PySide 6.11.3 |
| Machine | Windows 11 Home, AMD Ryzen AI 7 445 (6c/12t), 16 GB RAM, Radeon 840M |
| Full build time | 1 h 19 min (6 parallel jobs) |

All runs below use a **throwaway FreeCAD profile** (verified: FreeCAD's `user.cfg` was inside it).

## Tests

| Suite | Command | Result |
|---|---|---|
| C++ (GoogleTest + QtTest) | `pixi run test` | **26 / 26 test programs passed** |
| Headless Python, all suites except CAM | `tools/test/run_headless_suites.py --exclude TestCAMApp` | **1,631 upstream tests: 0 failures, 0 errors, 25 skipped** (plus 11 Studio tests, all passing) |
| Headless Python, CAM | `tools/test/run_cam_batches.py` | **2,066 run: 0 failures, 0 errors, 11 skipped** |
| GUI: Studio | `tools/test/run_gui_suites.py TestStudioGui` | 2 / 2 passed |
| GUI: upstream suites (`...Gui`) | not yet recorded | — |
| End-to-end startup | `tools/test/startup_smoke.py` | pass: a brand-new profile opens in `StudioWorkbench` |

Skips are environmental: 24 need the GUI and run under `FreeCAD.exe`, not `FreeCADCmd`; one
Sketcher case is skipped upstream on purpose ("secants still under discussion").

### Known upstream issue: CAM hangs on Windows after ~16,000 `asyncio.run()` calls

Running the whole CAM suite in one process **hangs forever** on this machine, always somewhere
inside the CAM tests, with 0% CPU.

- **Cause:** CAM's tool-asset manager (`Mod/CAM/Path/Tool/assets/manager.py`, `add_raw`) calls
  `asyncio.run()` for each asset. On Windows every new event loop opens a loopback socket pair,
  which leaves one TCP port in `TIME_WAIT` for about 2 minutes. Windows has 16,384 dynamic ports, so after
  roughly 15–16k calls they run out, and CPython's `_fallback_socketpair` then blocks forever in
  `accept()` instead of raising.
- **Reproduced outside FreeCAD:** a plain Python loop of `asyncio.run(noop())` hangs the same way
  after ~15,000 iterations (TIME_WAIT count climbing ~1 per call).
- **Effect on users:** loading many CAM tools/assets in a short time on Windows could freeze the
  app. Tracked for **Phase 8 (CAM)**: the asset manager should reuse one event loop instead of
  creating one per call.
- **Workaround for testing:** `tools/test/run_cam_batches.py` runs CAM in batches and waits for
  `TIME_WAIT` to drain between them.

### Known upstream issue: C++ tests fail on a fresh build folder on Windows (fixed)

`tests/CMakeLists.txt` put module DLL folders (`build/…/Mod/<name>`) on the test `PATH` by globbing
them at configure time, but they're only created by the build. On a brand-new build folder every C++
test that loads a module DLL failed with `0xc0000135` (DLL not found) until CMake was re-run. The 26/26
above passed only because that build had been reconfigured. Fixed in our fork (see
`docs/CORE_PATCHES.md`); worth sending upstream.

### Known upstream issue: first-run migration overrode the start workbench (fixed)

On every brand-new profile, `src/Mod/Start/StartMigrator.py` set the startup workbench to a
hardcoded `PartDesignWorkbench`, ignoring `branding.xml`. Fixed in our fork (see
`docs/CORE_PATCHES.md`); worth sending upstream.

## Performance

`pixi run python tools/bench/bench_startup.py --runs 6` (fresh throwaway profile for every run):

| Metric | Baseline |
|---|---|
| First start (fresh profile, OS file cache partly warm) | 5.1 s |
| Median start, runs 2–6 (launch → idle, usable main window) | **4.4 s** |
| Working set at ready | **598 MB** |
| Private bytes at ready | **559 MB** |

Budgets from this baseline (PLAN §1.3): startup at or below **2.2 s** by the end of Phase 2; memory must
not grow without sign-off.

**Re-measured 2026-11-13** (same full build, laptop on AC power, Windows "Balanced" plan, 6 runs):
median start **3.03 s**, working set 597 MB, private 559 MB. Memory matches; startup is 1.3 s faster
than on 2026-11-11. The 11-11 runs came right after the build finished, likely while the
OS was still scanning the new binaries. Startup numbers are only comparable when measured back to
back in one session; record the power state with them. **Decision (2026-11-13): the Phase 2 target
stays 2.2 s**, now a fixed number rather than 50% of whatever the baseline measures.

## Slim build (2026-11-13)

`pixi run configure-slim` / `build-slim` ([ADR 0006](adr/0006-slim-build.md)), measured back to back
with the full build:

| | Full | Slim |
|---|---|---|
| C++ test programs | 26 pass | 25 pass (Points' removed) |
| Headless Python (except CAM) | 1,642 pass, 25 skipped | 1,232 pass, 25 skipped, **0 worse**; all 410 missing are BIM/FEM tests |
| CAM in batches | 2,066 pass, 11 skipped | 2,066 pass, 11 skipped |
| GUI suite, startup smoke | pass | pass |
| Median start | 3.03 s | 3.00 s |
| Working set / private at ready | 597 / 559 MB | 584 / 542 MB |
| `bin` + `Mod` on disk | 5.3 GB | 4.2 GB |

> **Correction:** an earlier version of this page reported 4.7 s / 537 MB / 1.9 GB private. Those
> runs weren't actually isolated (FreeCAD ignores `FREECAD_USER_*` unless the folders exist) and
> used a profile that test runs had filled up. The numbers above replace them.

## Tools

- `tools/test/run_headless_suites.py`: runs suites in a throwaway profile (fails if the profile
  isn't really isolated), with a per-test watchdog that prints every thread's stack instead of hanging.
- `tools/test/run_cam_batches.py`: the CAM suite in batches (see the hang above).
- `tools/test/startup_smoke.py`: launches the real app on a brand-new profile and checks what a new
  user sees.
- `tools/test/run_gui_suites.py`: GUI suites (`FreeCAD.exe -t`) in a throwaway profile, killed on timeout.
- `tools/test/compare_test_logs.py`: diffs two suite logs (missing tests by module, tests that got worse).
- `tools/bench/bench_startup.py`: startup and memory benchmark, also in a throwaway profile.
