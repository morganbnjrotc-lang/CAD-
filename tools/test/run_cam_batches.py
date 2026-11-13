# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run FreeCAD's CAM test suite in batches, so it doesn't hang on Windows.

Usage (from the repo root):
    pixi run python tools/test/run_cam_batches.py [--batch-size 12] [--build-dir build/release]

Why: CAM's tool-asset manager calls asyncio.run() per asset. On Windows every call leaves a
loopback TCP port in TIME_WAIT for ~2 minutes; after ~16k calls the ports run out and CPython's
socketpair fallback blocks forever. Running the suite in batches and waiting for TIME_WAIT to
drain between them avoids that (details: docs/BASELINE.md).
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve().parent / "run_headless_suites.py"
# Widget tests are excluded by CAMTests/__init__.py as well (they need a GUI).
EXCLUDED = {
    "TestPathToolBitBrowserWidget",
    "TestPathToolBitEditorWidget",
    "TestPathToolBitListWidget",
    "TestPathToolBitPropertyEditorWidget",
    "TestPathToolDocumentObjectEditorWidget",
}
MAX_TIME_WAIT = 2000


def time_wait_count() -> int:
    out = subprocess.run(["netstat", "-an"], capture_output=True, text=True).stdout
    return out.count("TIME_WAIT")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=180, help="seconds allowed per test")
    parser.add_argument("--build-dir", type=Path, default=REPO / "build/relWithDebInfo")
    args = parser.parse_args()
    build_dir = args.build_dir.resolve()
    module_list = build_dir / "Mod/CAM/CAMTests/cam_test_modules.py"
    exe = build_dir / "bin" / "FreeCADCmd.exe"

    modules = [
        m for m in re.findall(r'"([A-Za-z0-9_]+)"', module_list.read_text(encoding="utf-8"))
        if m not in EXCLUDED
    ]
    totals = {"ran": 0, "failures": 0, "errors": 0, "skipped": 0}
    worst = 0
    for number, start in enumerate(range(0, len(modules), args.batch_size), 1):
        while time_wait_count() >= MAX_TIME_WAIT:
            time.sleep(10)
        names = ",".join(f"CAMTests.{m}" for m in modules[start : start + args.batch_size])
        log_name = f"cam-batch-{number}.log"
        code = subprocess.run(
            [sys.executable, str(RUNNER), "--exe", str(exe), "--timeout", str(args.timeout), "--log", log_name, names],
            capture_output=True,
        ).returncode
        log = (REPO / "build/test-logs" / log_name).read_text(encoding="utf-8", errors="replace")
        summary = re.findall(r"STUDIO_SUITE_SUMMARY (.*)", log)
        hung = "Timeout (" in log
        print(f"batch {number}: exit={code} hung={hung} {summary[-1] if summary else 'NO SUMMARY'}")
        for key, value in re.findall(r"(\w+)=(\d+)", summary[-1] if summary else ""):
            totals[key] += int(value)
        worst = max(worst, code if summary and not hung else max(code, 1))
    print("CAM total: " + " ".join(f"{k}={v}" for k, v in totals.items()))
    return worst


if __name__ == "__main__":
    sys.exit(main())
