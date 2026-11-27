# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Text tool in the app, like Fusion's (PLAN 4.1, docs/adr/0015; studio.services.sketch_text lays the text
out, studio.viewmodels.text_panel holds the panel's choices).

While a sketch is edited, Text (on the sketch toolbar and under Create) puts "Text" in the middle of the view
and opens the Text panel at the top of the Tasks panel (the sketch's own panel holds the rest): the text, one
line or more, the font by family and style among the installed ones, the capitals' height, alignment, line
spacing, and the box: fitted to the text, or of its own size. Every change shows straight away. Drag the text
to place it (FreeCAD's sketcher drags a group whole). Finish keeps it as one undo step; Cancel takes it back.
With a text picked (a click on its letters picks it), Text edits it instead.

A text's font is kept in its sketch (PLAN 4.2), so the fonts offered are the computer's and, where one isn't
installed, the sketch's own copy; a font whose license forbids keeping it is used, and the panel says so.

Dragging the text while the panel is open makes an undo step of its own, which closes the panel's: Cancel
then puts the text back by hand (a new one removed, an edited one as it was).
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import fonts as font_service
from studio.services import sketch_text
from studio.viewmodels.text_panel import TextPanel, with_kept

PANEL = "StudioTextPanel"
DELAY_MS = 120  # typing: the text is redrawn once the keys pause

_installed = None
_panel = None


def installed_fonts():
    """The installed fonts, read once a session (about half a second the first time)."""
    global _installed
    if _installed is None:
        _installed = font_service.installed()
    return _installed


def current_panel():
    """The open Text panel, or None."""
    return _panel


def _sketch_in_edit():
    from studio.shell import sketching

    return sketching.sketch_in_edit()


def picked_text(sketch):
    """The frame of the Studio text picked in `sketch` (a click on its letters picks its frame), or None."""
    for pick in FreeCADGui.Selection.getSelectionEx():
        if pick.Object != sketch:
            continue
        for name in pick.SubElementNames:
            if name.startswith("Edge") and name[4:].isdigit():
                frame = int(name[4:]) - 1
                if frame < len(sketch.Geometry) and sketch_text.read(sketch, frame) is not None:
                    return frame
    return None


def view_center(sketch):
    """The middle of the 3D view, in the sketch's coordinates."""
    view = FreeCADGui.ActiveDocument.ActiveView
    width, height = view.getSize()
    point = view.getPoint(width // 2, height // 2)
    local = sketch.getGlobalPlacement().inverse().multVec(point)
    return local.x, local.y


def _units():
    from studio.shell import units

    current = units.current()
    return current.units if current is not None and current.units else "millimeters"


def start():
    """Opens the Text panel: on the picked text, or on a new one in the middle of the view."""
    sketch = _sketch_in_edit()
    if sketch is None:
        return None
    if _panel is not None:
        _panel.finish()
    frame = picked_text(sketch)
    if frame is not None:
        return TextPanelView(sketch, frame=frame)
    return TextPanelView(sketch, at=view_center(sketch))


class _EditEnds:
    """Finishes the panel when its sketch stops being edited (Close Sketch)."""

    def __init__(self, panel):
        self.panel = panel

    def slotResetEdit(self, view_provider):
        if getattr(view_provider, "Object", None) == self.panel.sketch:
            QtCore.QTimer.singleShot(0, self.panel.finish)


class TextPanelView:
    def __init__(self, sketch, frame=None, at=(0.0, 0.0)):
        global _panel
        self.sketch, self.doc = sketch, sketch.Document
        self.new = frame is None
        self.original = None if self.new else sketch_text.read(sketch, frame)
        self.found = with_kept(installed_fonts(), sketch_text.kept_fonts(sketch))
        self.model = TextPanel(self.found, _units(), box=self.original)
        self._step()
        if self.new:
            if self.model.font is None:
                FreeCAD.Console.PrintError("Studio: no fonts found for Text\n")
                self.doc.abortTransaction()
                return
            frame = sketch_text.add(sketch, self.model.box, self.model.font, at, step=False)
            self.doc.recompute()
        self.frame = frame
        self._timer = QtCore.QTimer(singleShot=True, interval=DELAY_MS)
        self._timer.timeout.connect(self.apply)
        self.form = self._build()
        self._observer = _EditEnds(self)
        FreeCADGui.addDocumentObserver(self._observer)
        _panel = self
        import StudioGui  # Studio's C++ helpers: the panel goes at the top of the sketch's Tasks panel

        if not StudioGui.add_task_panel(self.form):
            FreeCAD.Console.PrintWarning("Studio: the Text panel couldn't join the Tasks panel\n")
        self.text.setFocus(QtCore.Qt.OtherFocusReason)
        self.text.selectAll()

    # -- the form ----------------------------------------------------------------------------------

    def _build(self):
        # a parent: FreeCAD deletes it, not Python (StudioGui.add_task_panel)
        form = QtWidgets.QFrame(FreeCADGui.getMainWindow())
        form.setObjectName(PANEL)
        layout = QtWidgets.QFormLayout(form)
        title = QtWidgets.QLabel("<b>Edit Text</b>" if not self.new else "<b>Text</b>")
        layout.addRow(title)
        box = self.model.box

        self.text = QtWidgets.QPlainTextEdit(objectName="textText")
        self.text.setPlainText(box.text)
        self.text.setFixedHeight(self.text.fontMetrics().lineSpacing() * 4 + 12)
        self.text.textChanged.connect(lambda: self._change(self.model.set_text(self.text.toPlainText())))
        layout.addRow("Text", self.text)

        self.family = QtWidgets.QComboBox(objectName="textFamily")
        self.family.setMaxVisibleItems(20)
        self.family.addItems(self.model.families)
        self.style = QtWidgets.QComboBox(objectName="textStyle")
        self._fill_font()
        self.family.currentTextChanged.connect(self._family_changed)
        self.style.currentTextChanged.connect(self._style_changed)
        layout.addRow("Font", self.family)
        layout.addRow("Style", self.style)
        self.missing = QtWidgets.QLabel(objectName="textMissing", wordWrap=True)
        self.note = QtWidgets.QLabel(objectName="textNote", wordWrap=True)
        layout.addRow(self.missing)
        layout.addRow(self.note)
        self._notes()

        loader = FreeCADGui.UiLoader()
        self.height = self._size_box(loader, "textHeight", box.height, self.model.set_height)
        layout.addRow("Height", self.height)

        self.align = self._choice(("left", "center", "right"), ("Left", "Center", "Right"), box.align,
                                  self.model.set_align, "textAlign")
        self.valign = self._choice(("top", "middle", "bottom"), ("Top", "Middle", "Bottom"), box.valign,
                                   self.model.set_valign, "textVAlign")
        layout.addRow("Align", self.align)
        layout.addRow("", self.valign)

        self.spacing = QtWidgets.QDoubleSpinBox(objectName="textSpacing", minimum=0.5, maximum=5.0,
                                                singleStep=0.1, decimals=2)
        self.spacing.setValue(box.spacing)
        self.spacing.valueChanged.connect(lambda v: self._change(self.model.set_spacing(v)))
        layout.addRow("Line spacing", self.spacing)

        self.fit = QtWidgets.QCheckBox("Box fits the text", objectName="textFit")
        self.fit.setChecked(box.fit)
        self.fit.toggled.connect(self._fit_changed)
        layout.addRow(self.fit)
        self.width = self._size_box(loader, "textWidth", box.width, self.model.set_width)
        self.depth = self._size_box(loader, "textDepth", box.depth, self.model.set_depth)
        layout.addRow("Box width", self.width)
        layout.addRow("Box height", self.depth)
        self._box_fields()

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Finish")
        buttons.accepted.connect(self.finish)
        buttons.rejected.connect(self.cancel)
        layout.addRow(buttons)
        for keys, slot in (("Ctrl+Return", self.finish), ("Escape", self.cancel)):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(keys), form)
            shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)
        return form

    def _size_box(self, loader, name, mm, setter):
        field = loader.createWidget("Gui::QuantitySpinBox")
        field.setObjectName(name)
        field.setProperty("unit", "mm")
        field.setProperty("minimum", 0.0)
        field.setProperty("rawValue", mm)
        field.valueChanged.connect(lambda q: self._change(setter(q.getValueAs("mm").Value)))
        return field

    def _choice(self, values, labels, current, setter, name):
        row = QtWidgets.QWidget(objectName=name)
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QButtonGroup(row)
        for value, label in zip(values, labels):
            button = QtWidgets.QToolButton(text=label, checkable=True, objectName=f"{name}_{value}")
            button.setChecked(value == current)
            button.toggled.connect(lambda on, value=value: on and self._change(setter(value)))
            group.addButton(button)
            layout.addWidget(button)
        layout.addStretch(1)
        return row

    def _fill_font(self):
        for combo, items, current in ((self.family, None, self.model.box.family),
                                      (self.style, self.model.styles, self.model.box.style)):
            combo.blockSignals(True)
            if items is not None:
                combo.clear()
                combo.addItems(items)
            index = combo.findText(current)
            if index < 0 and current:  # a font that isn't installed: shown, not picked from the list
                combo.addItem(current)
                index = combo.count() - 1
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _notes(self):
        """The font isn't installed (and not kept), or can't be kept in the file."""
        for label, text in ((self.missing, self.model.missing), (self.note, self.model.note)):
            label.setText(text)
            label.setVisible(bool(text))

    def _family_changed(self, family):
        if family and self.model.set_family(family):
            self._fill_font()
            self._notes()
            self._change(True)

    def _style_changed(self, style):
        if style and self.model.set_style(style):
            self._notes()
            self._change(True)

    def _fit_changed(self, on):
        current = sketch_text.read(self.sketch, self.frame)  # the fitted size, to start the box's own from
        self.model.set_fit(on, current.width if current else None, current.depth if current else None)
        if not on:
            for field, mm in ((self.width, self.model.box.width), (self.depth, self.model.box.depth)):
                field.blockSignals(True)
                field.setProperty("rawValue", mm)
                field.blockSignals(False)
        self._box_fields()
        self._change(True)

    def _box_fields(self):
        for field in (self.width, self.depth):
            field.setEnabled(not self.model.box.fit)

    # -- changes -----------------------------------------------------------------------------------

    def _step(self):
        """The panel's undo step: opened again when a drag (its own step) closed it."""
        if not self.doc.HasPendingTransaction:
            self.doc.openTransaction("Text" if self.new else "Edit Text")

    def _change(self, accepted):
        if accepted:
            self._timer.start()

    def apply(self):
        """Redraws the text with the panel's settings (unless its font is missing)."""
        self._timer.stop()
        font = self.model.font
        if font is None or self.frame is None:
            return
        self._step()
        self.frame = sketch_text.edit(self.sketch, self.frame, self.model.box, font, step=False)
        self.doc.recompute()

    def finish(self):
        if _panel is not self:
            return
        if self._timer.isActive():
            self.apply()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()
        self.model.remember()
        self._close()

    def cancel(self):
        if _panel is not self:
            return
        self._timer.stop()
        if self.doc.HasPendingTransaction:
            self.doc.abortTransaction()
            self.doc.recompute()
        # a drag committed part of it: put it back by hand
        still = self.frame is not None and self.frame < len(self.sketch.Geometry) and \
            sketch_text.read(self.sketch, self.frame)
        if self.new and still:
            sketch_text.remove(self.sketch, self.frame)
        elif not self.new and still and still != self.original:
            font = font_service.find(self.original.family, self.original.style, self.found)
            if font is not None:
                sketch_text.edit(self.sketch, self.frame, self.original, font)
        self.doc.recompute()
        self._close()

    def _close(self):
        global _panel
        _panel = None
        FreeCADGui.removeDocumentObserver(self._observer)
        import StudioGui

        StudioGui.remove_task_panel(self.form)  # FreeCAD deletes it
        self.form = None
