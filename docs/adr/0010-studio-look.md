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
   - Places FreeCAD draws (model tree, ☰ menus, FreeCAD's dialogs) get them under FreeCAD's own icon names,
     before FreeCAD builds those places. They use one neutral grey that keeps at least 3:1 contrast on
     both the light and the dark panel, because those icons can't change with the mode. Tools without a
     Studio icon keep FreeCAD's. (Planned through FreeCAD's external icon folder; changed in step 4, see
     the notes.)
5. **Home hides the empty Model panel** while no document is open (shown in the mock-up the user approved).
6. **Startup:** applying the look adds at most 30 ms, checked with the startup profiler and an A/B run
   before it lands.

## Implementation steps (PLAN 2.9)

1. Theme service, headless: palettes, mode resolution, FreeCAD color settings with user changes kept.
2. In the app: Fusion, palette, 3D and sketch colors; follow Windows; Appearance in the ☰ menu.
3. Studio's stylesheet: its own widgets, property rows and tool panels; Home hides the empty panel.
4. Line icons for Studio's surfaces and FreeCAD's places.
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
- **Step 3 (stylesheets and FreeCAD's panels)**, 2026-11-15. Studio's widgets restyle themselves when the
  look changes (`Appearance.follow`), each with a small stylesheet on its own widget, none app-wide: the
  top bar (search drawn as a field), the toolbar (hover and pressed in the soft accent), the status hint,
  Home (panel background, New Part as the accent button, file-type tiles redrawn in the mode's colors,
  hover on cards). Home hides the Model panel while it shows (no document, so the panel would be empty)
  and brings it back with the first document, also after the app was closed on Home: FreeCAD saves the
  panel hidden then, so Studio records that it hid it (`Home/PanelHidden`).
  FreeCAD's panels (`FreeCADPanels`): the property editor's group rows (FreeCAD reads their colors once,
  when it builds the editor: grey with blue text, 1.3:1 in dark), its tab box drawn flat (Fusion fills it
  a shade lighter than the panel), the panel title buttons' fixed dark icons tinted in the secondary text
  color, and FreeCAD's message color (`OutputWindow/colorText`, black by default) written like the other
  FreeCAD colors. The status bar and anything else under a FreeCAD stylesheet keep the old mode's colors
  after a live switch; Studio sets the status bar's stylesheet again on a switch. This part is in C++
  (`StudioGui.style_panels`; `panel_style` reads it back for the tests): done from Python, the wrappers
  it made (FreeCAD's model tree's above all) made FreeCAD abort at exit in up to half the runs after a
  workbench change (`docs/BASELINE.md`).
- **Step 4 (line icons)**, 2026-11-15. 48 drawings in `Resources/icons/line` (24 px grid, stroke 1.75, no
  fills, the neutral grey; tests check the style), mapped to FreeCAD's icon names in
  `studio/services/icons.py`: Studio's tools, Part Design's and Sketcher's features as the model tree shows
  them, datums and origin, the tree's eye icons, File and Edit commands. Subtractive features are their
  additive drawing with a minus. Studio's toolbar and palette draw them in the mode's text color
  (`studio/shell/icons.py`). For FreeCAD's places, Studio puts them into FreeCAD's icon cache under each
  name, with and without ".svg" (commands ask for "PartDesign_Pad", the model tree for "PartDesign_Pad.svg"),
  from `InitGui.py` (`StudioGui.add_icons`, C++: FreeCAD's Python `addIcon` refuses cached names and decodes
  each name separately). Not FreeCAD's external icon folder: with "prefer external" on, FreeCAD searches the
  folder, including a scan of every file in it, for each icon it loads, Studio's or not. The registration
  takes 9–13 ms at startup on a busy machine (logged: "Studio: 47 line icons in … ms"); FreeCAD's own SVG
  loader was slower, so Studio draws them with Qt directly at 32 px times the screen scale. The document
  icon at the top of the tree stays FreeCAD's: FreeCAD loads it before `InitGui.py` runs.
- **Step 5 (startup)**, 2026-11-15, slim Release, 10 interleaved rounds, machine ~15% busy (VS Code):
  inside the app the look takes 21.5 ms on a new profile and 21.7 ms on a returning one (median: icons
  11–12, palette and FreeCAD's colors and panels 8–9, Home 1.2), under the 30 ms decided above. End to end
  the medians were +46 ms (new profile) and +37 ms (returning) but the means −23 and −5 ms, with runs
  without the look spread from 3.12 to 4.13 s: the noise is larger than the effect. PLAN 2.10 checks
  startup on a quiet machine. The user tried steps 3 and 4 ("it looks amazing", "everything looks clean").
- Not done in step 3: FreeCAD's Tasks panel stays an empty box over the 3D view between tasks, and after
  a live switch its frame keeps the old colors until the next start. Every way of clearing it crashed
  FreeCAD on a workbench change, and holding FreeCAD's overlay widgets made the app abort at exit
  (`docs/BASELINE.md`). Lookups of FreeCAD widgets follow the rule written there: at startup, inside the
  Model panel, and nothing kept that FreeCAD destroys late.

## Consequences

- One design with two color sets; reference screenshots (PLAN 2.10) are taken in both modes.
- FreeCAD's theme packs are bypassed by default. Dialogs that rely on `FreeCAD.qss` may look plainer
  under Fusion; the user's try and the visual baselines are where that shows.
- Studio overwrites FreeCAD's default 3D and sketch colors, but never a color the user set.
- The tree's and menus' icons are neutral grey in both modes, while Studio's toolbar icons follow the
  text color.
- The stylesheet names a few FreeCAD widget classes (property editor, task panel); an upstream rename
  would undo that styling, and the visual baselines are what catch it.
