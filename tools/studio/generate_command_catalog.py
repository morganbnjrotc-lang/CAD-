# SPDX-License-Identifier: LGPL-2.1-or-later
"""Generates Studio's command catalog (docs/adr/0007-lazy-loading-command-catalog.md) from a build.

Usage (from the repo root):
    pixi run python tools/studio/generate_command_catalog.py [--exe build/slim-release/bin/FreeCAD.exe]
                                                            [--check]

For each catalog workbench, starts FreeCAD in a fresh throwaway profile set to English, records
the commands available from startup, activates that one workbench and records the commands its
loading registered: loading it on a command's first use is what makes those commands exist. A
command several workbenches register belongs to the one its name prefix names (assign_owners).
Each command gets its menu text, tooltip, shortcut and the source SVG of its icon, searched under
src/ (its own module first). Writes src/Mod/Studio/studio/services/command_catalog.json.

--check compares with the shipped catalog instead and exits 1 when it is out of date, e.g. after
an upstream merge renamed or added a command: regenerate, review the diff, commit.
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "bench"))

from benchlib import run_probe  # noqa: E402

PROBE = Path(__file__).resolve().parent / "_catalog_probe.py"
CATALOG = REPO / "src" / "Mod" / "Studio" / "studio" / "services" / "command_catalog.json"
TIMEOUT_S = 300

# The workbenches the unified environment draws commands from, in warm-up order (ADR 0007).
WORKBENCHES = (
    "SketcherWorkbench",
    "PartDesignWorkbench",
    "PartWorkbench",
    "AssemblyWorkbench",
    "TechDrawWorkbench",
    "CAMWorkbench",
    "SpreadsheetWorkbench",
)
FIELDS = ("workbench", "menu_text", "tooltip", "shortcut", "icon")
# FreeCAD's commands for testing FreeCAD itself (Std_Test1 "Test1" on Ctrl+T, progress bars, MDI
# tests): not user tools, so they stay out of the palette and the keymap.
DEVELOPER_COMMANDS = re.compile(r"Std_(MDI)?Test")


class IconIndex:
    """Every SVG in an icons folder under `src`, by file name without extension."""

    def __init__(self, src: Path):
        self._by_name = {}
        base = src.parent
        for path in sorted(src.rglob("*.svg")):
            if "icons" in (part.lower() for part in path.relative_to(src).parts[:-1]):
                self._by_name.setdefault(path.stem, []).append(path.relative_to(base).as_posix())

    def find(self, pixmap: str, module: str | None):
        """Repo-relative path of the SVG for a command's `pixmap`, preferring its own module."""
        name = pixmap.replace("\\", "/").rsplit("/", 1)[-1]  # resource path, file path or bare name
        for extension in (".svg", ".png", ".xpm"):
            name = name.removesuffix(extension)
        candidates = self._by_name.get(name, []) if name else []
        if not candidates:
            return None
        preferred = f"src/Mod/{module}/" if module else "src/Gui/"
        return next((c for c in candidates if c.startswith(preferred)), candidates[0])


def _module(workbench: str | None):
    return workbench.removesuffix("Workbench") if workbench else None


def startup_problems(run: dict) -> list:
    """Why a probe run can't be trusted. If Studio's InitGui.py fails, the app starts in FreeCAD's
    empty workbench and reports commands without their shortcuts (only a workbench's menus give
    actions their keys), so the catalog would come out wrong without any error."""
    start = run.get("start_workbench")
    if start != "StudioWorkbench":
        return [f"the app started in {start!r}, not StudioWorkbench: Studio's InitGui.py failed?"]
    return []


def assign_owners(alone: dict, classes: dict, order) -> list:
    """Picks each command's owning workbench from what each workbench registers when loaded alone.

    `alone`: {workbench: [getInfo() dicts]}; `classes`: {workbench: class name}. A command several
    workbenches register (Sketcher's loading also brings Part's commands) goes to the workbench its
    name prefix names ("Part_Box" -> PartWorkbench), else to the earliest in `order`. Returns
    [{"name", "class", "commands"}] in `order`.
    """
    candidates, infos = {}, {}
    for workbench in order:
        for info in alone.get(workbench, []):
            candidates.setdefault(info["name"], []).append(workbench)
            infos.setdefault((info["name"], workbench), info)
    owner = {}
    for name, workbenches in candidates.items():
        prefix = name.split("_", 1)[0]
        owner[name] = next((w for w in workbenches if _module(w) == prefix), workbenches[0])
    return [
        {"name": w, "class": classes[w],
         "commands": [infos[(n, w)] for n in sorted(owner) if owner[n] == w]}
        for w in order
    ]


