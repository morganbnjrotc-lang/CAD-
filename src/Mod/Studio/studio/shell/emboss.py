# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Emboss tool in the app, like Fusion's (PLAN 4.3, docs/adr/0016; studio.services.emboss makes the feature).

Pick a sketch drawn on a plane along a round face (text, shapes) and press Emboss (on the toolbar for a sketch,
and under Create); then pick the round face, or pick both first. The sketch is wrapped onto the face and raised
from it (Emboss) or cut into it (Deboss) by the depth, shown straight away; picking another round face moves it
there. OK keeps it as one undo step and hides the sketch, as Extrude does; Cancel takes it away. Double-click it
in the model tree to change it.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import emboss as emboss_service
from studio.services import icons as icon_service

_panel = None


def current_panel():
    """The open Emboss panel, or None. A panel whose dialog was closed some other way (closing its document,
    another dialog) is dropped here."""
    global _panel
    if _panel is not None and not _panel.open():
        _panel.forget()
        _panel = None
    return _panel


def _round_face(obj, sub):
    """(feature, face) when `sub` of `obj` is a round face of a Part Design feature, else None."""
    if not sub.startswith("Face") or not obj.isDerivedFrom("PartDesign::Feature"):
        return None
    try:
        emboss_service.round_face(obj, sub)
    except Exception:
        return None
    return obj, sub


def picked():
    """(sketch, (feature, face) or None): one sketch picked, and maybe one round face; else None."""
    sketches, faces = [], []
    for pick in FreeCADGui.Selection.getSelectionEx():
        if pick.Object.TypeId == "Sketcher::SketchObject" and not pick.SubElementNames:
            sketches.append(pick.Object)
            continue
        for sub in pick.SubElementNames:
            face = _round_face(pick.Object, sub)
            if face is None:
                return None
            faces.append(face)
    if len(sketches) != 1 or len(faces) > 1:
        return None
    return sketches[0], (faces[0] if faces else None)


def start():
    """Opens the Emboss panel on the picked sketch (and face)."""
    chosen = picked()
    if chosen is None:
        return None
    sketch, face = chosen
    FreeCADGui.Selection.clearSelection()
    panel = EmbossPanel(sketch=sketch, face=face)
    FreeCADGui.Control.showDialog(panel)
    return panel


def _icon():
    return QtGui.QIcon(icon_service.icon_path("emboss"))


class _Picks:
    """Hears round faces picked while the panel is open."""

    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, doc, obj, sub, point):
        if current_panel() is not self.panel:
            return
        target = FreeCAD.getDocument(doc).getObject(obj)
        face = _round_face(target, sub or "") if target is not None else None
        if face is not None:
            QtCore.QTimer.singleShot(0, lambda: self.panel.use_face(*face))


