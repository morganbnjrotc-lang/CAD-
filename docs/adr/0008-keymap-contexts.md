# 0008 — Keymap: Studio owns the shortcuts, which depend on what you are doing

- **Status:** proposed
- **Date:** 2026-11-14

## Context

PLAN 2.4 asks for `E` extrude, `F` focus selection, `Shift+F` fit all, user-editable bindings and
conflict detection.

FreeCAD already has 191 default shortcuts (from the command catalog, [ADR 0007](0007-lazy-loading-command-catalog.md)):

| Commands of | Shortcuts | Single letters |
|---|---|---|
| FreeCAD core (available from startup) | 73 | none (view keys `0`–`6`, `Del`, `Esc`, `Space`, F-keys, `Ctrl+…`, sequences like `V, F`) |
| Sketcher | 91 | 13: `A C D E H I L N P S T V W` |
| Assembly | 19 | 18 |
| TechDraw | 3 | `D` |
| CAM | 10 | none (two-key sequences) |
| Spreadsheet | 4 | none |
| Part Design, Part | 0 | none |

These work in FreeCAD only because one workbench's toolbars are active at a time: `E` is Sketcher's
"constrain equal" and Assembly's "create view"; `D` means dimension in three workbenches. In the
unified environment no other workbench is ever active. A command's own button doesn't exist until
its module loads (ADR 0007), and even then it sits in no toolbar, so FreeCAD's shortcut handling
(`ShortcutManager`: per-command user shortcuts, priorities for ambiguous keys) never sees a key
press for it.

## Decision

1. **Studio owns the keymap.** A binding is *(context, key sequence) → catalog command*. The shell
   installs the bindings and runs commands through the command service, so a shortcut works before its
   command's module is loaded: the first press loads it.
2. **Contexts: what you are doing decides what a key means.** *Global* is always active. A
   workbench's context (named after the workbench that owns the commands) is active while you do
   that kind of work: editing a sketch (Sketcher), editing an assembly (Assembly), a TechDraw page
   (TechDraw); CAM and Spreadsheet when the shell learns to detect them. A key is looked up in the
   most specific active context first, then in Global. While sketching, `D` is Dimension; elsewhere it
   is whatever Global says, or nothing.
3. **Defaults:** FreeCAD's own shortcuts, each in its command's context (core commands in Global),
   so FreeCAD users keep their habits (Sketcher's letters, `V, F`). Studio's defaults on top, in Global:
   `E` → extrude (`PartDesign_Pad` until Phase 3 brings a direct extrude tool), `F` → fit selection
   (`Std_ViewFitSelection`), `Shift+F` → fit all (`Std_ViewFitAll`).
4. **The user's bindings are stored with the settings service**, one setting per context and command:
   `Keymap/<Context>/<Command>` = key sequence, empty = deliberately unbound. Precedence: user, then
   Studio's defaults, then FreeCAD's.
5. **Conflicts:** two commands on the same key sequence *in the same context* are reported; the binding
   from the higher source wins, and between two FreeCAD defaults the earlier in catalog order. A
   specific context overriding Global is intended, not a conflict.
6. **Typing is safe:** a single-key shortcut doesn't fire while a text field has focus (Qt gives the
   key to the field first). A shell test checks it.
7. **Until 2.6 replaces FreeCAD's menus**, their actions (Undo, Save, …) keep their own shortcuts. The
   shell doesn't install a binding that one of FreeCAD's live actions already serves, so no key ends up
   with two owners.

## Consequences

- Keys that clash between workbenches in FreeCAD coexist, and Studio's single-key defaults don't take
  letters away from sketching.
- A workbench context the shell can't detect yet keeps its shortcuts inactive (CAM and Spreadsheet
  at first). Users can bind any command globally meanwhile.
- FreeCAD's "Customize → Keyboard" dialog doesn't know Studio's bindings. Studio gets its own keymap
  editor later; until then bindings are changed through settings.
- The keymap itself (normalizing key sequences, lookup, conflicts, user edits) has no Qt in it and
  lives in the interaction layer, tested headless; installing shortcuts and detecting the context is
  the shell's job.
