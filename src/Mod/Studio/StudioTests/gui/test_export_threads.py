# SPDX-License-Identifier: LGPL-2.1-or-later
"""Model all threads on export, in the app (PLAN 3.9; studio.shell.export_threads).

FreeCAD's File > Export ends in the export function of the module its file type belongs to
(ImportGui for STEP, Mesh for STL). Studio wraps those, so exported threads are modeled while the model
keeps them cosmetic. The tests call them as File > Export does.
"""

import os
import tempfile

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
