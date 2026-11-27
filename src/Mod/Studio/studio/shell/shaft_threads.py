# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Thread tool in the app, like Fusion's (PLAN 3.20, docs/adr/0014; studio.services.shaft_threads makes the
feature).

Pick a round face (a shaft, a stud) and press Thread, on the toolbar or under Create: a Thread feature is added,
sized from the face, and its panel opens: the standard and size, Modeled (otherwise cosmetic), full length or a
length from the face's end, from the other end, left handed, and a Fit for 3D printing. Every change shows
straight away; OK keeps it, Cancel takes it away (one undo step). Double-click it in the model tree to change it.

A cosmetic thread shows FreeCAD's thread texture on the face, as a cosmetic hole thread does: laid over the
body's own drawing (so it stays while later features show the body), not pickable.
"""

import math

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

from studio.services import icons as icon_service
from studio.services import shaft_threads

OVERLAY = "StudioThreadOverlay"
TEXTURE = ":/images/ThreadOverlay.png"  # FreeCAD's, as Part Design's cosmetic hole threads use
AROUND = 64  # the overlay's columns around the face


def selected_round_face():
    """(feature, face name) of the one round face picked on a Part Design body's feature, or None."""
    picks = FreeCADGui.Selection.getSelectionEx()
    if len(picks) != 1 or len(picks[0].SubElementNames) != 1:
        return None
    feature, face = picks[0].Object, picks[0].SubElementNames[0]
    body = feature.getParentGeoFeatureGroup() if hasattr(feature, "getParentGeoFeatureGroup") else None
    if getattr(body, "TypeId", "") != "PartDesign::Body" or not face.startswith("Face"):
        return None
    try:
        shaft_threads.round_face(feature, face)
    except Exception:
        return None
    return feature, face


def start():
    """Threads the picked round face and opens the Thread panel."""
    picked = selected_round_face()
    if picked is None:
        return None
    from studio.shell import units

    feature, face = picked
    doc = feature.Document
    doc.openTransaction("Thread")
    current = units.current()
    thread = shaft_threads.make(feature.getParentGeoFeatureGroup(), feature, face,
                                current.units if current is not None and current.units else "millimeters")
    ThreadView(thread.ViewObject)
    doc.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Control.showDialog(ThreadPanel(thread, new=True))
    return thread


# -- the panel -------------------------------------------------------------------------------------
_panel = None


def current_panel():
    """The open Thread panel, or None (for tests)."""
    return _panel


class ThreadPanel:
    def __init__(self, thread, new):
        global _panel
        _panel = self
        self.thread, self.new = thread, new
        self.doc = thread.Document
        if not new:
            self.doc.openTransaction("Edit Thread")
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("StudioThreadPanel")
        self.form.setWindowTitle("Thread")
        self.form.setWindowIcon(_icon())
        layout = QtWidgets.QFormLayout(self.form)
        loader = FreeCADGui.UiLoader()

        self.standard = QtWidgets.QComboBox(objectName="threadStandard")
        self.size = QtWidgets.QComboBox(objectName="threadSize")
        self.modeled = QtWidgets.QCheckBox("Modeled (real grooves: slower)", objectName="threadModeled")
        self.full = QtWidgets.QCheckBox("Full length", objectName="threadFullLength")
        self.length = loader.createWidget("Gui::QuantitySpinBox")
        self.length.setObjectName("threadLength")
        self.other_end = QtWidgets.QCheckBox("From the other end", objectName="threadReversed")
        self.left = QtWidgets.QCheckBox("Left-handed", objectName="threadLeftHanded")
        self.fit = loader.createWidget("Gui::QuantitySpinBox")
        self.fit.setObjectName("threadFit")
        self.fit.setToolTip("How much smaller across than standard: + is looser, for 3D printing")
        for row in (("Standard", self.standard), ("Size", self.size), ("", self.modeled), ("", self.full),
                    ("Length", self.length), ("", self.other_end), ("", self.left), ("Fit", self.fit)):
            layout.addRow(row[0], row[1])
        self._fill()
        self.standard.currentIndexChanged.connect(self._standard_changed)
        self.size.currentIndexChanged.connect(self._size_changed)
        for box, prop in ((self.modeled, "Modeled"), (self.full, "FullLength"), (self.other_end, "Reversed"),
                          (self.left, "LeftHanded")):
            box.toggled.connect(lambda on, prop=prop: self._set(prop, on))
        self.length.valueChanged.connect(lambda q: self._set("Length", _mm(q)))
        self.fit.valueChanged.connect(lambda q: self._set("Fit", _mm(q)))

    def _fill(self):
        t = self.thread
        self.standard.blockSignals(True)
        self.standard.clear()
        for standard in shaft_threads.NAMES:
            self.standard.addItem(shaft_threads.NAMES[standard], standard)
        self.standard.setCurrentIndex(self.standard.findData(t.ThreadType))
        self.standard.blockSignals(False)
        self._fill_sizes()
        self.modeled.setChecked(t.Modeled)
        self.full.setChecked(t.FullLength)
        self.length.setProperty("unit", "mm")
        self.length.setProperty("rawValue", t.Length.Value)
        self.length.setEnabled(not t.FullLength)
        self.other_end.setChecked(t.Reversed)
        self.left.setChecked(t.LeftHanded)
        self.fit.setProperty("unit", "mm")
        self.fit.setProperty("minimum", -5.0)
        self.fit.setProperty("rawValue", t.Fit.Value)

    def _fill_sizes(self):
        self.size.blockSignals(True)
        self.size.clear()
        for s in shaft_threads.sizes(self.thread.ThreadType):
            self.size.addItem(s.name, s.name)
        self.size.setCurrentIndex(self.size.findData(self.thread.ThreadSize))
        self.size.blockSignals(False)

    def _standard_changed(self, _index):
        standard = self.standard.currentData()
        face = shaft_threads.round_face(self.thread.Face[0], self.thread.Face[1][0])
        candidates = shaft_threads.sizes(standard)
        nearest = min(candidates, key=lambda s: abs(s.diameter - 2 * face.Surface.Radius))
        shaft_threads.set_size(self.thread, standard, nearest.name)
        self._fill_sizes()
        self._recompute()

    def _size_changed(self, _index):
        shaft_threads.set_size(self.thread, self.thread.ThreadType, self.size.currentData())
        self._recompute()

    def _set(self, prop, value):
        setattr(self.thread, prop, value)
        if prop == "FullLength":
            self.length.setEnabled(not value)
        self._recompute()

    def _recompute(self):
        self.thread.touch()
        self.doc.recompute()

    def getStandardButtons(self):
        # the flags as they are: FreeCAD reads Qt's enums (PySide6's can't be made an int)
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def accept(self):
        self.doc.recompute()
        self.doc.commitTransaction()
        self._close()
        return True

    def reject(self):
        if self.new:
            remove_overlay(self.thread)
        self.doc.abortTransaction()  # a new thread goes; an edited one is as it was
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        global _panel
        if _panel is self:
            _panel = None
        FreeCADGui.Control.closeDialog()
        gui = FreeCADGui.getDocument(self.doc.Name)
        if gui is not None and gui.getInEdit() is not None:
            gui.resetEdit()


