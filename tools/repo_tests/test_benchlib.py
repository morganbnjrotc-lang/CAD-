# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the throwaway FreeCAD profile the benchmarks run in (tools/bench/benchlib.py).

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "bench"))

import benchlib  # noqa: E402  (needs the path above)


def parameters(user_cfg: Path) -> dict:
    """Every parameter in a FreeCAD user.cfg as {"Group/Path/Name": (type, value)}."""
    found = {}

    def walk(element, path):
        for child in element:
            if child.tag == "FCParamGroup":
                walk(child, path + [child.get("Name")])
            else:
                found["/".join(path + [child.get("Name")])] = (child.tag, child.get("Value", child.text))

    walk(ElementTree.parse(user_cfg).getroot(), [])
    return found


class ThrowawayProfile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.env = benchlib.make_profile(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_freecad_is_pointed_at_folders_that_exist(self):
        # FreeCAD silently ignores FREECAD_USER_* unless the folders already exist, and would then
        # read and write the developer's real profile.
        for name in ("FREECAD_USER_HOME", "FREECAD_USER_DATA", "FREECAD_USER_TEMP"):
            with self.subTest(name=name):
                self.assertTrue(Path(self.env[name]).is_dir())
                self.assertTrue(Path(self.env[name]).is_relative_to(self.root))

    def test_opengl_version_warning_is_already_dismissed(self):
        # Without a GPU (GitHub's Windows runners) Windows offers only OpenGL 1.1, and release
        # builds then show a modal "Invalid OpenGL Version" warning at startup, before any probe
        # code runs. The profile starts as if the user had ticked "don't show again".
        # Key: DlgCheckableMessageBox stores the window title with spaces turned into underscores.
        user_cfg = Path(self.env["FREECAD_USER_HOME"]) / "user.cfg"
        self.assertEqual(
            parameters(user_cfg),
            {"Root/BaseApp/CheckMessages/FreeCAD_-_Invalid_OpenGL_Version": ("FCBool", "1")},
            "the profile must stay brand-new apart from this one setting",
        )


if __name__ == "__main__":
    unittest.main()
