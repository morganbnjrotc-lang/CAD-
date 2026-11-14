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

**After merging upstream `00cb280454` (2026-11-14, [UPSTREAM_MERGE.md](UPSTREAM_MERGE.md)):** the
same results, except CAM now has 2,077 tests (11 added upstream), all passing.

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

### Known upstream issue: closing a document right after creating a spreadsheet crashes

Creating a spreadsheet (`Spreadsheet_CreateSheet`, which opens its window) and closing the document
before Qt has processed the window's pending events triggers an access violation. FreeCAD catches
it ("Illegal storage access! … restart the application", "Unhandled Base::Exception caught in
GUIApplication::notify"), but the app can be left unstable: a test run hung afterwards.
Reproduced 3 of 3 times with FreeCAD's own `activateWorkbench` and no Studio code involved; letting
events run before closing avoids it every time (2026-11-14, `StudioTests.gui.test_command_backend`).
A user clicking through the UI is unlikely to hit it; scripts and macros can. Worth reporting
upstream with a minimal script.

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

Budgets from this baseline (PLAN §1.3): startup at or below **1.5 s** by the end of Phase 2, with
**1.0 s** as the stretch goal (set 2026-11-14, see below); memory must not grow without sign-off.

**Re-measured 2026-11-13** (same full build, laptop on AC power, Windows "Balanced" plan, 6 runs):
median start **3.03 s**, working set 597 MB, private 559 MB. Memory matches; startup is 1.3 s faster
than on 2026-11-11. The 11-11 runs came right after the build finished, likely while the
OS was still scanning the new binaries. Startup numbers are only comparable when measured back to
back in one session; record the power state with them. **Decision (2026-11-13): the Phase 2 target
stays 2.2 s**, now a fixed number rather than 50% of whatever the baseline measures.

**Re-measured 2026-11-14 on a quiet machine** (same full build, AC power, "Balanced", CPU at ~5%
before starting, no other heavy apps): median start **1.97 s**, working set 596 MB, private 559 MB.
Repeated three times back to back: 1.95 / 1.99 / 1.98 s. The committed `bench_startup.py` and the
refactored one (shared `benchlib.py`) gave the same numbers in those back-to-back runs, so the drop from
3.03 s is the machine, not the tool. The very first start of the session, with the OS file cache
cold, took 9.6 s. On this laptop the same build has measured 4.4 s, 3.03 s and 1.97 s on three
days. Only back-to-back comparisons mean anything; a single absolute number doesn't. Memory has
stayed the same every time (596–598 MB / 558–559 MB).

**Decision (2026-11-14):** upstream FreeCAD already meets the 2.2 s target on a quiet machine, so it no
longer pushes us anywhere. The Phase 2 target is now **≤ 1.5 s**, with **1.0 s** as the stretch goal.

## Reference files (2026-11-14)

`pixi run python tools/bench/bench_open.py --runs 6`. Each run starts the app in a fresh profile,
opens one file the way File > Open does and waits until the app is idle with the document shown
(**open**: includes loading the modules the file needs), then closes it and opens it again in the
same process (**reopen**: mostly the file itself). A load only counts if it was complete: every
saved object present, no object missing its Python code, and geometry on screen. Same quiet
machine and session as the startup numbers above. Medians of runs 2–6:

| File | Objects | Faces | Open, full | Open, slim | Reopen | + private memory |
|---|---|---|---|---|---|---|
| `data/examples/PartDesignExample.FCStd` | 28 | 255 | **0.49 s** | 0.49 s | 0.16 s | 120 MB |
| `data/examples/AssemblyExample.FCStd` | 54 | 288 | **0.70 s** | 0.68 s | 0.33 s | 143 MB |
| `data/examples/EngineBlock.FCStd` | 36 | 184 | **0.60 s** | 0.57 s | 0.17 s | 137 MB |
| `data/examples/Schenkel.stp` (STEP) | 1 | 409 | **1.33 s** | 1.34 s | 0.98 s | 114–121 MB |

- Run-to-run spread was small (PartDesign 0.47–0.54 s, STEP 1.28–1.36 s), and full and slim agree within 0.03 s.
- **STEP is the slow one:** reopening (modules already loaded) still takes 1 s for 409 faces, so the
  time is in reading and meshing the file, not in startup work.
- The first file opened in a session is much slower (PartDesign: 3.4 s on the full build) because the
  OS file cache is still cold for the modules it loads.
- **A new user can't open a STEP file without a dialog:** every new profile shows a modal "STEP Import Settings"
  dialog on the first STEP open (preference `Mod/Part/STEP/VisibleImportDialog`). The benchmark turns
  it off. To fix in the shell phases.
- On slim, the FEM and BIM example files are correctly rejected as incomplete (their object types
  aren't built), so they aren't in the reference set.

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
| Median start, quiet machine (2026-11-14, alternating full/slim twice) | 1.98 / 1.97 s | **1.83 / 1.88 s** (−6%) |
| Working set / private at ready | 597 / 559 MB | 584 / 542 MB |
| `bin` + `Mod` on disk | 5.3 GB | 4.2 GB |

> **Correction:** an earlier version of this page reported 4.7 s / 537 MB / 1.9 GB private. Those
> runs weren't actually isolated (FreeCAD ignores `FREECAD_USER_*` unless the folders exist) and
> used a profile that test runs had filled up. The numbers above replace them.

## Startup profile (2026-11-14)

`pixi run python tools/bench/profile_startup.py --runs 6` (Phase 2 task 2.1) splits startup into
phases at known lines in FreeCAD's log, which is flushed after every message. Medians of runs 2–6,
same afternoon. "Without PDBs": the slim RelWithDebInfo build with its debug-symbol files moved aside
for the run (an experiment). "Slim Release": `pixi run configure-slim-release` /
`build-slim-release` → `build/slim-release`, the configuration we ship and CI builds:

| Phase (code that runs in it) | Full | Slim | Slim without PDBs | **Slim Release** |
|---|---|---|---|---|
| Process start → first log line (EXE + DLL loading) | 99 ms | 114 ms | 108 ms | 101 ms |
| **Config + crash reporter setup** (`Application::initCrashReporter`) | **420 ms** | **432 ms** | **273 ms** | **271 ms** |
| App init script (`FreeCADInit.py`, every `Init.py`) | 111 ms | 120 ms | 123 ms | 105 ms |
| Qt application, main window, style sheet, OpenGL check | 274 ms | 432 ms | 302 ms | 284 ms |
| Coin3D init + splash | 45 ms | 41 ms | n/a | 42 ms |
| GUI init script (`FreeCADGuiInit.py`, every `InitGui.py`) | 367 ms | 282 ms | 267 ms | 245 ms |
| **Start workbench activation** (Studio's workbench is empty) | 226 ms | 228 ms | 230 ms | 151 ms |
| Window settings, autoloaded modules, migration check | 102 ms | 144 ms | n/a | 100 ms |
| First events after the event loop starts (Start page, f3d thumbnails, …) | 311 ms | 353 ms | n/a | 338 ms |
| Command-line files → idle | 113 ms | 104 ms | n/a | 134 ms |
| **Ready** | **2.10 s** | **2.27 s** | **1.91 s** | **1.79 s** |

The full and slim columns were measured one after the other, not alternated, so their totals carry
batch noise (alternated runs showed slim ~6% faster, see above). The shares are what matter:

- **The crash reporter is the largest single phase.** Upstream's `Base::CrashReporter::Writer::prewarm()`
  takes a stack trace with cpptrace at startup so the stack-walking code is loaded before any crash.
  About 160 ms of it only happens when debug symbols (PDBs) are present, so **RelWithDebInfo
  measurements overstate what users of a Release build see**. The Release build confirms it: 271 ms,
  the same as without PDBs. That remaining ~270 ms is real.
  Candidate: run the prewarm after the window is up (core patch; worth offering upstream).
- **Each module's `Init.py`/`InitGui.py` is cheap, except the first `InitGui.py` that imports shared
  heavy modules.** On the full build AddonManager takes 252 ms; on slim (no AddonManager) Draft takes
  104 ms and Tux 81 ms. Removing modules (the slim build) mostly moves this cost elsewhere.
- **Activating an empty workbench costs ~230 ms**: FreeCAD's generic activation (menus, toolbars,
  command bars), not our code. Relevant to the unified main window (2.6).
- **~300–350 ms go to the first events after the event loop starts**, mostly the Start page and
  its thumbnails (f3d). The file browser (2.8) replaces the Start page.
- Watching the log costs a little CPU. Use `bench_startup.py` for the startup number itself.

### Release build: the numbers budgets are checked against

`bench_startup.py --runs 6`, slim RelWithDebInfo and slim Release alternated twice, quiet machine
(CPU under 15% for 30 s before starting), AC power, "Balanced":

| | Slim RelWithDebInfo | **Slim Release** |
|---|---|---|
| Median start | 2.25 / 2.01 s | **1.75 / 1.72 s** |
| Working set at ready | 584 MB | **394 MB** |
| Private bytes at ready | 540 MB | **361 MB** |

The Release build starts 0.3–0.5 s faster and uses a third less memory. Most of the memory difference
is very likely the crash reporter's prewarm loading debug symbols. **From now on the startup and memory budgets
(PLAN §1.3) are checked on the slim Release build**: 1.72–1.75 s today, so the 1.5 s target needs
about 0.25 s and the 1.0 s stretch goal about 0.75 s. RelWithDebInfo numbers stay useful for comparing
two builds of the same kind.

## Tools

- `tools/test/run_headless_suites.py`: runs suites in a throwaway profile (fails if the profile
  isn't really isolated), with a per-test watchdog that prints every thread's stack instead of hanging.
- `tools/test/run_cam_batches.py`: the CAM suite in batches (see the hang above).
- `tools/test/startup_smoke.py`: launches the real app on a brand-new profile and checks what a new
  user sees.
- `tools/test/run_gui_suites.py`: GUI suites (`FreeCAD.exe -t`) in a throwaway profile, killed on timeout.
- `tools/test/compare_test_logs.py`: diffs two suite logs (missing tests by module, tests that got worse).
- `tools/bench/bench_startup.py`: startup and memory benchmark, also in a throwaway profile.
- `tools/bench/profile_startup.py`: where startup time goes, by phase and by module (`InitGui.py`).
- `tools/bench/bench_open.py`: opens the reference files; stops with an error if any load is incomplete.
  CI runs one pass of it on the slim Release build as a check (timings on a shared runner aren't used).
