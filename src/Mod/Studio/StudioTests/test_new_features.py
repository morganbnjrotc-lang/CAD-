# SPDX-License-Identifier: LGPL-2.1-or-later
"""What a feature made in Studio starts as (PLAN 3.18; studio.services.new_features).

The user, 2026-11-26: "in the model tab extrusions are still called pads". A feature made now is named in the
model tree as the toolbar names its tool (Extrude, Cut, Revolve Cut, Shell…), when it still has FreeCAD's own
name; features already in a file keep theirs (the user's pick). And "does the CAD have American thread
patterns": a new hole starts in the user's units' thread standard, UNC 1/4 in inches, ISO metric M6x1.0 in
millimeters (the user's pick), instead of none.
"""

import unittest
import uuid

import FreeCAD

from studio.services import new_features


class _Body(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("NewFeatures" + uuid.uuid4().hex[:8])
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        self.body = self.doc.addObject("PartDesign::Body", "Body")

    def make(self, kind, name=None):
        return self.body.newObject(kind, name or kind.split("::")[1])


class Names(_Body):
    def test_an_extrude_is_named_extrude(self):
        self.assertEqual(new_features.plain_label(self.make("PartDesign::Pad")), "Extrude")

    def test_the_toolbars_names(self):
        for kind, name in (("PartDesign::Pocket", "Cut"), ("PartDesign::Revolution", "Revolve"),
                           ("PartDesign::Groove", "Revolve Cut"), ("PartDesign::Thickness", "Shell"),
                           ("PartDesign::AdditivePipe", "Sweep"), ("PartDesign::SubtractiveLoft", "Loft Cut"),
                           ("PartDesign::Mirrored", "Mirror"), ("PartDesign::LinearPattern", "Rectangular Pattern"),
                           ("PartDesign::PolarPattern", "Circular Pattern"), ("PartDesign::Boolean", "Combine")):
            with self.subTest(kind=kind):
                self.assertEqual(new_features.plain_label(self.make(kind)), name)

    def test_named_in_turn(self):
        first, second = self.make("PartDesign::Pad"), self.make("PartDesign::Pad")
        new_features.rename(first)
        new_features.rename(second)
        self.assertEqual((first.Label, second.Label), ("Extrude", "Extrude001"))

    def test_features_freecad_names_as_the_toolbar_does_keep_their_names(self):
        for kind in ("PartDesign::Fillet", "PartDesign::Chamfer", "PartDesign::Hole", "PartDesign::Draft"):
            with self.subTest(kind=kind):
                self.assertIsNone(new_features.plain_label(self.make(kind)))

    def test_a_name_given_by_a_script_is_kept(self):
        self.assertIsNone(new_features.plain_label(self.make("PartDesign::Pad", "Block")))

    def test_a_renamed_feature_is_kept(self):
        pad = self.make("PartDesign::Pad")
        pad.Label = "Stem"
        self.assertIsNone(new_features.plain_label(pad))
        self.assertFalse(new_features.rename(pad))
        self.assertEqual(pad.Label, "Stem")

    def test_the_second_of_freecads_names_too(self):
        self.make("PartDesign::Pad")
        self.assertEqual(new_features.plain_label(self.make("PartDesign::Pad")), "Extrude")  # Pad001


class HoleStart(_Body):
    def test_inches_start_with_a_quarter_inch_unc_thread(self):
        hole = self.make("PartDesign::Hole")
        self.assertTrue(new_features.start_hole(hole, "inches"))
        self.assertEqual((hole.ThreadType, hole.ThreadSize), ("UNC", "1/4"))

    def test_millimeters_start_with_an_m6_thread(self):
        hole = self.make("PartDesign::Hole")
        self.assertTrue(new_features.start_hole(hole, "millimeters"))
        self.assertEqual((hole.ThreadType, hole.ThreadSize), ("ISOMetricProfile", "M6x1.0"))

    def test_still_a_plain_drilled_hole(self):
        # a standard to pick sizes from; threads only when the user picks Tap drill or Threaded
        hole = self.make("PartDesign::Hole")
        new_features.start_hole(hole, "inches")
        self.assertFalse(hole.Threaded)

    def test_a_hole_with_a_standard_keeps_it(self):
        hole = self.make("PartDesign::Hole")
        hole.ThreadType = "UNF"
        self.assertFalse(new_features.start_hole(hole, "inches"))
        self.assertEqual(hole.ThreadType, "UNF")
