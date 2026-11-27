# SPDX-License-Identifier: LGPL-2.1-or-later
"""Text in sketches, laid out by Studio (PLAN 4.1, docs/adr/0015): studio.services.sketch_text.

A text box: lines as typed, the capitals the given height whatever the word, aligned in the box; the letters'
outlines are sketch geometry held by a sketch Group to a construction line along the box's bottom edge (the
frame), which carries the text's settings, so the text moves with it and is edited again later.
Font: Noto Sans Regular (StudioTests/fonts), cap height 714 of 1000 units.
"""

import os
import shutil
import tempfile
import unittest
import uuid

import FreeCAD
import Part
import Sketcher

from studio.services import fonts, sketch_text
from studio.services.sketch_text import TextBox

V = FreeCAD.Vector
NOTO = os.path.join(os.path.dirname(__file__), "fonts", "NotoSans-Regular.ttf")


def box(text, **kw):
    settings = dict(text=text, family="Noto Sans", style="Regular", height=10.0, width=100.0, depth=40.0,
                    align="left", valign="bottom")
    settings.update(kw)
    return TextBox(**settings)


class SketchText(unittest.TestCase):
    def setUp(self):
        self.font = fonts.read(NOTO)
        self.doc = FreeCAD.newDocument("Text" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1
        self.addCleanup(lambda: FreeCAD.closeDocument(self.doc.Name))
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        self.sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        self.sketch.MapMode = "FlatFace"
        self.doc.recompute()

    def add(self, settings, corner=(0.0, 0.0), angle=0.0):
        frame = sketch_text.add(self.sketch, settings, self.font, corner, angle)
        self.doc.recompute()
        return frame

    def letters(self, frame=None):
        """The text's letters (not its construction lines) as one shape."""
        frames = [frame] if frame is not None else sketch_text.frames(self.sketch)
        ids = [i for f in frames for i in sketch_text.members(self.sketch, f) if not self.sketch.getConstruction(i)]
        return Part.Compound([self.sketch.Geometry[i].toShape() for i in ids])

    # sizes

    def test_the_capitals_are_the_height(self):
        self.add(box("H"))
        self.assertAlmostEqual(self.letters().BoundBox.YLength, 10.0, delta=0.02)

    def test_the_same_size_whatever_the_word(self):
        # FreeCAD's Text stretches each word to its line: "xz" would be as tall as "HEL" (letters with flat tops
        # and bottoms: round ones overshoot the lines a little)
        caps = self.letters(self.add(box("HEL"))).BoundBox.YLength
        small = self.letters(self.add(box("xz"), corner=(0, 50))).BoundBox.YLength
        self.assertAlmostEqual(caps, 10.0, delta=0.02)
        self.assertAlmostEqual(small / caps, self.font.x_height / self.font.cap_height, delta=0.02)

    def test_lines_as_typed(self):
        self.add(box("H\nH"))
        pitch = 10.0 * self.font.line_spacing / self.font.cap_height
        self.assertAlmostEqual(self.letters().BoundBox.YLength, 10.0 + pitch, delta=0.03)

    def test_line_spacing(self):
        self.add(box("H\nH", spacing=1.5))
        pitch = 1.5 * 10.0 * self.font.line_spacing / self.font.cap_height
        self.assertAlmostEqual(self.letters().BoundBox.YLength, 10.0 + pitch, delta=0.03)

    def test_a_blank_line_keeps_its_space(self):
        self.add(box("H\n\nH"))
        pitch = 10.0 * self.font.line_spacing / self.font.cap_height
        self.assertAlmostEqual(self.letters().BoundBox.YLength, 10.0 + 2 * pitch, delta=0.03)

    # in the box

    def test_left_center_and_right(self):
        for align, x in (("left", 0.0), ("center", 50.0), ("right", 100.0)):
            with self.subTest(align):
                frame = self.add(box("H", align=align))
                b = self.letters(frame).BoundBox
                edge = {"left": b.XMin, "center": (b.XMin + b.XMax) / 2, "right": b.XMax}[align]
                self.assertAlmostEqual(edge, x, delta=0.01)
                sketch_text.remove(self.sketch, frame)

    def test_top_middle_and_bottom(self):
        # top: the capitals' tops at the box's top; bottom: the last line on the box's bottom; middle: between
        for valign, y in (("top", 40.0), ("middle", 20.0), ("bottom", 0.0)):
            with self.subTest(valign):
                frame = self.add(box("H", valign=valign))
                b = self.letters(frame).BoundBox
                at = {"top": b.YMax, "middle": (b.YMin + b.YMax) / 2, "bottom": b.YMin}[valign]
                self.assertAlmostEqual(at, y, delta=0.02)
                sketch_text.remove(self.sketch, frame)

    def test_the_box_is_construction_around_it(self):
        frame = self.add(box("Hi"))
        lines = [i for i in [frame] + sketch_text.members(self.sketch, frame) if self.sketch.getConstruction(i)]
        self.assertEqual(len(lines), 4)
        outline = Part.Compound([self.sketch.Geometry[i].toShape() for i in lines]).BoundBox
        self.assertEqual((round(outline.XLength, 6), round(outline.YLength, 6)), (100.0, 40.0))
        self.assertTrue(all(not self.sketch.getConstruction(i) for i in sketch_text.members(self.sketch, frame)
                            if i not in lines))

    def test_placed_and_turned(self):
        frame = self.add(box("H", align="center", valign="middle"), corner=(5.0, 7.0), angle=90.0)
        b = self.letters(frame).BoundBox
        # turned a quarter: the box runs up from (5, 7), 100 long, 40 across to the left
        self.assertAlmostEqual((b.XMin + b.XMax) / 2, 5.0 - 20.0, delta=0.02)
        self.assertAlmostEqual((b.YMin + b.YMax) / 2, 7.0 + 50.0, delta=0.02)
        self.assertAlmostEqual(b.XLength, 10.0, delta=0.02)  # the capitals' height, now across

    # the frame holds it

    def test_it_moves_with_its_line(self):
        # the line held to its length and angle, so that moving one end moves it whole
        frame = self.add(box("Hi"))
        self.sketch.addConstraint(Sketcher.Constraint("Horizontal", frame))
        self.sketch.addConstraint(Sketcher.Constraint("Distance", frame, 100.0))
        self.doc.recompute()
        before = self.letters().BoundBox
        self.sketch.addConstraint(Sketcher.Constraint("DistanceX", frame, 1, 30.0))
        self.sketch.addConstraint(Sketcher.Constraint("DistanceY", frame, 1, 20.0))
        self.doc.recompute()
        after = self.letters().BoundBox
        self.assertAlmostEqual(after.XMin - before.XMin, 30.0, places=6)
        self.assertAlmostEqual(after.YMin - before.YMin, 20.0, places=6)

    def test_fully_defined_once_its_line_is(self):
        frame = self.add(box("Hi"))
        for c in (Sketcher.Constraint("DistanceX", frame, 1, 0.0), Sketcher.Constraint("DistanceY", frame, 1, 0.0),
                  Sketcher.Constraint("Horizontal", frame), Sketcher.Constraint("Distance", frame, 100.0)):
            self.sketch.addConstraint(c)
        self.doc.recompute()
        self.assertTrue(self.sketch.FullyConstrained)

    def test_it_extrudes(self):
        self.add(box("Hi"))
        pad = self.body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = self.sketch
        pad.Length = 2
        self.doc.recompute()
        self.assertTrue(pad.isValid(), pad.getStatusString())
        self.assertEqual(len(pad.Shape.Solids), 3)  # H, the i's stem and its dot

    # read back and edited

    def test_read_back(self):
        settings = box("Lesleigh's \"sun\" flower\nséance & <more>", align="center", valign="middle", spacing=1.2)
        frame = self.add(settings)
        self.assertEqual(sketch_text.read(self.sketch, frame), settings)

    def test_it_survives_save_and_reopen(self):
        # quotes, ampersands and angle brackets too: FreeCAD writes a geometry's text unescaped into the file
        settings = box("Lesleigh's \"sun\" flower\nséance & <more>")
        self.add(settings)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, "text.FCStd")
        self.doc.saveAs(path)
        letters, name = len(self.sketch.Geometry), self.sketch.Name
        FreeCAD.closeDocument(self.doc.Name)  # else opening the file gives back the same document
        self.doc = FreeCAD.openDocument(path)
        sketch = self.doc.getObject(name)
        self.assertEqual(len(sketch.Geometry), letters)
        [frame] = sketch_text.frames(sketch)
        self.assertEqual(sketch_text.read(sketch, frame), settings)

    def test_found_after_other_geometry_goes(self):
        self.sketch.addGeometry(Part.LineSegment(V(-50, -50, 0), V(-40, -40, 0)))
        frame = self.add(box("Hi"))
        self.sketch.delGeometry(0)
        self.doc.recompute()
        self.assertEqual(sketch_text.frames(self.sketch), [frame - 1])
        self.assertEqual(sketch_text.read(self.sketch, frame - 1).text, "Hi")

    def test_a_longer_line_makes_it_bigger(self):
        frame = self.add(box("H"))
        self.sketch.addConstraint(Sketcher.Constraint("Distance", frame, 150.0))
        self.doc.recompute()
        read = sketch_text.read(self.sketch, frame)
        self.assertAlmostEqual(read.width, 150.0, places=6)
        self.assertAlmostEqual(read.height, 15.0, places=6)
        self.assertAlmostEqual(read.depth, 60.0, places=6)
        self.assertAlmostEqual(self.letters().BoundBox.YLength / read.height, 1.0, delta=0.01)

    def test_edited(self):
        frame = self.add(box("Hi"))
        self.sketch.addConstraint(Sketcher.Constraint("DistanceX", frame, 1, 30.0))
        self.doc.recompute()
        changed = box("Hello\nthere", height=5.0, align="right")
        frame = sketch_text.edit(self.sketch, frame, changed, self.font)
        self.doc.recompute()
        self.assertEqual(sketch_text.read(self.sketch, frame), changed)
        self.assertEqual(sketch_text.frames(self.sketch), [frame])
        self.assertEqual([c.Type for c in self.sketch.Constraints].count("Group"), 1)
        self.assertIn("DistanceX", [c.Type for c in self.sketch.Constraints], "the user's constraint on the line")
        self.assertAlmostEqual(self.letters().BoundBox.XMax, 130.0, delta=0.01)  # right-aligned, the box moved 30

    def test_a_wider_box_lengthens_the_line(self):
        frame = self.add(box("H"))
        frame = sketch_text.edit(self.sketch, frame, box("H", width=120.0), self.font)
        self.doc.recompute()
        line = self.sketch.Geometry[frame]
        self.assertAlmostEqual(line.length(), 120.0, places=6)
        self.assertAlmostEqual(self.letters().BoundBox.YLength, 10.0, delta=0.02)

    def test_one_undo_step_each(self):
        frame = self.add(box("Hi"))
        sketch_text.edit(self.sketch, frame, box("Hello"), self.font)
        self.doc.recompute()
        self.doc.undo()
        self.doc.recompute()
        self.assertEqual(sketch_text.read(self.sketch, sketch_text.frames(self.sketch)[0]).text, "Hi")
        self.doc.undo()
        self.doc.recompute()
        self.assertEqual(sketch_text.frames(self.sketch), [])
        self.assertEqual(len(self.sketch.Geometry), 0)

    def test_inside_a_panels_step_it_adds_none(self):
        # the tool's preview: the panel opens the step (FreeCAD counts it as open only once something
        # changed, so the panel says so) and the text joins it; Cancel takes it all back
        self.doc.openTransaction("Text panel")
        frame = sketch_text.add(self.sketch, box("Hi"), self.font, step=False)
        sketch_text.edit(self.sketch, frame, box("Hello"), self.font, step=False)
        self.assertTrue(self.doc.HasPendingTransaction)
        self.doc.abortTransaction()
        self.doc.recompute()
        self.assertEqual(len(self.sketch.Geometry), 0)

    def test_removed(self):
        self.sketch.addGeometry(Part.LineSegment(V(-50, -50, 0), V(-40, -40, 0)))
        frame = self.add(box("Hi"))
        sketch_text.remove(self.sketch, frame)
        self.doc.recompute()
        self.assertEqual(len(self.sketch.Geometry), 1)
        self.assertEqual(len(self.sketch.Constraints), 0)

    def test_only_studios_texts(self):
        # a plain line, and FreeCAD's own Text, aren't Studio texts
        self.sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)), True)
        self.add(box("Hi"))
        self.assertEqual(len(sketch_text.frames(self.sketch)), 1)
        self.assertIsNone(sketch_text.read(self.sketch, 0))