class EmbossPanel:
    def __init__(self, sketch=None, face=None, emboss=None):
        """A new emboss of `sketch` (on `face`, or the face picked next), or `emboss` edited."""
        global _panel
        _panel = self
        self.emboss = emboss
        self.new = emboss is None
        self.sketch = sketch if self.new else emboss.Profile
        self.doc = self.sketch.Document
        self.doc_name = self.doc.Name
        self.doc.openTransaction("Emboss" if self.new else "Edit Emboss")
        self.form = self._build()
        self._picks = _Picks(self)
        FreeCADGui.Selection.addObserver(self._picks)
        if self.new and face is not None:
            self.use_face(*face)
        self._show()

    # -- the form ----------------------------------------------------------------------------------

    def _build(self):
        form = QtWidgets.QWidget()
        form.setObjectName("StudioEmbossPanel")
        form.setWindowTitle("Emboss")
        form.setWindowIcon(_icon())
        layout = QtWidgets.QFormLayout(form)
        self.face_label = QtWidgets.QLabel(objectName="embossFace", wordWrap=True)
        layout.addRow("Face", self.face_label)
        self.raised = QtWidgets.QRadioButton("Emboss: raised from the face", objectName="embossRaised")
        self.cut = QtWidgets.QRadioButton("Deboss: cut into the face", objectName="embossCut")
        is_cut = not self.new and self.emboss.TypeId == emboss_service.CUT
        (self.cut if is_cut else self.raised).setChecked(True)
        self.cut.toggled.connect(self._cut_changed)
        layout.addRow(self.raised)
        layout.addRow(self.cut)
        self.depth = FreeCADGui.UiLoader().createWidget("Gui::QuantitySpinBox")
        self.depth.setObjectName("embossDepth")
        self.depth.setProperty("unit", "mm")
        self.depth.setProperty("minimum", 0.0)
        self.depth.setProperty("rawValue", self.emboss.Depth.Value if not self.new else self._first_depth())
        self.depth.valueChanged.connect(self._depth_changed)
        layout.addRow("Depth", self.depth)
        self.problem = QtWidgets.QLabel(objectName="embossProblem", wordWrap=True)
        self.problem.setStyleSheet("color: #C0392B")
        layout.addRow(self.problem)
        return form

    @staticmethod
    def _first_depth():
        from studio.shell import units

        current = units.current()
        inches = current is not None and current.units == "inches"
        return 0.04 * 25.4 if inches else 1.0  # 0.04 in or 1 mm: shows on a print, quick to make

    def _show(self):
        if self.emboss is None:
            self.face_label.setText("Pick the round face to wrap the sketch onto")
            self.problem.setText("")
            return
        link, names = self.emboss.Face
        self.face_label.setText(f"{names[0]} of {link.Label}")
        valid = self.emboss.isValid()
        self.problem.setText("" if valid else self.emboss.getStatusString())

    # -- changes -----------------------------------------------------------------------------------

    def use_face(self, feature, face):
        """Wraps onto `feature`'s round face `face`: the emboss made, or moved there."""
        if self.emboss is None:
            body = feature.getParentGeoFeatureGroup()
            if body is None:
                return
            try:
                self.emboss = emboss_service.make(body, self.sketch, feature, face, self._depth(), self.cut.isChecked())
            except ValueError as e:
                self.problem.setText(str(e))
                return
            EmbossView(self.emboss.ViewObject)
        else:
            self.emboss.Face = (feature, [face])
        self._recompute()

    def _depth(self):
        return float(self.depth.property("rawValue"))  # mm

    def _depth_changed(self, quantity):
        if self.emboss is not None and quantity.Value > 0:
            self.emboss.Depth = quantity.Value
            self._recompute()

    def _cut_changed(self, cut):
        if self.emboss is not None:
            self.emboss = emboss_service.set_cut(self.emboss, cut)
            EmbossView(self.emboss.ViewObject)
            self._recompute()

    def _recompute(self):
        self.emboss.touch()
        self.doc.recompute()
        self._show()

    # -- the task dialog ---------------------------------------------------------------------------

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def accept(self):
        if self.emboss is None:  # no face picked: nothing made
            return self.reject()
        self.doc.recompute()
        self.sketch.Visibility = False  # as Extrude hides its sketch
        self.doc.commitTransaction()
        self._close()
        return True

    def reject(self):
        self.doc.abortTransaction()  # a new emboss goes; an edited one is as it was
        self.doc.recompute()
        self._close()
        return True

    def open(self):
        """Whether its dialog is still up, on a document still open."""
        return self.doc_name in FreeCAD.listDocuments() and bool(FreeCADGui.Control.activeDialog())

    def forget(self):
        """Stops hearing picks."""
        if self._picks is not None:
            FreeCADGui.Selection.removeObserver(self._picks)
            self._picks = None

    def _close(self):
        global _panel
        if _panel is self:
            _panel = None
        self.forget()
        FreeCADGui.Control.closeDialog()
        gui = FreeCADGui.getDocument(self.doc.Name)
        if gui is not None and gui.getInEdit() is not None:
            gui.resetEdit()


# -- the model tree ----------------------------------------------------------------------------------
class EmbossView:
    """The view provider proxy of an Emboss or Deboss: its icon and its panel."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object
        vobj.signalChangeIcon()  # the model tree drew the row before the proxy came

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return icon_service.icon_path("emboss")

    def claimChildren(self):
        return [self.Object.Profile] if getattr(self.Object, "Profile", None) is not None else []

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        FreeCADGui.Control.showDialog(EmbossPanel(emboss=vobj.Object))
        return True

    def unsetEdit(self, vobj, mode=0):
        return True

    def doubleClicked(self, vobj):
        FreeCADGui.ActiveDocument.setEdit(vobj.Object.Name, 0)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None


class _Watch:
    def slotFinishRestoreDocument(self, doc):
        for obj in doc.Objects:
            if isinstance(getattr(obj, "Proxy", None), emboss_service.EmbossFeature):
                if getattr(obj, "ViewObject", None) is not None and not isinstance(obj.ViewObject.Proxy, EmbossView):
                    EmbossView(obj.ViewObject)


_watch = None


def install_once():
    global _watch
    if _watch is None:
        _watch = _Watch()
        FreeCAD.addDocumentObserver(_watch)
    return _watch
