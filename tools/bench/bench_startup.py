# SPDX-License-Identifier: LGPL-2.1-or-later
"""Startup benchmark: time from process launch to an idle, usable main window, plus memory.

Usage (from the repo root):
    pixi run python tools/bench/bench_startup.py [--runs 5] [--exe build/relWithDebInfo/bin/FreeCAD.exe]

Each run uses a fresh, throwaway FreeCAD user profile so results don't depend on (or modify) the
developer's own settings. The first run is reported separately as "first" (cold-ish: OS file cache
may already be warm, so a true cold start needs a reboot); the rest are summarized by median.
Results are appended to build/bench/startup.jsonl.
"""

import argparse
import datetime
import json
import statistics
import sys
from pathlib import Path

from benchlib import run_probe

REPO = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parent / "_startup_probe.py"
TIMEOUT_S = 180


def run_once(exe: Path) -> dict:
    data = run_probe(exe, PROBE, {}, TIMEOUT_S)
    return {
        "startup_s": data["ready"] - data["launched"],
        "working_set_mb": data.get("working_set_mb"),
        "private_mb": data.get("private_mb"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--exe", type=Path, default=REPO / "build/relWithDebInfo/bin/FreeCAD.exe")
    parser.add_argument("--label", default="", help="free-text tag stored with the result")
    args = parser.parse_args()

    runs = [run_once(args.exe) for _ in range(args.runs)]
    first, rest = runs[0], runs[1:] or runs

    def median(key):
        return statistics.median(r[key] for r in rest)

    summary = {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "exe": str(args.exe),
        "runs": args.runs,
        "first_startup_s": round(first["startup_s"], 3),
        "median_startup_s": round(median("startup_s"), 3),
        "median_working_set_mb": round(median("working_set_mb"), 1),
        "median_private_mb": round(median("private_mb"), 1),
        "all": runs,
    }
    out_dir = REPO / "build" / "bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "startup.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")

    print(
        f"first start   : {summary['first_startup_s']:.2f} s\n"
        f"median start  : {summary['median_startup_s']:.2f} s  (of {len(rest)} runs)\n"
        f"working set   : {summary['median_working_set_mb']:.0f} MB\n"
        f"private bytes : {summary['median_private_mb']:.0f} MB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
