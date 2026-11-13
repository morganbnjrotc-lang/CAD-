# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run FreeCAD GUI test suites (`FreeCAD.exe -t`) in an isolated profile, with an overall timeout.

Usage (from the repo root):
    pixi run python tools/test/run_gui_suites.py                          # TestStudioGui
    pixi run python tools/test/run_gui_suites.py TestStudioGui --build-dir build/release

Why not just `FreeCAD.exe -t TestStudioGui`?
  * Isolation: a bare run uses the real profile. When the dev build's profile folder doesn't exist
    yet but an older FreeCAD's does (e.g. an installed FreeCAD 1.1), FreeCAD opens the modal
    "Welcome to FreeCAD" settings-migration dialog and the tests wait forever behind it.
    FreeCAD skips that dialog when FREECAD_USER_HOME/DATA/TEMP are set, which also keeps the run
    from reading or changing the developer's settings.
  * Hang protection: if the app hasn't exited after --timeout seconds it is killed and the run fails.

Output goes to stdout and to build/test-logs/<suites>.log. Exit code 0 only if every test passed.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("suites", nargs="*", default=["TestStudioGui"], help="GUI test module names")
    parser.add_argument("--build-dir", type=Path, default=REPO / "build/relWithDebInfo")
    parser.add_argument("--timeout", type=int, default=600, help="seconds allowed for the whole run")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="backslashreplace")

    exe = args.build_dir.resolve() / "bin" / "FreeCAD.exe"
    suites = ",".join(args.suites)
    log_dir = REPO / "build" / "test-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / (suites.replace(",", "+") + ".log")

    with tempfile.TemporaryDirectory(prefix="studio-gui-test-") as tmp:
        # FreeCAD silently ignores FREECAD_USER_* unless the folders already exist
        for sub in ("home", "data", "temp"):
            (Path(tmp) / sub).mkdir()
        env = dict(os.environ)
        env.update(
            FREECAD_USER_HOME=str(Path(tmp) / "home"),
            FREECAD_USER_DATA=str(Path(tmp) / "data"),
            FREECAD_USER_TEMP=str(Path(tmp) / "temp"),
        )
        try:
            proc = subprocess.run(
                [str(exe), "-t", suites],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=args.timeout,
            )
            output, code = proc.stdout, proc.returncode
        except subprocess.TimeoutExpired as hung:
            output = hung.output or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            output += (
                f"\nERROR: FreeCAD did not exit within {args.timeout} s and was killed"
                " (a test hung, or a dialog is waiting for input).\n"
            )
            code = 124

    sys.stdout.write(output)
    log_path.write_text(output, encoding="utf-8", errors="replace")
    print(f"\nlog: {log_path}\nexit code: {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