def build_catalog(probe: dict, icons: IconIndex) -> dict:
    order = {None: -1, **{w["name"]: i for i, w in enumerate(probe["workbenches"])}}
    commands = []
    groups = [(None, probe["core"])] + [(w["name"], w["commands"]) for w in probe["workbenches"]]
    for workbench, infos in groups:
        for info in infos:
            if DEVELOPER_COMMANDS.match(info["name"]):
                continue
            commands.append({
                "name": info["name"],
                "workbench": workbench,
                "menu_text": info["menuText"],
                "tooltip": info["toolTip"],
                "shortcut": info["shortcut"],
                "icon": icons.find(info["pixmap"], _module(workbench)),
            })
    commands.sort(key=lambda c: (order[c["workbench"]], c["name"]))
    return {
        "about": "Generated by tools/studio/generate_command_catalog.py; do not edit by hand. "
                 "workbench null = available from startup. See docs/adr/0007.",
        "freecad": probe["freecad"],
        "workbenches": [{"name": w["name"], "class": w["class"]} for w in probe["workbenches"]],
        "commands": commands,
    }


def dumps(catalog: dict) -> str:
    return json.dumps(catalog, indent=1, ensure_ascii=False) + "\n"


def missing_icons(catalog: dict) -> list:
    return sorted(c["name"] for c in catalog["commands"] if c["icon"] is None)


def differences(shipped: dict, current: dict) -> list:
    """Human-readable differences that matter (the FreeCAD version string alone doesn't)."""
    found = []
    if shipped["workbenches"] != current["workbenches"]:
        found.append(f"workbenches: {shipped['workbenches']} -> {current['workbenches']}")
    old = {c["name"]: c for c in shipped["commands"]}
    new = {c["name"]: c for c in current["commands"]}
    found += [f"removed: {name}" for name in sorted(old.keys() - new.keys())]
    found += [f"added: {name}" for name in sorted(new.keys() - old.keys())]
    for name in sorted(old.keys() & new.keys()):
        for field in FIELDS:
            if old[name][field] != new[name][field]:
                found.append(f"changed: {name} {field}: {old[name][field]!r} -> {new[name][field]!r}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exe", type=Path, default=REPO / "build/slim-release/bin/FreeCAD.exe")
    parser.add_argument("--check", action="store_true", help="compare with the shipped catalog")
    args = parser.parse_args()

    # One fresh process per workbench: what loading it *alone* registers is what loading it on a
    # command's first use will make available.
    alone, classes, core, version = {}, {}, None, None
    for workbench in WORKBENCHES:
        run = run_probe(
            args.exe, PROBE, {"STUDIO_CATALOG_WORKBENCHES": workbench}, TIMEOUT_S,
            settings={"BaseApp/Preferences/General/Language": "English"},
        )
        if "error" in run:
            print(f"FAIL: probe error loading {workbench}\n{run['error']}", file=sys.stderr)
            return 1
        for problem in startup_problems(run):
            print(f"FAIL: {problem}", file=sys.stderr)
            return 1
        if run["missing"]:
            print(f"FAIL: {workbench} is not in this build", file=sys.stderr)
            return 1
        if core is not None and {c["name"] for c in run["core"]} != {c["name"] for c in core}:
            print("FAIL: the commands available at startup differ between runs", file=sys.stderr)
            return 1
        core, version = run["core"], run["freecad"]
        alone[workbench] = run["workbenches"][0]["commands"]
        classes[workbench] = run["workbenches"][0]["class"]
    probe = {"freecad": version, "core": core, "workbenches": assign_owners(alone, classes, WORKBENCHES)}
    catalog = build_catalog(probe, IconIndex(REPO / "src"))
    per_workbench = {w: sum(c["workbench"] == w for c in catalog["commands"]) for w in [None, *WORKBENCHES]}
    print(f"{len(catalog['commands'])} commands: " + ", ".join(
        f"{_module(w) or 'startup'} {n}" for w, n in per_workbench.items()))
    missing = missing_icons(catalog)
    print(f"{len(missing)} without a source SVG icon" + (f": {', '.join(missing[:12])}..." if missing else ""))

    if args.check:
        shipped = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else None
        if shipped is None:
            print(f"FAIL: {CATALOG.relative_to(REPO)} does not exist; run without --check", file=sys.stderr)
            return 1
        found = differences(shipped, catalog)
        for line in found:
            print(line)
        if found:
            print(f"FAIL: command catalog out of date ({len(found)} differences). Regenerate: "
                  "pixi run python tools/studio/generate_command_catalog.py", file=sys.stderr)
            return 1
        print("command catalog up to date")
        return 0

    CATALOG.write_text(dumps(catalog), encoding="utf-8", newline="\n")
    print(f"wrote {CATALOG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