def _mm(quantity):
    return quantity.Value if hasattr(quantity, "Value") else float(quantity)


def _icon():
    from PySide import QtGui

    return QtGui.QIcon(icon_service.icon_path("thread"))


# -- the model tree and the 3D view ----------------------------------------------------------------
class ThreadView:
    """The view provider proxy of a Thread feature: its icon, its panel, its cosmetic texture."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object
        vobj.signalChangeIcon()  # the model tree drew the row before the proxy came

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return icon_service.icon_path("thread")

    def updateData(self, obj, prop):
        if prop in ("Shape", "Modeled", "Face", "ThreadPitch", "FullLength", "Length", "Reversed", "LeftHanded"):
            QtCore.QTimer.singleShot(0, lambda: update_overlay(obj))

    def onChanged(self, vobj, prop):
        if prop == "Visibility":
            QtCore.QTimer.singleShot(0, lambda: update_overlay(vobj.Object))

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        FreeCADGui.Control.showDialog(ThreadPanel(vobj.Object, new=False))
        return True

    def unsetEdit(self, vobj, mode=0):
        return True

    def doubleClicked(self, vobj):
        FreeCADGui.ActiveDocument.setEdit(vobj.Object.Name, 0)
        return True

    def onDelete(self, vobj, subelements):
        remove_overlay(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _body_root(thread):
    body = thread.getParentGeoFeatureGroup()
    return getattr(getattr(body, "ViewObject", None), "RootNode", None)


def _shown(thread):
    """As FreeCAD's cosmetic hole threads: while the body shows the thread or a feature after it."""
    body = thread.getParentGeoFeatureGroup()
    if thread.Modeled or body is None or not body.Visibility or thread not in body.Group:
        return False
    group = body.Group
    return any(getattr(f, "Visibility", False) for f in group[group.index(thread):] if f.isDerivedFrom("PartDesign::Feature"))


def _body_roots(doc):
    from pivy import coin  # noqa: F401  (FreeCAD hands out Coin nodes only once pivy is loaded)

    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body" and getattr(obj, "ViewObject", None) is not None:
            yield obj.ViewObject.RootNode


def _named(root, name):
    return [i for i in range(root.getNumChildren()) if root.getChild(i).getName().getString() == name]


def remove_overlay(thread, doc=None, name=None):
    """Takes a thread's texture away, wherever it is (the thread may be on its way out of its body)."""
    doc = doc or thread.Document
    name = f"{OVERLAY}_{name or thread.Name}"
    for root in _body_roots(doc):
        for i in reversed(_named(root, name)):
            root.removeChild(i)


def overlay(thread):
    """The overlay node of a thread, or None (for tests)."""
    for root in _body_roots(thread.Document):
        found = _named(root, f"{OVERLAY}_{thread.Name}")
        if found:
            return root.getChild(found[0])
    return None


