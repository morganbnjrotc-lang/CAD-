# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picking a sketch's regions while Extrude is open, like Fusion (PLAN 3.16; studio.services.profile_regions).

Part Design hides the sketch as soon as Extrude, Cut, Revolve or Revolve Cut starts, and the feature takes
the regions picked before it, no more: adding one meant cancelling, picking again and starting over. While
one of their panels is open, Studio shows the sketch again, and a click on one of its regions adds it to
the feature or takes it out; the preview follows. The region doesn't stay selected, so the next click on it
takes it out again. FreeCAD's OK hides the sketch (TaskDlgSketchBasedParameters::accept) and its Cancel of a
new feature shows it again; after an edit of an existing feature is cancelled, Studio hides it again.

A click is left to the panel while it picks something itself (a face to extrude up to, an axis): FreeCAD
has a selection gate on then.
"""

from dataclasses import dataclass

import FreeCAD
import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

from studio.services import profile_regions


@dataclass(frozen=True)
class _Open:
    """An open Extrude, Cut, Revolve or Revolve Cut panel, and its feature's sketch."""

    doc: str
    feature: str
    sketch: str

    def objects(self):
        if self.doc not in FreeCAD.listDocuments():
            return None, None
        doc = FreeCAD.getDocument(self.doc)
        return doc.getObject(self.feature), doc.getObject(self.sketch)


class Regions:
    """A FreeCADGui document observer (panels opening and closing) and a selection observer (clicks)."""

    def __init__(self):
        self._open = None

    # -- the panel opens and closes ----------------------------------------------------------
    def slotInEdit(self, view_provider):
        feature = getattr(view_provider, "Object", None)
        sketch = profile_regions.sketch_of(feature)
        if sketch is None:
            return
        self._open = _Open(feature.Document.Name, feature.Name, sketch.Name)
        sketch.ViewObject.show()  # Part Design's tool has just hidden it

    def slotResetEdit(self, view_provider):
        feature = getattr(view_provider, "Object", None)
        panel = self._open
        if panel is None or getattr(feature, "Name", None) != panel.feature:
            return
        self._open = None
        # Once FreeCAD's OK or Cancel has finished: Cancel deletes a new feature after the edit ends.
        QtCore.QTimer.singleShot(0, lambda: self._closed(panel))

    def slotDeletedDocument(self, gui_document):
        if self._open is not None and self._open.doc == gui_document.Document.Name:
            self._open = None

    def _closed(self, panel):
        feature, sketch = panel.objects()
        if feature is None or sketch is None or self._open == panel:
            return  # a new feature cancelled (FreeCAD shows its sketch), or its panel open again
        if sketch.ViewObject.isVisible():
            sketch.ViewObject.hide()  # an edit cancelled: as it was before

    # -- clicks ------------------------------------------------------------------------------
    def addSelection(self, doc, obj, sub, point):
        panel = self._open
        if panel is None or doc != panel.doc or obj != panel.sketch:
            return
        number = profile_regions.region(sub)
        if number is None:
            return
        import StudioGui

        if StudioGui.selection_gate():
            return  # the panel is picking something itself
        # Not from inside FreeCAD's selection call: the recompute and the clearing change the selection.
        QtCore.QTimer.singleShot(0, lambda: self._toggle(panel, number))

    def _toggle(self, panel, number):
        if self._open != panel:
            return
        feature, sketch = panel.objects()
        if feature is None:
            return
        if profile_regions.toggle(feature, number):
            feature.Document.recompute()
        FreeCADGui.Selection.clearSelection()


_regions = None


def install_once():
    global _regions
    if _regions is None:
        _regions = Regions()
        FreeCADGui.addDocumentObserver(_regions)
        FreeCADGui.Selection.addObserver(_regions)
    return _regions
