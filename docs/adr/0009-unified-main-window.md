# 0009 — Unified main window: one toolbar on top that follows the selection

- **Status:** accepted (2026-11-14: the user picked option A, with every recommended smaller choice,
  from the layout page shown to them)
- **Date:** 2026-11-14

## Context

PLAN 2.6 replaces FreeCAD's per-workbench window with one environment: no workbench switcher, a
toolbar driven by the selection, one panel for the model tree and properties, laptop-friendly.
FreeCAD's window today has a menu bar of seven or more menus plus one per loaded module, about twenty
toolbars (including the workbench switcher), and the Combo View (tree above properties, with a
Tasks tab). Studio's workbench derives from `Gui::PythonWorkbench` and inherits FreeCAD's standard menus and
toolbars; activating it costs 150–230 ms ([ADR 0007](0007-lazy-loading-command-catalog.md)), and
`Gui::PythonBlankWorkbench` crashes the app when it is the start workbench.

The user was shown three layouts with mockups for each kind of selection: A, a labeled toolbar on top
(Fusion 360-like); B, a floating toolbar in the 3D view; C, a vertical rail. They chose A, with one
☰ menu, tree above properties in one collapsible panel, icon-and-label buttons and plain tool names.

## Decision

1. **Layout A.** A top bar with the ☰ menu, the document tabs and a search field that opens the command
   palette (`S`, `Ctrl+K`); under it one toolbar row whose tools follow the selection, each with icon and
   label; the panel on the left (FreeCAD's Combo View: tree above properties), closed and opened with
   one click; the 3D view; a status bar with a hint for the current selection.
2. **One ☰ menu** holding FreeCAD's own File, Edit, View and Help menus (the same menus, reused); FreeCAD's
   menu bar is hidden. Every other tool is in the toolbar, the palette or the keymap.
3. **The toolbar follows the selection.** A hand-written table in `studio/viewmodels` maps the kind of
   selection to the tools offered: nothing, a sketch, faces, edges, faces and edges mixed, a feature,
   editing a sketch. The view-model sorts the selection into one of these kinds from the selected
   objects' types and sub-elements, without Qt. Buttons run their commands through the command service
   (so they work before a module loads) and are enabled when the live command is active.
4. **Plain tool names** where FreeCAD's differ from common CAD words: Extrude (Pad), Cut (Pocket), Shell
   (Thickness), Revolve Cut (Groove), Sweep and Sweep Cut (Additive/Subtractive Pipe), Loft and Loft Cut.
   FreeCAD's name stays searchable in the palette and appears in the button's tooltip.
5. **Studio's workbench trims what it inherits** in `Initialize()`, through the Python workbench's own
   API (removing toolbars and menus), instead of switching to `PythonBlankWorkbench`. The activation
   cost is measured before and after.
6. **"Make default" on fields moves to Phase 3**, where Studio's own tool panels (the direct extrude tool
   and others) get fields with defaults. FreeCAD's property panel has no per-property defaults to set.

## Consequences

- FreeCAD's module toolbars and the workbench switcher never show; a tool is reached through the toolbar,
  the palette or its key.
- Menu mnemonics on Alt (e.g. Alt+F for File) go with the hidden menu bar.
- The table of tools per selection is ours to keep up to date; the catalog check (ADR 0007) catches
  commands that disappear upstream.
- Tool names differ from FreeCAD's documentation for those seven tools; tooltips name FreeCAD's term.