def update_overlay(thread):
    """Draws (or takes away) a cosmetic thread's texture on its face."""
    try:
        if thread.Document is None:
            return
    except Exception:  # deleted meanwhile
        return
    remove_overlay(thread)
    if not _shown(thread):
        return
    root = _body_root(thread)
    try:
        node = _overlay_node(thread)
    except Exception as exc:
        FreeCAD.Console.PrintLog(f"Studio: no texture for {thread.Name}: {exc}\n")
        return
    if root is not None and node is not None:
        root.addChild(node)


def _overlay_node(thread):
    from pivy import coin

    link, names = thread.Face
    face = shaft_threads.round_face(link, names[0])
    surface = face.Surface
    start, end = shaft_threads.span(thread, face)
    pitch = thread.ThreadPitch.Value
    radius = surface.Radius * 1.001 + 0.002  # just outside, so it doesn't fight the face for the pixels
    rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), surface.Axis)
    rows = max(2, int(math.ceil((end - start) / (pitch / 2))))
    hand = -1.0 if thread.LeftHanded else 1.0
    points, normals, uvs = [], [], []
    for j in range(rows + 1):
        z = start + (end - start) * j / rows
        for i in range(AROUND + 1):
            a = 2 * math.pi * i / AROUND
            local = FreeCAD.Vector(radius * math.cos(a), radius * math.sin(a), z)
            p = surface.Center + rotation.multVec(local)
            n = rotation.multVec(FreeCAD.Vector(math.cos(a), math.sin(a), 0))
            points.append((p.x, p.y, p.z))
            normals.append((n.x, n.y, n.z))
            uvs.append((hand * i / AROUND, (z - start) / pitch))
    index = []
    width = AROUND + 1
    for j in range(rows):
        for i in range(AROUND):
            a, b, c, d = j * width + i, j * width + i + 1, (j + 1) * width + i + 1, (j + 1) * width + i
            index += [a, b, c, -1, a, c, d, -1]

    sep = coin.SoSeparator()
    sep.setName(f"{OVERLAY}_{thread.Name}")
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    material = coin.SoMaterial()
    color = _shape_color(thread)
    material.diffuseColor.setValue(color[0], color[1], color[2])
    texture = coin.SoTexture2()
    texture.filename = TEXTURE
    texture.wrapS = coin.SoTexture2.REPEAT
    texture.wrapT = coin.SoTexture2.REPEAT
    coordinates = coin.SoTextureCoordinate2()
    coordinates.point.setValues(0, len(uvs), uvs)
    binding = coin.SoNormalBinding()
    binding.value = coin.SoNormalBinding.PER_VERTEX_INDEXED
    normal = coin.SoNormal()
    normal.vector.setValues(0, len(normals), normals)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    faces = coin.SoIndexedFaceSet()
    faces.coordIndex.setValues(0, len(index), index)
    faces.normalIndex.setValues(0, len(index), index)
    for child in (pick, material, texture, coordinates, binding, normal, coords, faces):
        sep.addChild(child)
    return sep


def _shape_color(thread):
    body = thread.getParentGeoFeatureGroup()
    tip = getattr(body, "Tip", None) or thread
    try:
        c = tip.ViewObject.ShapeAppearance[0].DiffuseColor
        return c[0], c[1], c[2]
    except Exception:
        return 0.8, 0.8, 0.8


class _Watch:
    """Keeps textures right when the body's features show or hide (FreeCAD document observer)."""

    def slotChangedObject(self, obj, prop):
        if prop != "Visibility" or obj.Document.Restoring:
            return
        body = obj if obj.TypeId == "PartDesign::Body" else obj.getParentGeoFeatureGroup() \
            if hasattr(obj, "getParentGeoFeatureGroup") else None
        if getattr(body, "TypeId", "") != "PartDesign::Body":
            return
        for feature in body.Group:
            if getattr(getattr(feature, "Proxy", None), "__class__", None) is shaft_threads.ThreadFeature:
                QtCore.QTimer.singleShot(0, lambda f=feature: update_overlay(f))

    def slotDeletedObject(self, obj):
        """Cancel, an undo or a delete took a thread away: its texture goes too."""
        if isinstance(getattr(obj, "Proxy", None), shaft_threads.ThreadFeature):
            remove_overlay(obj, obj.Document, obj.Name)

    def slotFinishRestoreDocument(self, doc):
        for obj in doc.Objects:
            if isinstance(getattr(obj, "Proxy", None), shaft_threads.ThreadFeature):
                if getattr(obj, "ViewObject", None) is not None and not isinstance(obj.ViewObject.Proxy, ThreadView):
                    ThreadView(obj.ViewObject)
                QtCore.QTimer.singleShot(0, lambda o=obj: update_overlay(o))


_watch = None


def install_once():
    global _watch
    if _watch is None:
        _watch = _Watch()
        FreeCAD.addDocumentObserver(_watch)
    return _watch
