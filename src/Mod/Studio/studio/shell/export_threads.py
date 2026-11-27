# SPDX-License-Identifier: LGPL-2.1-or-later
"""Model all threads on export, in the app (PLAN 3.9; studio.services.threads does the modeling).

FreeCAD's File > Export (also Ctrl+E and the command palette) ends in the export function of the module
its file type belongs to: ImportGui or Import for STEP and IGES, Mesh for STL, 3MF and the other mesh
formats. Studio wraps those functions, so the exported file gets every cosmetic thread modeled while
the model keeps them cosmetic. The modules are wrapped when FreeCAD first imports them (an import hook),
so startup doesn't load them. ☰ › Threads › Model Threads on Export switches it (on by default).
"""

import importlib.abc
import sys
from contextlib import ExitStack

from PySide import QtWidgets  # FreeCAD's PySide shim

from studio.services import threads

EXPORTING_MODULES = ("Import", "ImportGui", "Mesh")


def _settings():
    from studio.services.settings import Settings

    return Settings()


def wrap(module):
    """Makes `module.export` model the exported documents' cosmetic threads first, if the setting says so."""
    original = getattr(module, "export", None)
    if original is None or getattr(original, "studio_models_threads", False):
        return

    def export(objects, filename, *args, **kwargs):
        if not _settings().get(threads.MODEL_ON_EXPORT):
            return original(objects, filename, *args, **kwargs)
        documents = {o.Document.Name: o.Document for o in objects if getattr(o, "Document", None) is not None}
        with ExitStack() as stack:
            made = []
            for document in documents.values():
                made += stack.enter_context(threads.modeled(document))
            plain = [_name(hole) for hole in threads.not_modeled(made)]
            result = original(objects, filename, *args, **kwargs)
        if plain:
            _tell_not_modeled(plain)
        return result

    export.studio_models_threads = True
    export.__doc__ = original.__doc__
    module.export = export


def _name(hole):
    body = hole.getParentGeoFeatureGroup()
    return f"{hole.Label} in {body.Label}" if body is not None else hole.Label


def _tell_not_modeled(names):
    """Says, without stopping anything, which threads the exported file has plain."""
    import FreeCADGui
    from PySide import QtCore

    box = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Warning, "Export",
        "The file was written, but these threads couldn't be modeled, so they're plain in it:\n\n"
        + "\n".join(f"• {name}" for name in names)
        + "\n\nTurn on Modeled in a thread's panel to see why; another size or length may work.",
        QtWidgets.QMessageBox.Ok, FreeCADGui.getMainWindow())
    box.setObjectName("StudioThreadsNotModeled")
    box.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    box.open()


class _WrapOnImport(importlib.abc.MetaPathFinder):
    """Wraps an exporting module as soon as it has been imported."""

    def find_spec(self, name, path, target=None):
        if name not in EXPORTING_MODULES:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None and spec.loader is not None:
                loader = spec.loader
                execute = loader.exec_module

                def exec_module(module, _execute=execute):
                    _execute(module)
                    wrap(module)

                loader.exec_module = exec_module
                return spec
        return None


class ThreadsMenu:
    """☰ › Threads › Model Threads on Export."""

    def __init__(self, parent):
        self.menu = QtWidgets.QMenu("Threads", parent)
        self.action = self.menu.addAction("Model Threads on Export")
        self.action.setCheckable(True)
        self.action.setToolTip("Exported files get the threads modeled; the model keeps them cosmetic")
        self.action.triggered.connect(lambda on: _settings().set(threads.MODEL_ON_EXPORT, bool(on)))
        self.menu.aboutToShow.connect(self.sync)
        self.sync()

    def sync(self):
        self.action.setChecked(_settings().get(threads.MODEL_ON_EXPORT))


_menu = None


def install_once():
    global _menu
    if _menu is None:
        import FreeCADGui

        from studio.shell import window

        for name in EXPORTING_MODULES:
            if name in sys.modules:
                wrap(sys.modules[name])
        sys.meta_path.insert(0, _WrapOnImport())
        _menu = ThreadsMenu(FreeCADGui.getMainWindow())
        if window.current() is not None:
            window.current().extra_menus.append(_menu.menu)
    return _menu


def current():
    return _menu
