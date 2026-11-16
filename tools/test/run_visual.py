# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's visual baselines (PLAN 2.10): captures the main screens and compares them with the reviewed
pictures in tests/visual/baselines/studio.

Usage (from the repo root):
    pixi run python tools/test/run_visual.py                     # compare (slim Release build)
    pixi run python tools/test/run_visual.py --update            # write new baselines, then review them
    pixi run python tools/test/run_visual.py --build-dir build/relWithDebInfo

Screens: Home, a model with a face selected, a sketch being edited; each in light and dark (a fresh
profile per mode). The 3D view is masked (OpenGL drawing differs between graphics cards; its colors
are checked by the theme tests), except the Tasks panel floating over it. To keep pictures the same across machines: a fixed 1280 x 800 window
with the mouse pointer off it (no hover), the vendored Noto Sans drawn by FreeType instead of the system font, no
high-DPI scaling and text and Qt's sizes at 96 DPI (100 %) whatever the display's scaling (checked: a 125 % display
pinned at 96 DPI draws Home pixel for pixel as GitHub's runner, which is at 100 %), the example files
copied with fixed "saved 3 days ago" dates, status messages cleared. On a mismatch the actual picture
and a diff (differing pixels in magenta) go to build/test-logs/visual. Exit code 0 only if all match.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "bench"))
sys.path.insert(0, str(REPO / "tools" / "test"))

from benchlib import run_probe  # noqa: E402
import visual_compare  # noqa: E402

BASELINES = REPO / "tests" / "visual" / "baselines" / "studio"
LOGS = REPO / "build" / "test-logs" / "visual"
EXAMPLES = REPO / "data" / "examples"
FONT = REPO / "tests" / "visual" / "fonts" / "NotoSans-Regular.ttf"  # the same text everywhere
RECENT = ("PartDesignExample.FCStd", "EngineBlock.FCStd", "AssemblyExample.FCStd", "Schenkel.stp")
SCREENS = ("home", "model", "sketch")
MODES = ("light", "dark")
ENV = {
    "QT_QPA_PLATFORM": "windows:fontengine=freetype",  # the same text on every Windows machine
    "QT_ENABLE_HIGHDPI_SCALING": "0",
    "QT_FONT_DPI": "96",  # the same text and sizes at any display scaling (see the top)
}


def capture(exe: Path, mode: str, out: Path) -> dict:
    """Runs the probe on a fresh profile in `mode`; FreeCAD's log goes to build/test-logs/visual."""
    with tempfile.TemporaryDirectory(prefix="studio-visual-files-") as files:
        files = Path(files)
        saved = time.time() - 3 * 86400  # Home says "Saved 3 days ago"
        for name in RECENT:
            shutil.copy(EXAMPLES / name, files / name)
            os.utime(files / name, (saved, saved))
        settings = {f"BaseApp/Preferences/RecentFiles/MRU{i}": (files / n).as_posix() for i, n in enumerate(RECENT)}
        settings["BaseApp/Preferences/Mod/Studio/Appearance/Mode"] = mode
        settings["BaseApp/Preferences/Mod/Studio/Commands/WarmUp"] = False  # no background loading meanwhile
        env = dict(ENV, STUDIO_VISUAL_OUT=str(out), STUDIO_VISUAL_MODEL=str(files / RECENT[0]),
                   STUDIO_VISUAL_FONT=str(FONT))
        return run_probe(exe, REPO / "tools" / "test" / "_visual_probe.py", env, 180, settings=settings,
                         keep_log=LOGS / f"{mode}-freecad.log")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", type=Path, default=REPO / "build" / "slim-release")
    parser.add_argument("--update", action="store_true", help="write the captures as the new baselines")
    args = parser.parse_args()
    exe = args.build_dir.resolve() / "bin" / "FreeCAD.exe"
    failures = []
    shutil.rmtree(LOGS, ignore_errors=True)
    for mode in MODES:
        with tempfile.TemporaryDirectory(prefix="studio-visual-") as out:
            out = Path(out)
            try:
                report = capture(exe, mode, out)
            except RuntimeError as problem:  # FreeCAD crashed or hung; its log is in LOGS
                failures.append(f"{mode}: the capture failed: {str(problem).splitlines()[0]}")
                print(f"{mode}: capture failed\n{problem}")
                continue
            masks = json.loads((out / "masks.json").read_text(encoding="utf-8"))
            print(f"{mode}: window {report.get('geometry')}, screens {report['screens']}")
            for screen in SCREENS:
                name = f"{screen}-{mode}"
                actual_path = out / f"{screen}.png"
                if args.update:
                    BASELINES.mkdir(parents=True, exist_ok=True)
                    shutil.copy(actual_path, BASELINES / f"{name}.png")
                    print(f"  {name}: baseline written")
                    continue
                baseline = BASELINES / f"{name}.png"
                if not baseline.exists():
                    failures.append(f"{name}: no baseline (run with --update and review it)")
                    continue
                actual = visual_compare.load(actual_path)
                areas = masks.get(screen, {})
                result = visual_compare.compare(actual, visual_compare.load(baseline), areas.get("mask", []),
                                                areas.get("keep", []))
                print(f"  {name}: {'ok' if result.ok else 'DIFFERS'} ({result.mismatch_pct:.3f} % of pixels)")
                if not result.ok:
                    LOGS.mkdir(parents=True, exist_ok=True)
                    shutil.copy(actual_path, LOGS / f"{name}-actual.png")
                    if result.diff is not None:
                        visual_compare.save(result.diff, LOGS / f"{name}-diff.png")
                    failures.append(f"{name}: {result.reason}")
    if failures:
        print("\nFAILED:\n  " + "\n  ".join(failures) + f"\nactual and diff pictures: {LOGS}")
        return 1
    print("\nOK" if not args.update else f"\nbaselines written to {BASELINES}: review them before committing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
