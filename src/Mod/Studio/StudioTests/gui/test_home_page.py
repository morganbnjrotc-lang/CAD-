# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home page (studio.shell.home), PLAN 2.8: replaces FreeCAD's Start page.

Shown over the main area while no document is open: New Part, Open, and the recent files as cards
with the preview stored in each .FCStd file. Most tests use their own page and recent-files list;
the session tests check the page Studio sets up.
"""

import tempfile
import time
import unittest
import uuid
from pathlib import Path

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

from studio.services.recent_files import HOME_COUNT, LIMIT_RAISED, RecentFiles
from studio.services.settings import Settings
from studio.shell.home import HomePage
from studio.viewmodels.home import Home

from .test_shortcuts import settle

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
EXAMPLES = Path(FreeCAD.getHomePath()).resolve().parents[1] / "data" / "examples"


def run_until(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
    return condition()


class FakeService:
    def __init__(self):
        self.ran = []

    def run(self, name):
        self.ran.append(name)


class HomePageTest(unittest.TestCase):
    def setUp(self):
        name = "HomePage" + uuid.uuid4().hex[:8]
        self.group = FreeCAD.ParamGet(f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.step = Path(self._tmp.name) / "Housing.step"
        self.step.write_text("ISO-10303-21;")
        self.paths = [str(EXAMPLES / "PartDesignExample.FCStd"), str(self.step),
                      str(Path(self._tmp.name) / "Gone.FCStd")]
        for i, path in enumerate(self.paths):
            self.group.SetString(f"MRU{i}", path)
        self.group.SetInt("RecentFiles", 10)
        self.opened, self.service = [], FakeService()
        self.page = HomePage(Home(RecentFiles(f"{TEST_PARENT}/{name}")), self.service,
                             opener=self.opened.append)
        self.addCleanup(self.page.deleteLater)
        self.page.refresh()

    def items(self):
        return [self.page.cards.item(i) for i in range(self.page.cards.count())]

    def test_a_card_per_recent_file_most_recent_first(self):
        self.assertEqual([item.data(QtCore.Qt.UserRole) for item in self.items()], self.paths)
        self.assertTrue(self.items()[0].text().startswith("PartDesignExample"))
        self.assertIn("File not found", self.items()[2].text())

    def test_previews_load_just_after_the_page_shows(self):
        self.assertTrue(run_until(lambda: self.page.previews_loaded), "previews never finished")
        first, step = self.items()[0], self.items()[1]
        self.assertFalse(first.icon().isNull())
        self.assertEqual(first.icon().pixmap(64, 64).cacheKey() == step.icon().pixmap(64, 64).cacheKey(), False)

    def test_activating_a_card_opens_its_file(self):
        self.page.cards.itemActivated.emit(self.items()[1])
        settle()
        self.assertEqual(self.opened, [str(self.step)])

    def test_a_missing_file_is_not_opened(self):
        self.page.cards.itemActivated.emit(self.items()[2])
        settle()
        self.assertEqual(self.opened, [])

    def test_remove_from_list(self):
        self.page.remove_path(str(self.step))
        self.assertEqual([item.data(QtCore.Qt.UserRole) for item in self.items()],
                         [self.paths[0], self.paths[2]])
        self.assertNotIn(str(self.step), RecentFiles(self.page_group_path()).paths())

    def page_group_path(self):
        return self.page._home._recent._path

    def test_new_part_and_open_run_freecads_commands(self):
        self.page.new_part_button.click()
        self.page.open_button.click()
        settle()
        self.assertEqual(self.service.ran, ["Std_New", "PartDesign_Body", "Std_Open"])

    def test_an_empty_list_says_how_to_start(self):
        for name in [n for _, n, _ in self.group.GetContents() if n.startswith("MRU")]:
            self.group.RemString(name)
        self.page.refresh()
        self.assertEqual(self.page.cards.count(), 0)
        self.assertTrue(self.page.empty_note.isVisibleTo(self.page))


class SessionHome(unittest.TestCase):
    def setUp(self):
        from studio.shell import home

        self.home = home.current()

    def test_studio_shows_home_instead_of_freecads_start_page(self):
        self.assertIsNotNone(self.home, "Studio did not set up the Home page")
        self.assertFalse(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Start").GetBool("ShowOnStartup", True))
        titles = [w.windowTitle() for w in FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea).subWindowList()]
        self.assertFalse([t for t in titles if "Start" in t], titles)

    def test_home_shows_only_while_no_document_is_open(self):
        if FreeCAD.listDocuments():
            self.skipTest("another test left a document open")
        settle()
        self.assertTrue(self.home.isVisible())
        doc = FreeCAD.newDocument("StudioHomeTest")
        settle()
        self.assertFalse(self.home.isVisible())
        FreeCAD.closeDocument(doc.Name)
        settle()
        self.assertTrue(self.home.isVisible())

    def test_freecad_remembers_enough_recent_files_to_fill_home(self):
        self.assertTrue(Settings().get(LIMIT_RAISED))
        self.assertGreaterEqual(RecentFiles().limit(), HOME_COUNT)  # the test profile is brand new
