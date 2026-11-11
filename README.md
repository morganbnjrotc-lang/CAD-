# CAD (working title)

A fast, fully local, lightweight CAD/CAM application built on top of [FreeCAD](https://github.com/FreeCAD/FreeCAD) — with a radically cleaner interface.

> **Status:** planning. This repository currently contains the upstream FreeCAD source as our starting point. Nothing below is implemented yet unless marked ✅.

## Principles

1. **The UI gets out of your way.** Sparse by default, tools appear when relevant. No wall of toolbars.
2. **One environment.** No switching "workbenches" to go from modeling → assembly → drawings → CAM. Parts and assemblies live in the same document; CAM is a mode you toggle on a body.
3. **Fully local.** No accounts, no cloud, no telemetry. The only network call is an explicit "check for updates" (and optional, user-triggered part downloads).
4. **Fast and lightweight.** Instant startup, quick file loads, runs well on a laptop.
5. **Laptop friendly.** First-class trackpad navigation (pinch zoom, two-finger orbit) plus mouse.
6. **Sensible defaults, deep preferences.** Right-click any field → "Make default".

## Feature roadmap

Inspiration: the feature set shown in [this FizCAD demo](https://www.youtube.com/watch?v=YKVOVaaIY48). Legend for the FreeCAD column: **Has** = exists in FreeCAD core, **Partial** = exists but clunky/limited or addon-only, **Missing** = needs to be built.

### Core modeling

| Feature | FreeCAD today | What we need to do |
|---|---|---|
| Sketch → extrude, single-key shortcuts (`E` extrude) | Partial — Sketcher + PartDesign Pad, but multi-step, workbench-bound | Unified sketch/feature tools, hotkey-driven, in-viewport drag handles |
| Section view | Has — Std ClippingPlane / Part Section | Single clean toggle with draggable plane |
| Sketch on curved surfaces (wraps around) | Missing — sketches are planar; wrap only via Curves addon | New: surface-mapped sketches |
| Rich text tool (box / area / centered area, system fonts) | Partial — Draft ShapeString (single line, font file path) | Word-processor-style text editor in sketches |
| Fonts embedded in the file | Missing — ShapeString references a font path | Embed font data in the document |
| Text on curved surfaces + extrude in/out | Missing | Falls out of surface sketches + text tool |
| 3D sketches / wire routing with draggable nodes, extend by adding points | Partial — Draft BSpline/Wire + Part Sweep; Cables addon | Native 3D spline sketch with node handles + auto sweep (wires, cables, tubing) |
| Threads: cosmetic or modeled, toggle anytime, "model all threads on export" | Partial — PartDesign Hole can model threads, but per-feature and fixed at creation | Cosmetic-by-default threads, global "model on export" |
| Thread allowance/clearance scrubber (3D printing fits) | Partial — Hole has custom thread clearance | Scroll-to-adjust allowance, works on cosmetic + modeled |
| Auto hole chamfer | Partial — Hole countersink/countersink-ish options | One-click hole chamfer |
| Sheet metal: unfold animation, movable fold lines, auto seam relief cutouts | Partial — SheetMetal is an external addon | Bring in built-in, add animated unfold + relief options |

### Assemblies

| Feature | FreeCAD today | What we need to do |
|---|---|---|
| Joints (revolute, spherical/ball, etc.), drag to move | Has — Assembly workbench (1.0+) | Merge into the single environment; direct drag manipulation |
| No part-vs-assembly distinction | Partial — Std Part / App::Link exist but the UX separates them | One document type; a body becomes an assembly when you add parts |
| Import as clone or link; "file out of sync — reimport?" keeping local adjustments | Partial — App::Link to external files | Explicit clone/link prompt + change detection with reimport |
| Exploded views + animation | Partial — Assembly exploded views; animation is addon-only | Built-in |

### CAM

| Feature | FreeCAD today | What we need to do |
|---|---|---|
| CAM toggled on a body (icon on body, no environment switch) | Missing — separate CAM workbench + Job setup | CAM as a mode/badge on a body |
| One-click "Add vise" (auto placement, jaw width/opening, parallel height) | Missing | New fixture system |
| Automatic stock generation (auto, explicit size, or from a solid body) | Has — Job stock (box/cylinder/from base) | Simplify, make "auto" the default |
| Probing cycles (all sides, pick feature/bore, collision-aware, draggable points; Tormach first) | Partial — basic Probe op exists | Real probing wizard with collision checks |
| Adaptive 2D/3D, bores, chamfers, scallop | Has — Adaptive, Helix, Deburr, Surface/Waterline | Mostly UX; evaluate scallop quality |
| Fast full-job simulation; "accuracy" view (unmachined stock highlighted); realistic aluminum view | Partial — new CAM simulator exists, slower and fewer views | Faster sim, accuracy + realistic material modes |
| Multi-setup with "flip part this way" animation; sim result overlaid on next setup | Missing | New |

### Drawings

| Feature | FreeCAD today | What we need to do |
|---|---|---|
| Live-linked 2D drawings | Has — TechDraw | Cleaner UX |
| Auto views + auto scale-to-fit on "Create drawing" | Partial — projection groups, manual layout/scale | One-click drawing with auto layout |
| Auto dimensioning (None / Basic / Thorough) | Missing (only manual / limited) | New |
| Flat pattern view for sheet metal | Partial — via SheetMetal addon + TechDraw | Built-in |

### Visualization

| Feature | FreeCAD today | What we need to do |
|---|---|---|
| Display modes: "pretty" w/ shadows, gray box, realistic, hidden line | Partial — draw styles + basic shadows (1.0) | Polished presets |
| Perspective / orthographic toggle | Has | — |
| Animation studio (play, auto-explode) | Missing (addon) | New |
| Ray-traced render engine with studio environments | Partial — Render addon (external renderers) | Built-in path tracer |

### Navigation, files, and app

| Feature | FreeCAD today | What we need to do |
|---|---|---|
| Instant startup, fast loads | Partial — notably slow startup (Python workbench init) | Lazy-load modules, profile startup |
| Trackpad: pinch zoom, two-finger orbit; `F` focus selection, `Shift+F` fit all | Partial — Touchpad/Gesture nav styles; fit-selection is `V,S` | New default nav style + Blender-like hotkeys |
| Recent files browser (remove/hide entries) | Partial — Start page recents | Cleaner browser with management |
| Import STEP/IGES/STL/etc. as solids | Has | — |
| Import feature history from other CAD | Missing | Long-term |
| Fully offline, no telemetry | Has | Keep it that way |
| Parts library download (McMaster-style) with auto material detection | Missing (Parts Library addon is offline files) | Optional, user-triggered; legal review needed for third-party catalogs |
| Right-click any field → "Make default" | Missing | New |

### Our additions

_Add features here that go beyond the demo._

## Building

This currently builds exactly like upstream FreeCAD — see FreeCAD's build docs in [`README.FreeCAD.md`](README.FreeCAD.md) and the [developer guide](https://freecad.github.io/DevelopersHandbook/).

## License

This project is a fork of FreeCAD and is licensed under the **GNU LGPL v2.1 or later** — see [`LICENSE`](LICENSE). FreeCAD is © its contributors. Upstream is tracked as the `upstream` git remote so we can pull in fixes.
