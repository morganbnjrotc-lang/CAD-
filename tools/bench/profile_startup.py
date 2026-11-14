# SPDX-License-Identifier: LGPL-2.1-or-later
"""Startup profile: where the time goes between launching the app and a usable window.

Usage (from the repo root):
    pixi run python tools/bench/profile_startup.py [--runs 5] [--exe build/slim/bin/FreeCAD.exe]
                                                   [--label TEXT]

Each run starts FreeCAD in a fresh throwaway profile (as bench_startup.py does) and stamps every
line of FreeCAD's log as it is written: FreeCAD flushes the log after each message. Startup is then
split into phases at known log lines, from launch to the moment the app is idle with its main
window ready, and each module's InitGui.py gets the time since the module before it.

FreeCAD's embedded Python runs in isolated mode, so PYTHONPROFILEIMPORTTIME and friends are
ignored; the log is the only view in that needs no change to FreeCAD.

A phase whose closing log line is missing (reworded by an upstream merge?) is reported as unknown,
and its time goes to the next phase that can be measured, so the phases still add up to the total.
Watching the log costs a little CPU; use bench_startup.py for the startup number itself. Results
are appended to build/bench/startup_profile.jsonl.
"""

import argparse
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

from benchlib import run_probe

REPO = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parent / "_startup_probe.py"
TIMEOUT_S = 180

# (phase, pattern of the log line that ends it), in startup order. What runs in each phase is in
# src/App/Application.cpp (init) and src/Gui/StartupProcess.cpp (StartupPostProcess::execute).
PHASES = (
    ("process start → first log line", r"Msg: FreeCAD \d"),
    ("config + crash reporter setup", r"Log: Create Application$"),
    ("App init script (FreeCADInit.py)", r"Log: Using .* as module path!$"),
    ("Qt application + OpenGL check", r"Log: OpenGL version is"),
    ("main window + splash", r"Log: Run Gui init script$"),
    ("GUI init script (all InitGui.py)", r"Log: Init: Running FreeCADGuiInit\.py start script\.\.\. done$"),
    ("between GUI init and workbench", r"Log: Init: Activating default workbench"),
    ("start workbench activation", r"Log: Init: Showing main window$"),
    ("show main window", r"Log: Init: Entering event loop$"),
    ("first events (Start page, …)", r"Log: Init: Processing command line files$"),
)
READY_PHASE = "command-line files → idle"

_GUI_INIT_START = re.compile(r"Log: Run Gui init script$")
_GUI_INIT_SEARCH = re.compile(r"Log: Init:\s+Searching modules$")
_GUI_INIT_END = re.compile(PHASES[5][1])
# "Init:      Initializing C:\...\Mod\Part... done", "... (InitGui.py not found)... ignore",
# "Init: Initializing freecad.Addon... done"
_MODULE_DONE = re.compile(
    r"Log: Init:\s+Initializing (?:.*[\\/])?(?P<name>[^\\/ ]+?)(?: \(InitGui\.py not found\))?\.\.\. (?:done|ignore)$"
)


def _clean(line: str) -> str:
    return line.lstrip("\ufeff")


def split_phases(log: list, ready: float) -> list:
    """[(phase, seconds or None)] for one run. `log` is [(seconds since launch, line)] and `ready`
    is when the app went idle. A phase is None if its closing line wasn't found."""
    phases, last, index = [], 0.0, 0
    for name, pattern in PHASES:
        regex = re.compile(pattern)
        for i in range(index, len(log)):
            t, line = log[i]
            if regex.match(_clean(line)):
                phases.append((name, t - last))
                last, index = t, i + 1
                break
        else:
            phases.append((name, None))
    phases.append((READY_PHASE, ready - last))
    return phases


def initgui_times(log: list) -> list:
    """[(module, seconds)] for each module's InitGui.py, in load order. A module gets the time
    since the module before it (the first one: since the search for modules started)."""
    times, last, inside = [], None, False
    for t, line in log:
        line = _clean(line)
        if not inside:
            inside = bool(_GUI_INIT_START.match(line))
            last = t
            continue
        if _GUI_INIT_END.match(line):
            break
        if _GUI_INIT_SEARCH.match(line):
            last = t
        elif match := _MODULE_DONE.match(line):
            times.append((match["name"], t - last))
            last = t
    return times


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--exe", type=Path, default=REPO / "build/relWithDebInfo/bin/FreeCAD.exe")
    parser.add_argument("--label", default="", help="free-text tag stored with the result")
    parser.add_argument("--top", type=int, default=8, help="how many InitGui.py modules to list")
    args = parser.parse_args()

    runs = []
    for run in range(1, args.runs + 1):
        data = run_probe(args.exe, PROBE, {}, TIMEOUT_S, tail=True)
        ready = data["ready"] - data["launched"]
        runs.append(
            {
                "ready_s": ready,
                "phases": split_phases(data["log"], ready),
                "initgui": initgui_times(data["log"]),
            }
        )
        print(f"run {run}/{args.runs}: ready after {ready:.2f} s")

    # The first start of a session pays for a cold OS file cache; like bench_startup.py, report
    # the median of the runs after it.
    rest = runs[1:] or runs
    ready = _median(r["ready_s"] for r in rest)
    phase_names = [name for name, _ in rest[0]["phases"]]
    phases = {name: _median(dict(r["phases"])[name] for r in rest) for name in phase_names}
    modules = {}
    for r in rest:
        for name, seconds in r["initgui"]:
            modules.setdefault(name, []).append(seconds)
    module_medians = sorted(((n, _median(s)) for n, s in modules.items()), key=lambda m: -m[1])

    print(f"\n{'phase':<36} {'median':>8} {'share':>6}")
    for name, seconds in phases.items():
        if seconds is None:
            print(f"{name:<36} {'unknown':>8}   (closing log line not found: reworded upstream?)")
        else:
            print(f"{name:<36} {seconds * 1000:>6.0f} ms {seconds / ready:>5.0%}")
    print(f"{'ready (median)':<36} {ready * 1000:>6.0f} ms")
    print(f"(medians of {len(rest)} run(s){' after the first' if len(runs) > 1 else ''};"
          " phase medians need not add up exactly)")
    print(f"\nslowest InitGui.py (of {len(module_medians)}):")
    for name, seconds in module_medians[: args.top]:
        print(f"  {seconds * 1000:6.0f} ms  {name}")

    out_dir = REPO / "build" / "bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "exe": str(args.exe),
        "runs": args.runs,
        "median_ready_s": ready,
        "median_phases_s": phases,
        "median_initgui_s": dict(module_medians),
        "all": runs,
    }
    with open(out_dir / "startup_profile.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
