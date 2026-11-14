# SPDX-License-Identifier: LGPL-2.1-or-later
"""Reference-file benchmark: time to open the reference models the way File > Open does.

Usage (from the repo root):
    pixi run python tools/bench/bench_open.py [--runs 6] [--exe build/relWithDebInfo/bin/FreeCAD.exe]
                                              [--label TEXT] [file ...]

Each run starts FreeCAD in a fresh throwaway profile, waits until it's idle, then opens one file
and waits until the app is idle again with the document shown ("open": what a user waits for
after starting the app, including loading the modules the file needs). It then closes the
document and opens it again in the same process ("reopen": modules already loaded, so mostly the
cost of the file itself). Files take turns run by run, so drift (heat, background work) hits them
equally. As in bench_startup.py, the first run of each file is reported on its own and the rest by
median.

A load only counts if it was complete: a FreeCAD file must come back with every object it was
saved with and every object's Python code, and every file must have geometry. A broken load opens
faster, so it would otherwise look like a speed-up. The benchmark stops with exit code 1 at the
first incomplete load. Results are appended to build/bench/open.jsonl.
"""

import argparse
import datetime
import json
import statistics
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from benchlib import run_probe

REPO = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parent / "_open_probe.py"
TIMEOUT_S = 300

# docs/PLAN.md §1.3. Paths relative to the repo; tracked in git so they can't change unnoticed.
REFERENCE_FILES = (
    "data/examples/PartDesignExample.FCStd",  # PartDesign body and sketches
    "data/examples/AssemblyExample.FCStd",  # assembly, joints are Python objects
    "data/examples/EngineBlock.FCStd",  # Part features and Draft (Python) objects
    "data/examples/Schenkel.stp",  # STEP import with colors
)


def expected_objects(path: Path):
    """Number of objects a FreeCAD file was saved with; None for other formats."""
    if path.suffix.lower() != ".fcstd":
        return None
    with zipfile.ZipFile(path) as archive:
        document = ElementTree.fromstring(archive.read("Document.xml"))
    return int(document.find("Objects").get("Count"))


def load_problems(report: dict, expected_objects) -> list:
    """Why a probe's load doesn't count; [] if it was complete."""
    if "error" in report:
        return [report["error"]]
    problems = []
    if expected_objects is not None and report["objects"] != expected_objects:
        problems.append(
            f"{report['objects']} of {expected_objects} saved objects loaded "
            "(object types this build doesn't have?)"
        )
    missing = report["missing_proxies"]
    if missing:
        shown = ", ".join(missing[:5]) + (", ..." if len(missing) > 5 else "")
        problems.append(f"{len(missing)} objects lost their Python code (module not importable): {shown}")
    if not report["faces"]:
        problems.append("no geometry: the document has 0 faces")
    return problems


def run_once(exe: Path, path: Path) -> dict:
    report = run_probe(exe, PROBE, {"STUDIO_BENCH_FILE": str(path)}, TIMEOUT_S)
    if "error" not in report and report.get("memory_before_open"):
        before, after = report["memory_before_open"], report["memory_after_open"]
        report["private_delta_mb"] = after["private_mb"] - before["private_mb"]
    return report


def summarize(name: str, runs: list) -> dict:
    first, rest = runs[0], runs[1:] or runs

    def median(key):
        values = [r[key] for r in rest if r.get(key) is not None]
        return round(statistics.median(values), 3) if values else None

    return {
        "file": name,
        "objects": first["objects"],
        "faces": first["faces"],
        "first_open_s": round(first["open_s"], 3),
        "median_open_s": median("open_s"),
        "median_reopen_s": median("reopen_s"),
        "median_private_delta_mb": median("private_delta_mb"),
        "all": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=6)
    parser.add_argument("--exe", type=Path, default=REPO / "build/relWithDebInfo/bin/FreeCAD.exe")
    parser.add_argument("--label", default="", help="free-text tag stored with the result")
    parser.add_argument("files", nargs="*", default=REFERENCE_FILES, help="default: the reference set")
    args = parser.parse_args()

    files = [(name, (REPO / name).resolve()) for name in args.files]
    runs = {name: [] for name, _ in files}
    for run in range(1, args.runs + 1):
        for name, path in files:
            report = run_once(args.exe, path)
            problems = load_problems(report, expected_objects(path))
            if problems:
                print(f"FAIL {name} (run {run}): incomplete load, not timed", file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                return 1
            runs[name].append(report)
            print(f"run {run}/{args.runs}  {name}: open {report['open_s']:.2f} s, reopen {report['reopen_s']:.2f} s")

    summary = {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "exe": str(args.exe),
        "runs": args.runs,
        "files": [summarize(name, runs[name]) for name, _ in files],
    }
    out_dir = REPO / "build" / "bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "open.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")

    rest = max(args.runs - 1, 1)
    print(f"\n{'file':<42} {'objects':>7} {'faces':>6} {'first':>7} {'open':>7} {'reopen':>7} {'+private':>9}")
    for s in summary["files"]:
        delta = s["median_private_delta_mb"]
        print(
            f"{s['file']:<42} {s['objects']:>7} {s['faces']:>6} {s['first_open_s']:>6.2f}s "
            f"{s['median_open_s']:>6.2f}s {s['median_reopen_s']:>6.2f}s "
            + (f"{delta:>7.0f}MB" if delta is not None else f"{'n/a':>9}")
        )
    print(f"(open, reopen and +private are medians of {rest} run(s){' after the first' if args.runs > 1 else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
