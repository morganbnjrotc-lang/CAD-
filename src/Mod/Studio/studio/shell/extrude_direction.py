# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude or cut by direction in the app, like Fusion (PLAN 3.5; studio.services.extrude decides).

While Part Design's Extrude (Pad) or Cut (Pocket) panel is open, Studio waits for the mouse to be let go
(the end of a drag of the length arrow, or of a click on it, which turns it around). A new extrude let
go pointing into the part becomes a cut, a new cut let go pointing out of it an extrude, straight away:
Studio presses the panel's OK, takes that step back and starts the other tool on the same sketch with
the same length, so the other tool's panel shows the result and its Cancel leaves nothing.

Whatever else ends a panel pointing the other way (a typed length and Return, Finish, an existing
feature edited) is redone as the other feature, as one undo step.

Swapping the feature while its panel stays open isn't possible: FreeCAD's resetEdit, which closing the
panel needs, commits the panel's transaction. So Studio uses only FreeCAD's own steps: OK, undo, the
other tool's command.
"""

from dataclasses import dataclass

import FreeCAD
import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

from studio.services import extrude

COMMAND = {extrude.PAD: "PartDesign_Pad", extrude.POCKET: "PartDesign_Pocket"}
STEP_NAME = {extrude.PAD: "Extrude", extrude.POCKET: "Cut"}


@dataclass(frozen=True)
class _Panel:
    """An open Extrude or Cut panel."""

    doc: str
    name: str  # the feature's
    new: bool  # made by this panel's tool, not an existing feature edited
    # The document's undo steps once the panel's OK commits its step. A new feature's step is counted
    # from its making, before the panel opens; an edit's only once something changes.
    undo_count_after: int

    def step_is_last(self, doc) -> bool:
        """Whether the document's last undo step is the panel's, just committed."""
        return not doc.HasPendingTransaction and doc.UndoCount == self.undo_count_after


def _kind(view_provider):
    return getattr(getattr(view_provider, "Object", None), "TypeId", "")


class _Created:
    """FreeCAD document observer: the last Extrude or Cut made, to tell a new one from one edited."""

    def __init__(self):
        self.last = None

    def slotCreatedObject(self, obj):
        if obj.TypeId in extrude.OTHER:
            self.last = (obj.Document.Name, obj.Name)


class Watcher:
    """FreeCADGui document observer for Extrude and Cut panels opening and closing."""

    def __init__(self, created):
        self._created = created
        self._panel = None
        self._watch = None  # StudioGui.watch_mouse_release id while a panel is open
        self._busy = False  # switching: the OK and the undo are Studio's own

    # -- the panel opens and closes ----------------------------------------------------------
    def slotInEdit(self, view_provider):
        if _kind(view_provider) not in extrude.OTHER:
            return
        obj = view_provider.Object
        doc = obj.Document
        after = doc.UndoCount + (0 if doc.HasPendingTransaction else 1)
        self._panel = _Panel(doc.Name, obj.Name, self._created.last == (doc.Name, obj.Name), after)
        if self._watch is None:
            import StudioGui

            self._watch = StudioGui.watch_mouse_release(self._let_go)

    def slotResetEdit(self, view_provider):
        if _kind(view_provider) not in extrude.OTHER:
            return
        panel, self._panel = self._panel, None
        self._stop_watching()
        if panel is not None and not self._busy:
            QtCore.QTimer.singleShot(0, lambda: self._after_panel(panel))

    def slotDeletedDocument(self, gui_document):
        """A document closed with its panel open: FreeCAD doesn't tell that its edit ended."""
        if self._panel is not None and self._panel.doc == gui_document.Document.Name:
            self._panel = None
            self._stop_watching()

    def _stop_watching(self):
        if self._watch is not None:
            import StudioGui

            StudioGui.unwatch_mouse_release(self._watch)
            self._watch = None

    # -- the mouse let go while the panel is open --------------------------------------------
    def _let_go(self):
        panel = self._panel
        feature = _feature(panel)
        if feature is None or not _in_edit(panel, feature):  # the panel went away without telling
            self._panel = None
            self._stop_watching()
            return
        if not panel.new or self._busy:
            return
        target = extrude.becomes(feature)
        if target is None:
            return
        sketch, length = feature.Profile[0], abs(feature.Length.Value)
        self._busy = True
        # Not from inside the mouse watch's call: closing the panel stops that watch.
        QtCore.QTimer.singleShot(0, lambda: self._accept(panel, sketch, length, target))

    def _accept(self, panel, sketch, length, target):
        dialog = FreeCADGui.Control.activeTaskDialog()
        if dialog is None:
            self._busy = False
            return
        dialog.accept()  # FreeCAD's OK: commits the feature as it is (nothing to see yet)
        QtCore.QTimer.singleShot(0, lambda: self._start_other(panel, sketch, length, target))

    def _start_other(self, panel, sketch, length, target):
        try:
            doc = FreeCAD.getDocument(panel.doc)
            if FreeCADGui.Control.activeDialog() or not panel.step_is_last(doc):
                return  # FreeCAD refused the OK, or something else happened meanwhile
            doc.undo()
        finally:
            self._busy = False
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(sketch)
        FreeCADGui.runCommand(COMMAND[target], 0)
        QtCore.QTimer.singleShot(0, lambda: _take_length(length))

    # -- a panel ended pointing the other way ------------------------------------------------
    def _after_panel(self, panel):
        feature = _feature(panel)
        if feature is None or _in_edit(panel, feature):
            return  # cancelled, or still being edited
        target = extrude.becomes(feature)
        doc = feature.Document
        if target is None or not panel.step_is_last(doc):
            return  # right as it is, or the last undo step isn't the panel's
        body = feature.getParentGeoFeatureGroup()
        kind, profile, length = feature.TypeId, feature.Profile, feature.Length.Value
        reversed_, refine = feature.Reversed, feature.Refine
        doc.undo()  # the panel's step: the feature is gone again, or back as it was before the edit
        doc.openTransaction(STEP_NAME[target])
        again = doc.getObject(panel.name) or body.newObject(kind, panel.name)
        again.Profile, again.Length, again.Reversed, again.Refine = profile, length, reversed_, refine
        doc.recompute()
        other = extrude.switch(again)
        _show_result(other)
        doc.recompute()
        doc.commitTransaction()


def _feature(panel):
    if panel is None or panel.doc not in FreeCAD.listDocuments():
        return None
    return FreeCAD.getDocument(panel.doc).getObject(panel.name)


def _in_edit(panel, feature):
    view_provider = FreeCADGui.getDocument(panel.doc).getInEdit()
    return getattr(view_provider, "Object", None) == feature


def _show_result(feature):
    """As Part Design's tools leave it: the new feature shows, its sketch and the solid before it don't."""
    feature.Visibility = True
    feature.Profile[0].Visibility = False
    if feature.BaseFeature is not None:
        feature.BaseFeature.Visibility = False


def _take_length(length):
    """Puts the length into the panel just opened (in mm), its number selected for typing over."""
    import StudioGui

    if StudioGui.set_field("lengthEdit", length):
        StudioGui.focus_field("lengthEdit")


_watcher = None


def install_once():
    global _watcher
    if _watcher is None:
        created = _Created()
        FreeCAD.addDocumentObserver(created)
        _watcher = Watcher(created)
        FreeCADGui.addDocumentObserver(_watcher)
    return _watcher
