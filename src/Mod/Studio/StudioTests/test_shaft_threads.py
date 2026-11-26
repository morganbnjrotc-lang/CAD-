# SPDX-License-Identifier: LGPL-2.1-or-later
"""A Thread tool for round faces, like Fusion's (PLAN 3.20, docs/adr/0014; studio.services.shaft_threads).

The user, 2026-11-26: "is adding threads to a cylinder an option". Click a round face: the size is picked
from its diameter, in the units' standard (inches: UNC first). Cosmetic by default (the solid doesn't
change), Modeled cuts the thread's groove; full length or a length from the face's end; left handed on
request; a Fit makes it looser for 3D printing. Sizes come from FreeCAD's own thread tables.
"""

import math
import unittest
import uuid

import FreeCAD
import Part

from studio.services import shaft_threads

V = FreeCAD.Vector
INCH = 25.4
QUARTER = 0.25 * INCH  # a 1/4 in shaft
LENGTH = 20.0


class Sizes(unittest.TestCase):
    def test_freecads_unc_sizes(self):
        quarter = next(s for s in shaft_threads.sizes("UNC") if s.name == "1/4")
        self.assertAlmostEqual(quarter.diameter, QUARTER, places=3)
        self.assertAlmostEqual(quarter.pitch, INCH / 20, places=3)  # 1/4-20

    def test_freecads_metric_sizes(self):
        m6 = next(s for s in shaft_threads.sizes("ISOMetricProfile") if s.name == "M6x1.0")
        self.assertEqual((m6.diameter, m6.pitch), (6.0, 1.0))

    def test_a_quarter_inch_shaft_gets_quarter_twenty(self):
        self.assertEqual(shaft_threads.nearest(QUARTER, "inches"), ("UNC", "1/4"))

    def test_a_six_millimeter_shaft_gets_m6(self):
        self.assertEqual(shaft_threads.nearest(6.0, "millimeters"), ("ISOMetricProfile", "M6x1.0"))

    def test_the_units_standard_first_then_any_that_fits(self):
        # 10 mm is no UNC size (3/8 in is 9.5 mm): ISO metric fits it, also when working in inches
        self.assertEqual(shaft_threads.nearest(10.0, "inches"), ("ISOMetricProfile", "M10x1.5"))
        # and a 1/4 in shaft drawn in millimeters still gets 1/4-20
        self.assertEqual(shaft_threads.nearest(QUARTER, "millimeters"), ("UNC", "1/4"))

    def test_the_standards_offered(self):
        self.assertEqual(shaft_threads.standards("inches")[:3], ("UNC", "UNF", "UNEF"))
        self.assertEqual(shaft_threads.standards("millimeters")[:2], ("ISOMetricProfile", "ISOMetricFineProfile"))


class OnAShaft(unittest.TestCase):
    """A 1/4 in shaft 20 mm long, extruded from a circle on the XY plane."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("ShaftThreads" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1  # an export models threads in a step it then takes back
        self.addCleanup(lambda: FreeCAD.closeDocument(self.doc.Name)
                        if self.doc.Name in FreeCAD.listDocuments() else None)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        sketch.MapMode = "FlatFace"
        sketch.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), QUARTER / 2))
        self.shaft = self.body.newObject("PartDesign::Pad", "Shaft")
        self.shaft.Profile = sketch
        self.shaft.Length = LENGTH
        self.doc.recompute()
        self.face = next(f"Face{n}" for n, f in enumerate(self.shaft.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Cylinder")
        self.volume = self.shaft.Shape.Volume

    def thread(self, **settings):
        thread = shaft_threads.make(self.body, self.shaft, self.face, "inches")
        for name, value in settings.items():
            setattr(thread, name, value)
        self.doc.recompute()
        self.assertTrue(thread.isValid(), thread.getStatusString())
        return thread

    def test_the_size_from_the_face(self):
        thread = self.thread()
        self.assertEqual((thread.ThreadType, thread.ThreadSize), ("UNC", "1/4"))

    def test_cosmetic_leaves_the_shaft_as_it_is(self):
        thread = self.thread()
        self.assertFalse(thread.Modeled)
        self.assertAlmostEqual(thread.Shape.Volume, self.volume, places=6)
        self.assertEqual(self.body.Tip, thread)

    def test_modeled_cuts_the_groove_its_full_length(self):
        thread = self.thread(Modeled=True)
        removed = self.volume - thread.Shape.Volume
        # a 60° thread's groove takes about a fifth of the ring between the major and minor diameters
        pitch = INCH / 20
        depth = 5 / 8 * math.sqrt(3) / 2 * pitch
        ring = math.pi * ((QUARTER / 2) ** 2 - (QUARTER / 2 - depth) ** 2) * LENGTH
        self.assertGreater(removed, 0.3 * ring)
        self.assertLess(removed, 0.8 * ring)
        self.assertEqual(len(thread.Shape.Solids), 1)

    def test_a_length_from_the_end(self):
        full = self.volume - self.thread(Modeled=True).Shape.Volume
        self.doc.removeObject(self.body.Tip.Name)
        part = self.volume - self.thread(Modeled=True, FullLength=False, Length=LENGTH / 2).Shape.Volume
        self.assertAlmostEqual(part / full, 0.5, delta=0.1)

    def test_left_handed(self):
        thread = self.thread(Modeled=True, LeftHanded=True)
        self.assertLess(thread.Shape.Volume, self.volume)

    def test_a_fit_makes_it_looser(self):
        plain = self.volume - self.thread(Modeled=True).Shape.Volume
        self.doc.removeObject(self.body.Tip.Name)
        loose = self.volume - self.thread(Modeled=True, Fit=0.2).Shape.Volume
        self.assertGreater(loose, plain)

    def test_the_fit_box_takes_it_as_a_thread(self):
        from studio.services import threads

        thread = self.thread()
        self.assertEqual(threads.threaded([thread, self.shaft]), [thread])
        threads.set_fit([thread], 0.2)
        self.assertAlmostEqual(threads.fit(thread), 0.2)

    def test_an_export_models_it_and_puts_it_back(self):
        from studio.services import threads

        thread = self.thread()
        with threads.modeled(self.doc):
            self.assertTrue(thread.Modeled)
            self.assertLess(thread.Shape.Volume, self.volume)
        self.assertFalse(thread.Modeled)
        self.assertAlmostEqual(thread.Shape.Volume, self.volume, places=6)

    def test_kept_in_the_file(self):
        import os
        import tempfile

        name = self.thread(Modeled=True, LeftHanded=True).Name
        path = os.path.join(tempfile.mkdtemp(), "Thread.FCStd")
        self.doc.saveAs(path)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.openDocument(path)
        again = self.doc.getObject(name)
        self.assertEqual((again.ThreadType, again.ThreadSize, again.Modeled, again.LeftHanded),
                         ("UNC", "1/4", True, True))
        self.doc.recompute()
        self.assertTrue(again.isValid(), again.getStatusString())

    def test_a_flat_face_isnt_threaded(self):
        flat = next(f"Face{n}" for n, f in enumerate(self.shaft.Shape.Faces, 1)
                    if f.Surface.__class__.__name__ == "Plane")
        with self.assertRaises(ValueError):
            shaft_threads.make(self.body, self.shaft, flat, "inches")
