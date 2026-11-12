# SPDX-License-Identifier: LGPL-2.1-or-later
"""Interaction: tools as modal state machines, keymap and navigation.

Tools follow start -> preview -> (adjust)* -> commit | cancel, each inside one document
transaction. They reach the viewport only through abstract interfaces defined here, so they can be
tested with synthetic events. May import services. Must not import Qt, FreeCADGui or viewmodels.
"""
