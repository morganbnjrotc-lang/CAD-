# SPDX-License-Identifier: LGPL-2.1-or-later
"""End-to-end startup check: launch the real app on a brand-new profile and verify what a new
user would see.

Usage (from the repo root):
    pixi run python tools/test/startup_smoke.py [--build-dir build/release]

Unit tests check pieces; this checks the assembled app actually starts the way we intend. Exit code 0 = pass.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).resolve().parent / "_startup_smoke_probe.py"

EXPECTED = {
    "active_workbench": "StudioWorkbench",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", type=Path, default=REPO / "build/relWithDebInfo")
    args = parser.parse_args()
    exe = args.build_dir.resolve() / "bin" / "FreeCAD.exe"

    with tempfile.TemporaryDirectory(prefix="studio-smoke-") as tmp:
        tmp = Path(tmp)
        out = tmp / "state.json"
        # FreeCAD silently ignores FREECAD_USER_* unless the folders already exist
        for sub in ("home", "data", "temp"):
            (tmp / sub).mkdir()
        env = dict(os.environ)
        env.update(
            STUDIO_SMOKE_OUT=str(out),
            FREECAD_USER_HOME=str(tmp / "home"),
            FREECAD_USER_DATA=str(tmp / "data"),
            FREECAD_USER_TEMP=str(tmp / "temp"),
        )
        subprocess.run([str(exe), str(PROBE)], env=env, timeout=180, capture_output=True)
        if not out.exists():
            print("FAIL: app did not report its state (crashed or hung during startup)")
            return 1
        state = json.loads(out.read_text(encoding="utf-8"))
        profile_isolated = Path(state.get("user_parameter_file", "")).resolve().is_relative_to(
            tmp.resolve()
        )

    failures = {k: (v, state.get(k)) for k, v in EXPECTED.items() if state.get(k) != v}
    if not profile_isolated:
        failures["user_parameter_file"] = ("inside the throwaway profile", state.get("user_parameter_file"))
    print(json.dumps(state, indent=2))
    for key, (want, got) in failures.items():
        print(f"FAIL: {key}: expected {want!r}, got {got!r}")
    print("PASS" if not failures else f"{len(failures)} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
