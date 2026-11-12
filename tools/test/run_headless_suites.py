# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run FreeCAD's headless Python test suites in an isolated profile, with a per-test watchdog.

Usage (from the repo root):
    pixi run python tools/test/run_headless_suites.py                    # every registered suite
    pixi run python tools/test/run_headless_suites.py TestStudioApp      # one or more suites
    pixi run python tools/test/run_headless_suites.py --timeout 120 TestPartDesignApp

Why not just `FreeCADCmd -t 0`?
  * Isolation: FreeCAD's user home, data and temp folders point to a throwaway directory, so the
    run neither reads nor changes the developer's settings, and can't contend for lock files with
    another FreeCAD that is open at the same time.
  * Hang protection: if one test runs longer than --timeout seconds, every thread's stack is
    printed and the run stops, instead of the suite silently waiting forever.

Output goes to stdout and to build/test-logs/<name>.log. The exit code is 0 only if every test passed.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve().parent / "_suite_runner.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("suites", nargs="*", help="test module names (default: all registered)")
    parser.add_argument("--timeout", type=int, default=300, help="seconds allowed per test")
    parser.add_argument("--exe", type=Path, default=REPO / "build/relWithDebInfo/bin/FreeCADCmd.exe")
    parser.add_argument("--log", default=None, help="log file name under build/test-logs/")
    parser.add_argument(
        "--exclude", default="", help="comma-separated suites to skip when running all"
    )
    args = parser.parse_args()
    # The Windows console is often cp1252; FreeCAD output can contain any Unicode character.
    sys.stdout.reconfigure(errors="backslashreplace")

    suites =",".join(args.suites) if args.suites else "0"
    log_dir = REPO / "build" / "test-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / (args.log or ("all" if suites == "0" else suites.replace(",", "+")) + ".log")

    with tempfile.TemporaryDirectory(prefix="studio-test-") as tmp:
        # FreeCAD silently ignores FREECAD_USER_* unless the folders already exist
        for sub in ("home", "data", "temp"):
            (Path(tmp) / sub).mkdir()
        env = dict(os.environ)
        env.update(
            STUDIO_SUITES=suites,
            STUDIO_SUITES_EXCLUDE=args.exclude,
            STUDIO_TEST_TIMEOUT=str(args.timeout),
            FREECAD_USER_HOME=str(Path(tmp) / "home"),
            FREECAD_USER_DATA=str(Path(tmp) / "data"),
            FREECAD_USER_TEMP=str(Path(tmp) / "temp"),
        )
        with open(log_path, "w", encoding="utf-8", errors="replace") as log:
            proc = subprocess.Popen(
                [str(args.exe), str(RUNNER)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            isolated = False
            for line in proc.stdout:
                sys.stdout.write(line)
                log.write(line)
                if line.startswith("STUDIO_USER_PARAMETER "):
                    used = Path(line.split(" ", 1)[1].strip()).resolve()
                    isolated = used.is_relative_to(Path(tmp).resolve())
            code = proc.wait()
        if not isolated:
            print("\nERROR: FreeCAD did not use the throwaway profile; results may depend on your settings.")
            code = code or 2

    print(f"\nlog: {log_path}\nexit code: {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
