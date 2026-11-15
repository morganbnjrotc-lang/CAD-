# SPDX-License-Identifier: LGPL-2.1-or-later
"""Home page data (PLAN 2.8): recent files, their preview images and the cards that show them.

studio.services.recent_files reads and edits FreeCAD's own recent-files list, so the File menu and
the Home page always agree; studio.services.thumbnails reads the preview image FreeCAD stores in a
.FCStd file; studio.viewmodels.home turns them into cards.
"""

import os
import tempfile
import time
import unittest
import uuid
import zipfile
from pathlib import Path

import FreeCAD

from studio.services.recent_files import RecentFiles
from studio.services.thumbnails import thumbnail_png
from studio.viewmodels.home import Home, saved_when

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
PNG = b"\x89PNG\r\n\x1a\n" + b"fake image data"
REPO = Path(FreeCAD.getHomePath()).resolve().parents[1]  # build/<preset>/ -> repository


class Files(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        name = "Recent" + uuid.uuid4().hex[:8]
        self.group_path = f"{TEST_PARENT}/{name}"
        self.group = FreeCAD.ParamGet(self.group_path)
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))

    def make(self, name, content=b"x", age_s=0):
        path = self.dir / name
        path.write_bytes(content)
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
        return str(path)

    def store(self, *paths, count=10):
        for i, path in enumerate(paths):
            self.group.SetString(f"MRU{i}", path)
        self.group.SetInt("RecentFiles", count)
        return RecentFiles(self.group_path)


class RecentFilesStore(Files):
    def test_most_recent_first_including_files_that_no_longer_exist(self):
        a, b = self.make("a.FCStd"), self.make("b.step")
        gone = str(self.dir / "gone.FCStd")
        recent = self.store(a, gone, b)
        self.assertEqual([f.path for f in recent.files()], [a, gone, b])
        self.assertEqual([f.exists for f in recent.files()], [True, False, True])

    def test_order_follows_the_number_not_the_text(self):
        paths = [self.make(f"f{i}.FCStd") for i in range(12)]
        recent = self.store(*paths, count=12)
        self.assertEqual(recent.paths(), paths)  # MRU10 comes after MRU9, not after MRU1

    def test_removing_keeps_the_rest_in_order_with_no_gaps(self):
        a, b, c = self.make("a.FCStd"), self.make("b.FCStd"), self.make("c.FCStd")
        recent = self.store(a, b, c, count=7)
        recent.remove(b)
        self.assertEqual(recent.paths(), [a, c])
        names = sorted(n for _, n, _ in self.group.GetContents() if n.startswith("MRU"))
        self.assertEqual(names, ["MRU0", "MRU1"])
        self.assertEqual(self.group.GetInt("RecentFiles"), 7)  # FreeCAD reloads its menu on this key

    def test_removing_matches_paths_regardless_of_case_on_windows(self):
        a = self.make("Part.FCStd")
        recent = self.store(a)
        recent.remove(a.upper() if os.name == "nt" else a)
        self.assertEqual(recent.paths(), [])

    def test_removing_a_path_not_in_the_list_changes_nothing(self):
        a = self.make("a.FCStd")
        recent = self.store(a)
        recent.remove(str(self.dir / "other.FCStd"))
        self.assertEqual(recent.paths(), [a])

    def test_an_empty_list(self):
        self.assertEqual(RecentFiles(self.group_path).files(), [])


class Thumbnails(Files):
    def fcstd(self, name, thumbnail=PNG):
        path = self.dir / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Document.xml", "<Document/>")
            if thumbnail is not None:
                archive.writestr("thumbnails/Thumbnail.png", thumbnail)
        return str(path)

    def test_the_preview_freecad_stored_in_the_file(self):
        self.assertEqual(thumbnail_png(self.fcstd("part.FCStd")), PNG)
        self.assertEqual(thumbnail_png(self.fcstd("upper.FCSTD")), PNG)

    def test_no_preview_is_none(self):
        self.assertIsNone(thumbnail_png(self.fcstd("bare.FCStd", thumbnail=None)))
        self.assertIsNone(thumbnail_png(self.make("broken.FCStd", b"not a zip file")))
        self.assertIsNone(thumbnail_png(self.make("part.step", b"ISO-10303-21;")))
        self.assertIsNone(thumbnail_png(str(self.dir / "missing.FCStd")))

    def test_a_real_example_file(self):
        png = thumbnail_png(str(REPO / "data" / "examples" / "PartDesignExample.FCStd"))
        self.assertTrue(png and png.startswith(b"\x89PNG"))


class Cards(Files):
    NOW = time.mktime((2026, 11, 14, 15, 0, 0, 0, 0, -1))

    def test_saved_when_reads_like_a_person_would_say_it(self):
        cases = [(20, "Saved just now"), (5 * 60, "Saved 5 minutes ago"), (60, "Saved 1 minute ago"),
                 (2 * 3600, "Saved 2 hours ago"), (3600, "Saved 1 hour ago"),
                 (20 * 3600, "Saved yesterday"), (3 * 86400, "Saved 3 days ago"),
                 (40 * 86400, "Saved 5 Oct 2026")]
        for age, expected in cases:
            with self.subTest(age=age):
                self.assertEqual(saved_when(self.NOW - age, self.NOW), expected)

    def saved_at(self, name, age_s):
        """A file saved `age_s` before NOW (a fixed afternoon, so the test can't straddle midnight)."""
        path = self.make(name)
        os.utime(path, (self.NOW - age_s, self.NOW - age_s))
        return path

    def test_a_card_per_recent_file(self):
        part = self.saved_at("Bracket.FCStd", 2 * 3600)
        step = self.saved_at("Housing.step", 0)
        gone = str(self.dir / "Old.FCStd")
        home = Home(self.store(part, step, gone), now=lambda: self.NOW)
        cards = home.cards()
        self.assertEqual([(c.title, c.kind, c.exists) for c in cards],
                         [("Bracket", "FreeCAD", True), ("Housing", "STEP", True), ("Old", "FreeCAD", False)])
        self.assertEqual(cards[0].folder, self.dir.name)
        self.assertEqual(cards[0].when, "Saved 2 hours ago")
        self.assertEqual(cards[2].when, "File not found")

    def test_remove_takes_a_card_off(self):
        a, b = self.make("a.FCStd"), self.make("b.FCStd")
        home = Home(self.store(a, b))
        home.remove(a)
        self.assertEqual([c.path for c in home.cards()], [b])


if __name__ == "__main__":
    unittest.main()
