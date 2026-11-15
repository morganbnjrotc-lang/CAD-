# 0010 — Studio's own look: light and dark on Qt's Fusion style

- **Status:** accepted (2026-11-14: the user picked from the look options page: light and dark following
  Windows, teal accent in light, orange accent in dark, Studio line icons, soft-gradient 3D background)
- **Date:** 2026-11-14

## Context

PLAN 2.9 gives the app its own look. Under Studio's layout ([ADR 0009](0009-unified-main-window.md)) the
app still wears FreeCAD's: Qt's default Windows style, FreeCAD's multicolored icons, FreeCAD's blue-purple
3D background and dark grey property group rows.

FreeCAD has a theme system: a YAML file of named colors (tokens) feeds `FreeCAD.qss`, a 2,806-line
stylesheet applied to the whole app, and preference packs set the 3D and sketch colors. Measured on the
slim Release build, alternating six times on a busy machine, FreeCAD's Light theme adds about 190 ms to
startup (median 2.94 → 3.13 s), while Qt's Fusion style alone adds nothing measurable (2.94 s). Startup
is already above its 1.5 s budget (1.72–2.0 s), so the look can't spend 0.2 s.

FreeCAD reads `MainWindow/QtStyle` at startup and applies changes to it live. It loads icons through
`BitmapFactory`, which can take them from an outside folder (`Bitmaps/ExternalTheme`: `Enabled`, `Path`,
`PreferExternal`), falling back to its own for any name the folder lacks. That folder is read once, when
the GUI starts, and icons are cached where they're used, so FreeCAD can't recolor them when the mode
changes. Studio's `Init.py` runs before the GUI starts.

## Decision

1. **Two palettes, one design.** Light and dark sets of named colors in `studio/services/theme.py`: window
   and panels, text, borders, the 3D background (a soft vertical gradient), model faces and edges, sketch
   lines, highlights. The accent is **teal in light** and **orange `#F28D47` in dark** (the user's
   choice; the teal is `#0A7D73`, see the notes). The setting `Appearance/Mode` is `system` (default, follows Windows), `light` or `dark`.
   In `system` mode the app follows Windows while running (Qt's color-scheme change signal). The ☰ menu
   offers the three modes.
2. **Qt's Fusion style with a palette made from those colors** styles every widget, FreeCAD's dialogs
   included. Studio sets `MainWindow/QtStyle` to Fusion. A small stylesheet generated from the same colors
   covers only what a palette can't: Studio's own widgets (top bar, toolbar, panel headers, Home, palette,
   status hint) and the few FreeCAD widgets Fusion leaves plain (property group rows, tool panel boxes).
   FreeCAD's theme system and `FreeCAD.qss` are not used. If the user picks a FreeCAD stylesheet in
   Preferences, Studio leaves the app-wide palette alone.
3. **3D view and sketch colors are FreeCAD settings** (`View/…`, `Mod/Sketcher/General/…`). Studio writes
   them at startup and when the mode changes. It remembers what it wrote and skips any value the user has
   changed since, so a color picked in Preferences stays. Selection and hover highlights use the accent.
4. **Studio line icons** (about 40, one stroke weight on a 24 px grid) for the tools Studio shows and the
   tree's feature types. Two ways to draw them:
   - Surfaces Studio draws (toolbar, top bar, Home, palette) render them in the mode's text color, so
     they switch with the mode.
   - Places FreeCAD draws (model tree, ☰ menus, FreeCAD's dialogs) get them through FreeCAD's icon folder,
     set by `Init.py` before the GUI starts. They use one neutral grey that keeps at least 3:1 contrast on
     both the light and the dark panel, because those icons can't change with the mode. Tools without a
     Studio icon keep FreeCAD's.
5. **Home hides the empty Model panel** while no document is open (shown in the mock-up the user approved).
6. **Startup:** applying the look adds at most 30 ms, checked with the startup profiler and an A/B run
   before it lands.

## Implementation steps (PLAN 2.9)

1. Theme service, headless: palettes, mode resolution, FreeCAD color settings with user changes kept.
2. In the app: Fusion, palette, 3D and sketch colors; follow Windows; Appearance in the ☰ menu.
3. Studio's stylesheet: its own widgets, property rows and tool panels; Home hides the empty panel.
4. Line icons for Studio's surfaces and FreeCAD's icon folder.
5. Startup A/B, all suites, the user's try.

## Implementation notes

- **Step 1 (theme service)** `studio/services/theme.py`, tested headless (`StudioTests/test_theme.py`).
  Contrast is checked by the tests: text and secondary text ≥ 4.5:1 on window and panel in both modes,
  the accent ≥ 3:1, button text on the accent ≥ 4.5:1, the neutral icon grey `#7F8996` ≥ 3:1 on all four
  backgrounds (3.3–4.8:1). The light accent is one shade deeper than the swatch the user picked
  (`#0A7D73` instead of `#0B877D`): white text on the swatch was 4.4:1, now 5.0:1. Dark mode's orange
  button carries dark text (7.0:1); white on it would be 2.4:1.
- A document stores its own colors, so the model color applies to parts created from now on; files saved
  earlier keep theirs.
- **Step 2 (in the app)** `studio/shell/appearance.py`: the palette and FreeCAD's colors are applied when
  Studio activates; the app follows Windows through Qt's `colorSchemeChanged` signal; ☰ › Appearance offers
  Follow Windows, Light and Dark. The tree's edited and active rows take the soft accent too
  (`TreeView/TreeEditColor`, `TreeActiveColor`). Fusion is picked in `Init.py` (`theme.default_to_fusion`):
  set later, from Studio's activation, Qt restyled the finished window and the first start took ~0.2 s
  longer.
- Startup cost of step 2: Studio's call takes ~3 ms, timed inside the app. End-to-end A/B runs on a busy
  machine (CPU ~15%, runs spread over ±0.3 s) can't resolve the rest: three sessions gave median
  differences of −10 to +140 ms and mean differences of −13 to +64 ms. Re-measured on a quiet machine in
  PLAN 2.10.

## Consequences

- One design with two color sets; reference screenshots (PLAN 2.10) are taken in both modes.
- FreeCAD's theme packs are bypassed by default. Dialogs that rely on `FreeCAD.qss` may look plainer
  under Fusion; the user's try and the visual baselines are where that shows.
- Studio overwrites FreeCAD's default 3D and sketch colors, but never a color the user set.
- The tree's and menus' icons are neutral grey in both modes, while Studio's toolbar icons follow the
  text color.
- The stylesheet names a few FreeCAD widget classes (property editor, task panel); an upstream rename
  would undo that styling, and the visual baselines are what catch it.
