# 0013 — Every tool in Fusion's groups on the top bar, and pinned tools

- **Status:** accepted (2026-11-22: the user picked "groups in the top bar" and "pin for that selection"
  from the layouts shown to them, PLAN 3.17). Amends [ADR 0009](0009-unified-main-window.md).
- **Date:** 2026-11-22

## Context

ADR 0009 gave Studio one toolbar that follows the selection, with a few tools for each kind of selection;
every other tool was in the command palette (search) or under a key. The user, 2026-11-22: "I like our
current setup but it lacks a lot of features that have to be searched for. Autodesk's organization is nice
but it leaves the screen too busy." Fusion groups every tool under a few words (Create, Modify, Assemble,
Construct, Inspect, Insert, Select; while sketching Create, Modify, Constraints, Inspect…) and shows two or
three icons per group next to each word, which is what makes its bar busy.

The user was shown three layouts: the group words as menus in the top bar, which was mostly empty; group
buttons at the start of the toolbar; one "All tools" button opening a panel with every group side by side.
And three ways to pin: for the kind of selection there is, always, or not now.

## Decision

1. **The group words are menus in the top bar**, between Panel and Display: Create, Modify, Construct,
   Inspect, Insert; while a sketch is being edited Create, Modify, Constrain, Inspect. Words only, like a
   menu bar: no icons on the bar itself, so the screen gets no busier. The toolbar below keeps following
   the selection, unchanged.
2. **Each group holds every tool in it** (`studio/viewmodels/tool_groups.py`, a hand-written table like the
   toolbar's): icons, plain names (the toolbar's, e.g. Extrude, Combine, Fix), the active key at the right,
   FreeCAD's name in the tooltip. A tool drawing more than one way lists its ways in a side menu (the same
   ways as its toolbar button, and picking one makes the button draw it); Part Design's primitives, which
   one command makes by item number, are a side menu too. A tool that can't run now is grayed, as on the
   toolbar; the sketch tools FreeCAD stops with a "Wrong selection" dialog wait for a selection (the
   toolbar's list of them grew from 3 to 12).
3. **Right-click a tool in a group → "Pin to toolbar for faces"** (or for sketches, edges, while
   sketching…: the kind of selection there is now). From then on it shows after that kind's own tools,
   past a separator. Right-clicking the pinned button, or the tool in its group again, unpins it. Pins are
   Studio settings (`Toolbar/Pins/<kind>`), each remembered by the tool's command and, where it has one,
   its item number or drawing method; a pin whose tool is gone from the groups is skipped.
4. **Group menus are built when they open.** On each change of selection only the group names are set
   and pinned buttons are built only when something is pinned for that kind.

## Consequences

- Every tool of the modules Studio ships is two clicks away, without searching; search and keys stay.
- The groups' table is ours to keep current, like the toolbar's; the tests check every tool in it is a
  catalog command with an icon in the build (Part Design's primitive icons are now copied next to the
  catalog's), and that every toolbar tool is in a group.
- The top bar has five more words; the toolbar row is unchanged, so the 3D view keeps its height.
- `StudioGui.choose_popup` (a test helper) also matches an item showing its key after a tab.
