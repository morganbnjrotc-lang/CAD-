# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Text tool in the app (PLAN 4.1, docs/adr/0015; studio.shell.sketch_text).

In a sketch, Text (the toolbar's Text Box way; FreeCAD's own text is its Along a Line way) puts "Text" in the
middle of the view and opens the Text panel at the top of the Tasks panel; typing redraws it, Finish keeps it
as one undo step, Cancel takes it back, also after a drag closed the panel's step; a picked text is edited;
closing the sketch finishes it. Fonts are the computer's (Arial and Times New Roman: on every Windows).
"""

import FreeCAD
import FreeCADGui

from StudioTests.gui.sketch_input import INCH, settle
from StudioTests.gui.test_sketch_ways import ToolbarDrawing, tools
from studio.services import fonts, sketch_text
from studio.services.settings import Settings
from studio.services.sketch_text import TextBox
from studio.shell import sketch_text as text_tool
from studio.viewmodels import text_panel


class TextTool(ToolbarDrawing):
    def setUp(self):
        super().setUp()
        self.addCleanup(tools().choose_way, "Studio_Text", 0)
        self.addCleanup(self.close_panel)
        # the font and height used last start the next text: each test starts from none
        settings = Settings()
        for setting in (text_panel.FAMILY, text_panel.STYLE, text_panel.HEIGHT):
            if settings.is_overridden(setting):
                self.addCleanup(settings.set, setting, settings.get(setting))
            else:
                self.addCleanup(settings.reset, setting)
            settings.reset(setting)

    def close_panel(self):
        panel = text_tool.current_panel()
        if panel is not None:
            panel.cancel()
            settle(100)

    def texts(self):
        return sketch_text.frames(self.sketch)

    def start(self):
        self.pick("Text", "Text Box")
        panel = text_tool.current_panel()
        self.assertIsNotNone(panel, "no Text panel")
        return panel

    def settings(self):
        [frame] = self.texts()
        return sketch_text.read(self.sketch, frame)

    def test_text_lists_its_ways(self):
        self.assertEqual([a.text() for a in self.button("Text").menu().actions()], ["Text Box", "Along a Line"])

    def test_a_new_text_in_the_middle_of_the_view(self):
        panel = self.start()
        self.assertTrue(panel.form.isVisible(), "the panel isn't shown")
        self.assertEqual(self.settings().text, "Text")
        x, y = text_tool.view_center(self.sketch)
        corner = self.sketch.Geometry[self.texts()[0]].StartPoint
        self.assertAlmostEqual(corner.x, x, places=3)
        self.assertAlmostEqual(corner.y, y, places=3)

    def test_a_quarter_inch_to_start_with(self):
        self.start()
        self.assertAlmostEqual(self.settings().height, 0.25 * INCH, places=6)

    def test_typing_redraws_it(self):
        self.start()
        self.type("Lesleigh")  # the text field has the focus, "Text" selected
        settle(text_tool.DELAY_MS + 300)
        self.assertEqual(self.settings().text, "Lesleigh")

    def test_finish_keeps_it_in_one_undo_step(self):
        undo = self.doc.UndoCount
        panel = self.start()
        panel.text.setPlainText("Hi")
        settle(text_tool.DELAY_MS + 300)
        panel.finish()
        settle(200)
        self.assertIsNone(text_tool.current_panel())
        self.assertEqual(len(self.texts()), 1)
        self.assertEqual(self.doc.UndoCount, undo + 1)
        self.doc.undo()
        self.doc.recompute()
        self.assertEqual(self.texts(), [])

    def test_cancel_takes_it_back(self):
        panel = self.start()
        panel.cancel()
        settle(200)
        self.assertIsNone(text_tool.current_panel())
        self.assertEqual(len(self.sketch.Geometry), 0)

    def test_cancel_after_a_drag(self):
        # a drag is an undo step of its own: it closes the panel's, so Cancel removes the text by hand
        panel = self.start()
        self.doc.commitTransaction()
        panel.cancel()
        settle(200)
        self.assertEqual(self.texts(), [])

    def test_a_picked_text_is_edited(self):
        arial = fonts.find("Arial", "Regular", text_tool.installed_fonts())
        frame = sketch_text.add(self.sketch, TextBox("Hi", "Arial", "Regular", 6.0, 20.0, 6.0, fit=True), arial)
        self.doc.recompute()
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, f"Edge{frame + 1}")
        settle(300)
        panel = self.start()
        self.assertFalse(panel.new)
        self.assertEqual(panel.text.toPlainText(), "Hi")
        panel.text.setPlainText("Hello")
        settle(text_tool.DELAY_MS + 300)
        panel.finish()
        settle(200)
        self.assertEqual(len(self.texts()), 1)
        self.assertEqual(self.settings().text, "Hello")

    def test_another_font(self):
        panel = self.start()
        families = [panel.family.itemText(i) for i in range(panel.family.count())]
        self.assertIn("Arial", families)
        panel.family.setCurrentText("Times New Roman")
        settle(text_tool.DELAY_MS + 300)
        self.assertEqual((self.settings().family, self.settings().style), ("Times New Roman", "Regular"))

    def test_closing_the_sketch_finishes_it(self):
        panel = self.start()
        panel.text.setPlainText("Kept")
        settle(text_tool.DELAY_MS + 300)
        FreeCADGui.ActiveDocument.resetEdit()
        settle(400)
        self.assertIsNone(text_tool.current_panel())
        self.assertEqual(self.settings().text, "Kept")
        self.assertFalse(self.doc.HasPendingTransaction)
