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

    def test_a_cut_that_takes_nothing_is_an_error(self):
        # a groove that misses the shaft would leave it smooth with no sign: it has to show as an error
        real = shaft_threads.groove
        shaft_threads.groove = lambda *args, **kwargs: Part.makeBox(1, 1, 1, V(100, 100, 100))
        self.addCleanup(setattr, shaft_threads, "groove", real)
        thread = shaft_threads.make(self.body, self.shaft, self.face, "inches")
        thread.Modeled = True
        self.doc.recompute()
        self.assertFalse(thread.isValid())
        self.assertIn("couldn't be cut", thread.getStatusString())

    def test_an_export_tells_which_threads_it_couldnt_model(self):
        from studio.services import threads

        thread = self.thread()
        real = shaft_threads.groove
        shaft_threads.groove = lambda *args, **kwargs: Part.makeBox(1, 1, 1, V(100, 100, 100))
        self.addCleanup(setattr, shaft_threads, "groove", real)
        with threads.modeled(self.doc) as made:
            self.assertEqual(threads.not_modeled(made), [thread])
        shaft_threads.groove = real
        with threads.modeled(self.doc) as made:
            self.assertEqual(threads.not_modeled(made), [])

    def breaks_when_modeled(self):
        """A feature after the thread that fails once the thread is modeled, as a chamfer on a threaded hole's
        edge does (the edge it names is gone)."""
        breaks = self.body.newObject("PartDesign::FeaturePython", "Breaks")
        _BreaksWhenModeled(breaks, self.volume)
        self.doc.recompute()
        self.assertTrue(breaks.isValid(), breaks.getStatusString())
        return breaks

    def test_an_export_tells_when_a_feature_after_the_thread_fails(self):
        from studio.services import threads

        thread = self.thread()
        self.breaks_when_modeled()
        with threads.modeled(self.doc) as made:
            self.assertTrue(thread.isValid())
            self.assertEqual(threads.not_modeled(made), [thread])

    def test_an_export_tells_when_a_thread_waits_on_a_failed_body(self):
        # the user's stem is drawn on the flower's hole: when the flower fails, FreeCAD skips the stem, which
        # keeps its cosmetic shape with no error of its own
        from studio.services import threads

        thread = self.thread()
        breaks = self.breaks_when_modeled()
        doc, other, pad, face = self.doc, None, None, None
        other = doc.addObject("PartDesign::Body", "Other")
        sketch = other.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(other.Origin.OriginFeatures[3], "")]
        sketch.MapMode = "FlatFace"
        sketch.addGeometry(Part.Circle(V(50, 0, 0), V(0, 0, 1), QUARTER / 2))
        pad = other.newObject("PartDesign::Pad", "Stem")
        pad.Profile = sketch
        pad.Length = LENGTH
        doc.recompute()
        face = next(f"Face{n}" for n, f in enumerate(pad.Shape.Faces, 1)
                    if f.Surface.__class__.__name__ == "Cylinder")
        waits = shaft_threads.make(other, pad, face, "inches")
        waits.FullLength = False
        waits.setExpression("Length", f"{breaks.Name}.Size")
        doc.recompute()
        self.assertTrue(waits.isValid(), waits.getStatusString())
        with threads.modeled(doc) as made:
            self.assertEqual(set(threads.not_modeled(made)), {thread, waits})


class _BreaksWhenModeled:
    def __init__(self, obj, smooth_volume):
        obj.Proxy = self
        obj.addProperty("App::PropertyFloat", "Smooth")
        obj.Smooth = smooth_volume
        obj.addProperty("App::PropertyLength", "Size")
        obj.Size = 5.0

    def execute(self, obj):
        base = obj.BaseFeature.Shape
        if base.Volume < obj.Smooth - 1e-6:
            raise RuntimeError("the edge it names is gone")
        obj.Shape = base.copy()


