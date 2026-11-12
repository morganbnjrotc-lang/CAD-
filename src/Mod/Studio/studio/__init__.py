# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio: the fork's unified shell and services.

Layers, top to bottom (docs/adr/0002-layered-architecture.md). Dependencies point down only:

    Gui/ (Qt widgets)  ->  viewmodels  ->  interaction  ->  services  ->  FreeCAD kernel

Everything in this package is headless: no Qt, no FreeCADGui. StudioTests.test_architecture
enforces this.
"""
