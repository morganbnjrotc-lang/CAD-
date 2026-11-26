# SPDX-License-Identifier: LGPL-2.1-or-later
"""Threads (PLAN 3.9): modeled on export, and a fit for 3D-printed parts.

Threads stay cosmetic in the model, FreeCAD's default (a threaded hole is drilled at its tap-drill size,
no thread cut), which keeps the model light and quick; an export gets them modeled, for a printer or a
machinist. Inside `modeled(doc)` every cosmetic threaded hole is modeled; afterwards the document is as
it was, with no undo step left: the change is made in a transaction that is then rolled back.

A threaded hole's **fit** (`fit`, `set_fit`) is how much bigger (or, negative, smaller) its diameter is
made than standard, in mm: FreeCAD's custom thread clearance. FreeCAD applies it only to modeled threads;
Studio's FreeCAD applies it to cosmetic ones too, to their drilled hole (CORE_PATCHES.md), so the fit
picked on a cosmetic thread is the one an export models.

A Thread on a shaft (studio.services.shaft_threads, PLAN 3.20) counts too: its `Fit` makes the shaft that much
smaller across (looser, as a hole's makes it bigger), and an export models it while it is cosmetic.
"""

from contextlib import contextmanager

from studio.services.settings import Setting

MODEL_ON_EXPORT = Setting("Threads/ModelOnExport", True)


def is_shaft_thread(obj) -> bool:
    """Whether `obj` is a Thread on a round face (studio.services.shaft_threads)."""
    from studio.services import shaft_threads

    return isinstance(getattr(obj, "Proxy", None), shaft_threads.ThreadFeature)


def threaded(objects):
    """The threaded holes, and the Threads on shafts, among `objects`."""
    return [o for o in objects
            if (getattr(o, "TypeId", "") == "PartDesign::Hole" and o.Threaded) or is_shaft_thread(o)]


def fit(hole) -> float:
    """The thread's fit in mm on its diameter; 0 when it has none (standard)."""
    if is_shaft_thread(hole):
        return hole.Fit.Value
    if not hole.Threaded or not hole.UseCustomThreadClearance:
        return 0.0
    return hole.CustomThreadClearance.Value


def set_fit(holes, mm: float):
    """Gives each threaded hole among `holes` the fit `mm` and recomputes (the caller makes the undo step)."""
    changed = threaded(holes)
    for hole in changed:
        if is_shaft_thread(hole):
            hole.Fit = mm
            continue
        hole.UseCustomThreadClearance = True
        hole.CustomThreadClearance = mm
    documents = {hole.Document.Name: hole.Document for hole in changed}
    for document in documents.values():
        document.recompute()
    return changed


def cosmetic_holes(doc):
    """The holes with a thread that isn't modeled, and the cosmetic Threads on shafts."""
    return [o for o in doc.Objects
            if (o.TypeId == "PartDesign::Hole" and o.Threaded and not o.ModelThread)
            or (is_shaft_thread(o) and not o.Modeled)]


def _model(thread, on):
    if is_shaft_thread(thread):
        thread.Modeled = on
    else:
        thread.ModelThread = on


@contextmanager
def modeled(doc):
    """Models every cosmetic thread of `doc` while inside; yields those holes."""
    holes = cosmetic_holes(doc)
    if not holes:
        yield []
        return
    own_step = not doc.HasPendingTransaction  # a panel's step open: change and change back by hand
    if own_step:
        doc.openTransaction("Model threads for export")
    try:
        for hole in holes:
            _model(hole, True)
        doc.recompute()
        yield holes
    finally:
        if own_step:
            doc.abortTransaction()
        else:
            for hole in holes:
                _model(hole, False)
        doc.recompute()
