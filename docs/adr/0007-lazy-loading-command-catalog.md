# 0007 — One environment without loading every module: command catalog and on-demand loading

- **Status:** accepted (2026-11-14)
- **Date:** 2026-11-14

## Context

Phase 2 puts every tool (Part Design, Sketcher, Part, Assembly, TechDraw, CAM, Measure, …) in one
environment, with no workbench switching ([PLAN §2.2](../PLAN.md#22-key-design-choices)). It also
has to start in **≤ 1.5 s** (stretch goal 1.0 s); upstream FreeCAD takes about 2.0 s on the reference laptop
([BASELINE.md](../BASELINE.md#startup-profile-2026-11-14)).

How FreeCAD organises this today:

- Each module's `InitGui.py` only declares its workbench class. That's why the GUI init of all
  modules is cheap (one shared first-import cost aside).
- The workbench's `Initialize()` runs on **first activation**. It imports the module's GUI library
  (for example `import PartDesignGui`), and that import is what registers the module's commands and
  its compiled-in icons (`Q_INIT_RESOURCE`, `src/Mod/PartDesign/Gui/AppPartDesignGui.cpp`). Python
  workbenches (Assembly, CAM, Draft) register theirs from `Initialize()` too.
- So **before its module loads, a command has no name, text or icon in the running app.** A unified
  workbench whose `Initialize()` imports every module would load all of them at startup, because
  it is the start workbench.
- Activating even our empty workbench costs ~230 ms. It derives from `Gui::PythonWorkbench`, which
  brings FreeCAD's full standard menus and toolbars (an action and an icon per command). FreeCAD
  also has `Gui::PythonBlankWorkbench`, without them.

What the app knows about a command without loading its module: the command list and texts can be
read from a running FreeCAD (`FreeCADGui.Command.listAll()`, `Command.get(name).getInfo()` gives
menu text, tooltip, icon name and shortcut), and the icons exist as source SVGs in this repository
(e.g. `src/Mod/PartDesign/Gui/Resources/icons/*.svg`).

## Decision

1. **A command catalog**, shipped with Studio, lists every command the environment offers: FreeCAD
   command name, owning workbench, menu text, tooltip, icon, plus Studio's own fields (the context it
   applies in, for example "a sketch is selected", category, search keywords).
   - The FreeCAD-derived fields are **generated** by a tool that loads the modules in a real build
     and dumps `getInfo()`; icons are copied from the source SVGs at build time. Studio's fields are
     kept by hand in a separate file.
   - A GUI test regenerates the catalog in memory and **fails when it differs from the shipped
     one**, so an upstream merge that renames, removes or adds a command can't go unnoticed.
2. **The shell reads the catalog, not FreeCAD's command registry.** The palette (2.5), the keymap
   (2.4) and the contextual toolbar (2.6) show catalog entries and run them through one service
   (`studio/services`), which:
   - loads the owning module on first use, the way FreeCAD does on first activation: it runs the
     workbench's `Initialize()` once, without activating that workbench. For Python workbenches
     (Assembly, CAM) FreeCAD first creates a C++ workbench object and attaches it as
     `__Workbench__`; `Initialize()` fails without it (`appendToolbar`). Only `activateWorkbench`
     does that, and Python has no API for it. A small C++ helper in Studio does the same steps
     through `Gui::WorkbenchManager::createWorkbench` (exported), so FreeCAD's code stays unchanged.
     Once the object is attached, a later `activateWorkbench` skips that step and `Initialize()`, so
     nothing runs twice;
   - then runs the real command (`FreeCADGui.runCommand`), so FreeCAD's own command code, undo and
     macro recording stay unchanged;
   - decides whether a command applies from the catalog's context until the module is loaded, and
     asks the real command (`isActive()`) after that.

   No placeholder commands are registered in FreeCAD, so command names never clash with upstream's.
3. **Background warm-up for cheap modules only.** Once the window is idle, the service loads the
   modules that take under ~100 ms each (Sketcher, Part Design, Part, TechDraw, Spreadsheet, Assembly:
   ~150 ms together, see Measurements), one per idle moment, yielding to user input. **CAM (~0.6 s,
   a single blocking import) is never warmed up**: it loads on the first CAM action, with a busy
   indicator. Making CAM itself load faster belongs to Phase 8. Warm-up can be turned off in settings.
4. **The ~150–230 ms activation of Studio's workbench is tackled in 2.6, not here.** It derives from
   `Gui::PythonWorkbench` and so builds FreeCAD's full standard menus and toolbars. The obvious fix,
   `Gui::PythonBlankWorkbench`, **crashes the app** (access violation) when used as the start
   workbench (tried 2026-11-14 on the slim Release build). 2.6 either finds and fixes that crash or
   trims the standard menus through a `WorkbenchManipulator`, and measures both.
5. **A test keeps startup lazy.** The startup smoke test records which module GUI libraries are loaded
   when the app first becomes idle, before warm-up starts. Any catalog module loaded by then fails
   the test. Unlike a timing check, this works reliably on CI.

Related work that this ADR does not decide: the file browser replacing the Start page (2.8, ~300 ms of
startup) and moving the crash reporter's prewarm after the window shows (a core patch, ~270 ms).

## Consequences

- Startup no longer grows with the number of modules the environment offers. Loading them all at
  startup would add ~0.7 s, against a target that needs 0.25 s *removed*. The cost moves to first
  use, which for the modeling modules is too short to notice (≤ 25 ms, Assembly ~85 ms) and is hidden
  by warm-up anyway. A first CAM action waits ~0.6 s.
- Upstream's commands and workbenches stay untouched, so upstream merges stay cheap. After a merge,
  regenerating the catalog is one command, and the test says when it's needed.
- Translations: generated texts are English. Each module's translations load only with the module, so
  translated catalog texts are left for later (Phase 10 at the latest).
- FreeCAD's own toolbars, the "Customize" dialog and the workbench switcher don't show catalog
  entries; they are hidden in the unified UI anyway.
- Some commands use generic or theme icons, or icons generated at runtime; the catalog tool reports
  any it can't map to a source SVG.

## Measurements

Slim Release build (what users get), 2026-11-14, quiet machine (CPU under 15% for 30 s first). A
probe runs once the app is idle after startup and times each workbench's `Initialize()` without
activating it. The two Python workbenches were given a borrowed C++ workbench object, which
is fine in a throwaway process. Medians of 4 runs:

| Workbench | All in one process (= cost at startup) | Alone in a fresh process (= first use) |
|---|---|---|
| Sketcher | 13 ms | 12 ms |
| Part Design | 12 ms | 23 ms |
| Part | 8 ms | 16 ms |
| Assembly | 93 ms | 85 ms |
| TechDraw | 26 ms | 23 ms |
| CAM | **564 ms** | **581 ms** |
| Spreadsheet | 0 ms | 3 ms |
| **Total** | **713 ms** | |

Loading them all takes the number of registered commands from 207 to 719. Startup of this build
without them: 1.72–1.75 s ([BASELINE.md](../BASELINE.md)). Measure has no workbench of its own in this
build; its commands are registered at startup already.

Studio as `PythonBlankWorkbench`: the app crashes while activating it (access violation, after
"Init: Activating default workbench StudioWorkbench"). As `PythonWorkbench`, activation takes
150–230 ms depending on the run.
