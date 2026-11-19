# SPDX-License-Identifier: LGPL-2.1-or-later
"""Part Design's panels the Fusion way (PLAN 3.11): Fillet and Chamfer open ready to pick more edges.

FreeCAD opens them picking only when no edge was selected first; with one selected (Studio's toolbar
offers Fillet for a selected edge) the user had to press "Select" before another click counted. The
clicks go through FreeCAD's selection, as a click in the 3D view does.
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui

from StudioTests.gui.sketch_input import settle


class PicksEdges(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("Edges" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        body = self.doc.addObject("PartDesign::Body", "Body")
        self.box = body.newObject("PartDesign::AdditiveBox", "Box")
        self.doc.recompute()

    def close(self):
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
        settle(100)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def start(self, command, type_id):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, self.box.Name, "Edge1")
        FreeCADGui.runCommand(command, 0)
        settle(500)
        return next(o for o in self.doc.Objects if o.TypeId == type_id)

    def click_edge(self, edge):
        FreeCADGui.Selection.addSelection(self.doc.Name, self.box.Name, edge)
        settle(300)

    def test_fillet_takes_more_edges_straight_away(self):
        fillet = self.start("PartDesign_Fillet", "PartDesign::Fillet")
        self.click_edge("Edge3")
        self.assertEqual(sorted(fillet.Base[1]), ["Edge1", "Edge3"])

    def test_chamfer_takes_more_edges_straight_away(self):
        chamfer = self.start("PartDesign_Chamfer", "PartDesign::Chamfer")
        self.click_edge("Edge3")
        self.assertEqual(sorted(chamfer.Base[1]), ["Edge1", "Edge3"])

    def test_a_second_click_on_an_edge_takes_it_out(self):
        fillet = self.start("PartDesign_Fillet", "PartDesign::Fillet")
        self.click_edge("Edge3")
        self.click_edge("Edge3")
        self.assertEqual(fillet.Base[1], ["Edge1"])
