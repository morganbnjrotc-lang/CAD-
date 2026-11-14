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

sys.path.insert(0, str(REPO / "tools" / "bench"))
from benchlib import make_profile  # noqa: E402  (shared throwaway profile)

EXPECTED = {
    "active_workbench": "StudioWorkbench",
    # Nothing waiting for a click in front of a new user. The profile has the OpenGL 1.x warning
    # dismissed (a hardware warning, shown on GPU-less CI runners), so any dialog here is ours or
    # a first-run dialog from upstream.
    "dialogs": [],
}


def failures(state: dict, profile_dir: Path) -> dict:
    """{check: (expected, got)} for every check the reported app state fails; {} = pass."""
    found = {k: (v, state.get(k)) for k, v in EXPECTED.items() if state.get(k) != v}
    user_cfg = state.get("user_parameter_file") or ""
    if not (user_cfg and Path(user_cfg).resolve().is_relative_to(profile_dir.resolve())):
        found["user_parameter_file"] = ("inside the throwaway profile", user_cfg)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", type=Path, default=REPO / "build/relWithDebInfo")
    args = parser.parse_args()
    exe = args.build_dir.resolve() / "bin" / "FreeCAD.exe"

    with tempfile.TemporaryDirectory(prefix="studio-smoke-") as tmp:
        tmp = Path(tmp)
        out = tmp / "state.json"
        env = dict(os.environ)
        env.update(make_profile(tmp), STUDIO_SMOKE_OUT=str(out))
        subprocess.run([str(exe), str(PROBE)], env=env, timeout=180, capture_output=True)
        if not out.exists():
            print("FAIL: app did not report its state (crashed or hung during startup)")
            return 1
        state = json.loads(out.read_text(encoding="utf-8"))
        failed = failures(state, tmp)

    print(json.dumps(state, indent=2))
    for key, (want, got) in failed.items():
        print(f"FAIL: {key}: expected {want!r}, got {got!r}")
    print("PASS" if not failed else f"{len(failed)} check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
