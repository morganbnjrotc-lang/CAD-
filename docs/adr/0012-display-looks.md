# 0012 — Display looks: Coin's shadows around FreeCAD's objects

- **Status:** accepted (2026-11-21: the user said yes to trying shadows, gray box and realistic as new
  rendering work, PLAN 3.8)
- **Date:** 2026-11-21

## Context

PLAN 3.8 asks for display presets beyond FreeCAD's draw styles: *pretty* (shadows), *gray box* and
*realistic*. FreeCAD's 3D viewer draws no shadows and has no way to show every part in one color or to
add highlights. Coin, which FreeCAD draws with (bundled in `src/3rdParty/coin`), has shadows:
`SoShadowGroup` renders variance shadow maps for the shadow lights in its subtree, with per-pixel
lighting, and `SoShadowStyle` says what casts and what receives them. FreeCAD never uses them (pivy
doesn't even wrap them). Every view provider's scene sits in one group of the viewer, `ObjectGroup`;
FreeCAD only adds and removes that group's children and never relies on where the group sits.

## Decision

1. **Studio draws the looks, without changing FreeCAD's code:** `StudioGui.set_look(shadows, gray, shiny,
   floor_color)` (C++, `ViewLook` in `src/Mod/Studio/Gui/AppStudioGui.cpp`) moves each 3D view's
   `ObjectGroup` into a `SoShadowGroup` that also holds a directional shadow light from above and a floor
   just under the model that takes its shadow. Taken off, the group goes back where it was.
2. **Three presets on the Display menu** (`studio/services/display.py`), each a draw style plus a look:
   *Pretty* = shaded with edges + shadows; *Gray Box* = shaded, every part one neutral gray (an override
   material) + shadows; *Realistic* = shaded, the parts' own colors with highlights (an override of only
   the specular color and shininess) + shadows.
3. **The floor** is one-sided (from below the model shows through), six times the model's size, in the
   theme's 3D background color dimmed so that, lit, it shows about as bright as the background; it
   follows the model (a node sensor on the object group refits it and the shadow light).
4. **The shadow light covers 1.6 times the model's size**: Coin's shadow map is 2048 px at most, so a
   tighter box gives sharper shadows.

## Consequences

- Shadows cost a second rendering pass of the model (the shadow map); they are opt-in presets.
- Shadow edges are a little stepped: Coin's border smoothing (`smoothBorder`) is switched off in Coin
  itself as unfinished.
- The floor hides the background gradient while a preset is on (a product-shot look).
- The 3D view is masked in the visual check (rendering differs between machines), so the presets were
  reviewed on screenshots by hand: the example model and colored parts, light and dark (2026-11-21).
- Coin's shadows need GLSL; where the GPU can't run them, the view draws without shadows.
