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
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parent / "_startup_probe.py"
TIMEOUT_S = 180


def _kill_leftover_probes() -> None:
    if sys.platform != "win32":
        return
    subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='FreeCAD.exe'\" | "
            "Where-Object { $_.CommandLine -like '*_startup_probe.py*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
        ],
        check=False,
        capture_output=True,
    )


def run_once(exe: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="studio-bench-") as tmp:
        tmp = Path(tmp)
        out = tmp / "result.json"
        env = dict(os.environ)
        # Isolate home, data AND temp: FreeCAD keeps lock files in its temp cache, and sharing it
        # with another running FreeCAD (e.g. a test run) can make that process wait forever.
        # FreeCAD silently ignores these variables unless the folders already exist.
        for sub in ("home", "data", "temp"):
            (tmp / sub).mkdir()
        env.update(
            STUDIO_BENCH_OUT=str(out),
            FREECAD_USER_HOME=str(tmp / "home"),
            FREECAD_USER_DATA=str(tmp / "data"),
            FREECAD_USER_TEMP=str(tmp / "temp"),
        )
        log = tmp / "freecad.log"
        start = time.time()
        try:
            proc = subprocess.run(
                [str(exe), "--log-file", str(log), str(PROBE)],
                env=env,
                timeout=TIMEOUT_S,
                capture_output=True,
                text=True,
            )
        finally:
            # FreeCAD can relaunch itself as a detached process (e.g. one-time first-run setup);
            # that copy outlives `proc`, so close anything still running our probe.
            _kill_leftover_probes()
        if not out.exists():
            tail = log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else ""
            raise RuntimeError(
                f"probe did not report (exit code {proc.returncode})\n"
                f"--- stdout/stderr ---\n{(proc.stdout + proc.stderr)[-2000:]}\n"
                f"--- FreeCAD log ---\n{tail}"
            )
        data = json.loads(out.read_text(encoding="utf-8"))
        return {
            "startup_s": data["ready"] - start,
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
