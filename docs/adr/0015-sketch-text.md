# 0015 — Text in sketches, laid out by Studio like Fusion's

- **Status:** accepted (2026-11-27: proposed when the user moved on to Phase 4, Fusion's way as the user has
  picked for each tool so far; the user tried the tool the same day: "it works")
- **Date:** 2026-11-27

## Context

The roadmap asks for a text tool with a box, an area and a centered area, any installed font, and fonts kept
in the file (README, PLAN Phase 4). Fusion's sketch Text: drag a box, type one or more lines, pick a font and
style, give a height, align the lines in the box; the text stays editable.

FreeCAD's sketcher has a Text tool (`Sketcher_CreateText`, on Studio's sketch toolbar since 3.12). Two clicks
give a construction line; the text's outline (`Part::makeTextWires`: FreeType and HarfBuzz) becomes sketch
geometry (lines and B-splines) that a `Text` constraint holds to the line: the solver keeps only the line, and
the letters follow it rigidly, scaled with its length. Measured 2026-11-27, headless:

- The text is stretched to the word's own outline: with the line 10 mm long, "ace" gets 10 mm tall small
  letters, "ABC" 10 mm capitals: the letter size depends on the word, not on a height.
- A typed line break is dropped ("two\nlines" is one line).
- Fonts are listed by file name (`arialbd`, `BKANT`), and the file keeps only that name.

The same holding mechanism is open to anyone as the sketch's `Group` constraint (a frame line and its
members), and works from Python: geometry made by Studio and grouped follows the frame when it is moved,
turned or lengthened, the sketch counts as fully defined once the frame is, it pads into solids, and it
survives save and reopen. Part's `GeometryStringExtension` on a sketch geometry is saved with it.

## Decision

1. **Studio lays the text out** (`studio/services/sketch_text.py`): lines split where typed, each line's
   outline from the font (Part's `makeWireString`, which kerns), scaled so that the **capitals are the typed
   height** (the font's cap height, as drafting measures text; the same height for any word), lines spaced by
   the font's line gap, aligned left, center or right and top, middle or bottom in the box.
2. **Held by a sketch Group**: the frame is a construction line along the box's bottom edge; the letters and
   the box's other edges (construction) are its members. Moving, turning or dimensioning the frame moves the
   text; the solver sees only the frame.
3. **The text's settings ride on the frame** (a `GeometryStringExtension` named `StudioText`, JSON: text,
   font family and style, height, alignment, box; base64-encoded, since FreeCAD writes an extension's text
   into the file unescaped and a quote there loses the sketch's geometry on reopen, BASELINE.md), so the
   text is found and edited again from its geometry, whatever its place in the sketch's lists; an edit
   rebuilds the members around the same frame in one undo step, or inside a tool panel's step.
4. **Fonts by name and style** (`studio/services/fonts.py`): every installed font file (Windows' fonts folder
   and the user's own) read for its family and style names (the font's `name` table), its metrics and its
   embedding permission (`OS/2 fsType`), without loading Qt: a headless service.
5. **FreeCAD's Text stays** as the tool's "Along a Line" way; Studio's text box is the default way.
6. **Fonts kept in the file** (PLAN 4.2): each font the sketch's texts use is kept in the sketch as an
   included file (`App::PropertyFileIncluded`, group "Studio Fonts"), once a font, added and dropped with the
   texts; FreeCAD saves it in the `.FCStd` and unpacks it on opening. Editing offers the computer's fonts and,
   where one isn't installed, the sketch's copy, matched by the family and style in the frame's settings. A
   font whose license forbids embedding (OS/2 `fsType`: restricted, or preview and print only) is used but
   not kept, and the panel says so.

## Consequences

- No FreeCAD file changes; a file with Studio text opens in FreeCAD as a sketch with grouped geometry
  (editable as geometry, not as text).
- FreeCAD's own Text edit dialog doesn't open Studio texts (they are Groups, not Texts); Studio's panel does.
- Text is many curves: a long text is a heavy sketch, as FreeCAD's is.
- A kept font is kept whole: the file grows by its size (on this computer: half the fonts under 0.07 MB, Arial 1 MB, the biggest Asian and Unicode ones 17–35 MB).
  Keeping only the letters used would need a font subsetter, which neither FreeCAD nor its libraries have.
- Lines break only where typed for now; wrapping at the box's width can come later.
- The Text panel sits at the top of the Tasks panel, above the sketch's own: FreeCAD shows one dialog at a
  time and the edited sketch's holds it, but its contextual panels take any widget (`StudioGui.add_task_panel`).
- A new text starts in the middle of the view and is dragged into place. Clicking the box's corners, as in
  Fusion, would need a sketcher tool (a C++ `DrawSketchHandler`), which would load the sketcher with Studio's
  C++ helpers at every start; left for later if placing by dragging falls short.
