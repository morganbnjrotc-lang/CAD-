# SPDX-License-Identifier: LGPL-2.1-or-later
"""Model all threads on export (PLAN 3.9).

Threads stay cosmetic in the model, FreeCAD's default (a threaded hole is drilled at the thread's size,
no thread cut), which keeps the model light and quick; an export gets them modeled, for a printer or a
machinist. Inside `modeled(doc)` every cosmetic threaded hole is modeled; afterwards the document is as
it was, with no undo step left: the change is made in a transaction that is then rolled back.
"""

from contextlib import contextmanager

from studio.services.settings import Setting

MODEL_ON_EXPORT = Setting("Threads/ModelOnExport", True)


def cosmetic_holes(doc):
    """The holes with a thread that isn't modeled."""
    return [o for o in doc.Objects
            if o.TypeId == "PartDesign::Hole" and o.Threaded and not o.ModelThread]


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
            hole.ModelThread = True
        doc.recompute()
        yield holes
    finally:
        if own_step:
            doc.abortTransaction()
        else:
            for hole in holes:
                hole.ModelThread = False
        doc.recompute()
