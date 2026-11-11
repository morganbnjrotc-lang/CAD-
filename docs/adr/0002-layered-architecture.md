# 0002 — Layered architecture in our own module

- **Status:** accepted
- **Date:** 2026-11-11

## Context

We need (a) most behavior testable without a GUI, to support test-driven development, and (b) our code kept apart
from FreeCAD's so upstream merges stay cheap.

## Decision

All new behavior lives in `src/Mod/Studio` (working codename) in these layers, with dependencies
pointing down only:

1. **Shell:** Qt widgets. Draws the UI and binds to view-models.
2. **View-models:** UI state in plain Python, no widgets.
3. **Interaction:** tools as modal state machines (start → preview → commit | cancel, one
   transaction each), keymap and navigation. Talks to the viewport through abstract interfaces.
4. **Domain services:** headless APIs over FreeCAD's App and modeling modules.
5. **Kernel:** FreeCAD, unchanged where possible.

FreeCAD files change only when no extension point exists, and every such change is logged in
`docs/CORE_PATCHES.md`.

## Consequences

- Layers 2–4 run under `FreeCADCmd` and are tested in milliseconds without a window.
- A single always-active workbench (the shell) can gather commands from every module, which is how we get "one environment".
- Some features (e.g. sketch on curved surfaces) will need kernel-level work; those get their own ADR and a logged core patch.
- More code up front (interfaces, view-models) than writing straight into Qt widgets; we accept that in exchange for testability.