def shaft(diameter, length):
    """A new document's body with a round shaft `diameter` across and `length` long, up from the XY plane:
    (doc, body, the shaft's Pad, its round face's name)."""
    doc = FreeCAD.newDocument("ShaftThreads" + uuid.uuid4().hex[:8])
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sketch.MapMode = "FlatFace"
    sketch.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), diameter / 2))
    pad = body.newObject("PartDesign::Pad", "Shaft")
    pad.Profile = sketch
    pad.Length = length
    doc.recompute()
    face = next(f"Face{n}" for n, f in enumerate(pad.Shape.Faces, 1) if f.Surface.__class__.__name__ == "Cylinder")
    return doc, body, pad, face


def radii(shape, z):
    """The nearest and farthest a cut through `shape` at height `z` comes to the Z axis."""
    section = shape.slice(V(0, 0, 1), z)
    points = [p for wire in section for p in wire.discretize(720)]
    distances = [math.hypot(p.x, p.y) for p in points]
    return min(distances), max(distances)


class EverySize(unittest.TestCase):
    """The user, 2026-11-26: the stem's 1/2-13 thread came out of an export smooth. The groove's sweep (one
    long helix) failed, with no error, for about half the standard sizes and lengths; these are some."""

    CASES = [  # (standard, size, threaded length mm): each cut nothing, or failed, before
        ("UNC", "1/2", 10.16), ("UNC", "1/4", 25.4), ("UNC", "3/8", 25.4), ("UNF", "1/4", 10.16),
        ("UNF", "#1", 25.4), ("ISOMetricProfile", "M6x1.0", 10.16), ("ISOMetricProfile", "M8x1.25", 10.16),
        ("ISOMetricProfile", "M16x2.0", 25.4),
    ]

    def modeled(self, standard, name, length, diameter=None):
        chosen = shaft_threads.size(standard, name)
        doc, body, pad, face = shaft(diameter or chosen.diameter, length + 10)
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        thread = shaft_threads.make(body, pad, face, "inches")
        shaft_threads.set_size(thread, standard, name)
        thread.FullLength = False
        thread.Length = length
        thread.Modeled = True
        doc.recompute()
        return pad, thread

    def test_the_groove_is_cut_on_every_size(self):
        for standard, name, length in self.CASES:
            with self.subTest(size=name, length=length):
                pad, thread = self.modeled(standard, name, length)
                self.assertTrue(thread.isValid(), thread.getStatusString())
                chosen = shaft_threads.size(standard, name)
                r = chosen.diameter / 2
                depth = 5 / 8 * math.sqrt(3) / 2 * chosen.pitch
                ring = math.pi * (r * r - (r - depth) ** 2) * length
                removed = pad.Shape.Volume - thread.Shape.Volume
                self.assertGreater(removed, 0.3 * ring)
                self.assertLess(removed, 0.8 * ring)
                self.assertEqual(len(thread.Shape.Solids), 1)

    def test_a_thicker_face_is_turned_down_to_the_size(self):
        # the user's stem: 0.56 in across, threaded 1/2-13 for 0.4 in from its end, to screw into a 1/2-13
        # hole; the thread is the size's (1/2 in across), not the face's, and the rest stays as it was
        pad, thread = self.modeled("UNC", "1/2", 0.4 * INCH, diameter=0.56 * INCH)
        self.assertTrue(thread.isValid(), thread.getStatusString())
        box = pad.Shape.BoundBox  # the shaft is 0.4 in + 10 mm long: 0.2 in from one end is threaded
        threaded, plain = sorted((radii(thread.Shape, box.ZMin + 0.2 * INCH),
                                  radii(thread.Shape, box.ZMax - 0.2 * INCH)), key=lambda r: r[1])
        root = 0.25 * INCH - 5 / 8 * math.sqrt(3) / 2 * INCH / 13
        self.assertAlmostEqual(threaded[1], 0.25 * INCH, delta=0.03)
        self.assertAlmostEqual(threaded[0], root, delta=0.05)
        self.assertAlmostEqual(plain[0], 0.28 * INCH, delta=0.01)
        self.assertAlmostEqual(plain[1], 0.28 * INCH, delta=0.01)
