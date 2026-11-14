# SPDX-License-Identifier: LGPL-2.1-or-later
"""End-to-end startup check: launch the real app on brand-new profiles and verify what a new user
would see.

Usage (from the repo root):
    pixi run python tools/test/startup_smoke.py [--build-dir build/release]

Starts the app twice (RUNS):
  lazy  with background warm-up off: startup itself must load none of the command catalog's
        workbenches (docs/adr/0007), checked once startup has settled;
  warm  as a new user gets it: warm-up must then load its plan (the cheap workbenches), never CAM,
        without switching workbench.
Both: the Studio workbench is active and no dialog is waiting. Unit tests check pieces; this checks
the assembled app actually starts the way we intend. Exit code 0 = pass.
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

RUNS = (
    ("lazy", {"BaseApp/Preferences/Mod/Studio/Commands/WarmUp": False}),
    ("warm", {}),
)

EXPECTED = {
    "active_workbench": "StudioWorkbench",
    # Nothing waiting for a click in front of a new user. The profile has the OpenGL 1.x warning
    # dismissed (a hardware warning, shown on GPU-less CI runners), so any dialog here is ours or
    # a first-run dialog from upstream.
    "dialogs": [],
}


def failures(mode: str, state: dict, profile_dir: Path) -> dict:
    """{check: (expected, got)} for every check the reported app state fails; {} = pass."""
    found = {k: (v, state.get(k)) for k, v in EXPECTED.items() if state.get(k) != v}
    user_cfg = state.get("user_parameter_file") or ""
    if not (user_cfg and Path(user_cfg).resolve().is_relative_to(profile_dir.resolve())):
        found["user_parameter_file"] = ("inside the throwaway profile", user_cfg)
    if mode == "lazy":
        if state.get("early_commands") != []:
            found["early_commands"] = ([], state.get("early_commands"))
    else:
        warmup = state.get("warmup") or {}
        if not warmup.get("done"):
            found["warmup.done"] = (True, warmup.get("done"))
        if warmup.get("failed"):
            found["warmup.failed"] = ([], warmup.get("failed"))
        if not warmup.get("planned") or warmup.get("loaded") != warmup.get("planned"):
            found["warmup.loaded"] = (warmup.get("planned") or "a non-empty plan", warmup.get("loaded"))
        if state.get("cam_loaded") is not False:
            found["cam_loaded"] = (False, state.get("cam_loaded"))
    return found


def run(exe: Path, mode: str, settings: dict):
    with tempfile.TemporaryDirectory(prefix="studio-smoke-") as tmp:
        tmp = Path(tmp)
        out = tmp / "state.json"
        env = dict(os.environ)
        env.update(make_profile(tmp, settings), STUDIO_SMOKE_OUT=str(out), STUDIO_SMOKE_MODE=mode)
        subprocess.run([str(exe), str(PROBE)], env=env, timeout=180, capture_output=True)
        if not out.exists():
            return None, {"report": ("app state", "none: crashed or hung during startup")}
        state = json.loads(out.read_text(encoding="utf-8"))
        return state, failures(mode, state, tmp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", type=Path, default=REPO / "build/relWithDebInfo")
    args = parser.parse_args()
    exe = args.build_dir.resolve() / "bin" / "FreeCAD.exe"

    total = 0
    for mode, settings in RUNS:
        state, failed = run(exe, mode, settings)
        print(f"=== {mode}")
        if state is not None:
            print(json.dumps(state, indent=2))
        for key, (want, got) in failed.items():
            print(f"FAIL: {mode}: {key}: expected {want!r}, got {got!r}")
        total += len(failed)
    print("PASS" if not total else f"{total} check(s) failed")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
