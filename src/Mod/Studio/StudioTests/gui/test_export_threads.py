# SPDX-License-Identifier: LGPL-2.1-or-later
"""Model all threads on export, in the app (PLAN 3.9; studio.shell.export_threads).

FreeCAD's File > Export ends in the export function of the module its file type belongs to
(ImportGui for STEP, Mesh for STL). Studio wraps those, so exported threads are modeled while the model
keeps them cosmetic. The tests call them as File > Export does.
"""

import os
import tempfile
import unittest

import FreeCAD
import Mesh
import Part

from StudioTests.gui.sketch_input import settle
from StudioTests.test_threads import ThreadedPart
from studio.services import threads
from studio.services.settings import Settings


class ExportedThreads(ThreadedPart):
    def setUp(self):
        super().setUp()
        settings = Settings()
        self.addCleanup(settings.set, threads.MODEL_ON_EXPORT, settings.get(threads.MODEL_ON_EXPORT))
        settle(100)

    def step_faces(self, on):
        import ImportGui  # File > Export's module for STEP

        Settings().set(threads.MODEL_ON_EXPORT, on)
        path = os.path.join(tempfile.mkdtemp(), "part.step")
        ImportGui.export([self.body], path)
        return len(Part.read(path).Faces)

    def stl_facets(self, on):
        Settings().set(threads.MODEL_ON_EXPORT, on)
        path = os.path.join(tempfile.mkdtemp(), "part.stl")
        Mesh.export([self.body], path)
        return Mesh.Mesh(path).CountFacets

    def test_a_step_export_gets_modeled_threads(self):
        self.assertGreater(self.step_faces(True), self.step_faces(False))
        self.assertFalse(self.hole.ModelThread, "the model should keep its cosmetic thread")

    def test_an_stl_export_gets_modeled_threads(self):
        self.assertGreater(self.stl_facets(True), self.stl_facets(False))
        self.assertFalse(self.hole.ModelThread)

    def test_nothing_to_report_when_every_thread_is_modeled(self):
        self.step_faces(True)
        settle(100)
        self.assertEqual(not_modeled_boxes(), [])

    def test_the_menu_switches_it(self):
        from studio.shell import export_threads

        action = export_threads.current().action
        self.assertEqual(action.text(), "Model Threads on Export")
        self.assertTrue(action.isCheckable())
        Settings().set(threads.MODEL_ON_EXPORT, True)
        export_threads.current().sync()
        self.assertTrue(action.isChecked())
        action.trigger()
        self.assertFalse(Settings().get(threads.MODEL_ON_EXPORT))


def not_modeled_boxes():
    from PySide import QtWidgets

    return [w for w in QtWidgets.QApplication.topLevelWidgets()
            if w.objectName() == "StudioThreadsNotModeled" and w.isVisible()]


class AThreadNotModeled(unittest.TestCase):
    """The user, 2026-11-26: an exported stem came out smooth with no word why. When a thread can't be
    modeled, the export still writes the file, and says which threads are plain in it."""

    def setUp(self):
        from StudioTests.test_shaft_threads import shaft
        from studio.services import shaft_threads

        self.doc, self.body, pad, face = shaft(0.25 * 25.4, 20.0)
        self.doc.UndoMode = 1  # an export models threads in a step it then takes back
        self.addCleanup(lambda: FreeCAD.closeDocument(self.doc.Name)
                        if self.doc.Name in FreeCAD.listDocuments() else None)
        self.thread = shaft_threads.make(self.body, pad, face, "inches")
        self.doc.recompute()
        real = shaft_threads.groove
        shaft_threads.groove = lambda *args, **kwargs: Part.makeBox(1, 1, 1, FreeCAD.Vector(100, 100, 100))
        self.addCleanup(setattr, shaft_threads, "groove", real)
        settings = Settings()
        self.addCleanup(settings.set, threads.MODEL_ON_EXPORT, settings.get(threads.MODEL_ON_EXPORT))
        settings.set(threads.MODEL_ON_EXPORT, True)
        self.addCleanup(lambda: [box.close() for box in not_modeled_boxes()])

    def test_the_export_says_which(self):
        import ImportGui

        path = os.path.join(tempfile.mkdtemp(), "stem.step")
        ImportGui.export([self.body], path)
        settle(100)
        self.assertTrue(os.path.exists(path), "the file is still written")
        boxes = not_modeled_boxes()
        self.assertEqual(len(boxes), 1)
        self.assertIn(f"{self.thread.Label} in {self.body.Label}", boxes[0].text())
        self.assertFalse(self.thread.Modeled, "the model keeps its cosmetic thread")
