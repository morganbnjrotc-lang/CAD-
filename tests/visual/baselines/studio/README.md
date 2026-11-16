# Studio's visual baselines

Reviewed pictures of Studio's main screens (PLAN 2.10), checked in CI by `tools/test/run_visual.py`.

| Picture | Screen |
|---|---|
| `home-light.png`, `home-dark.png` | Home at startup: recent files with previews and a STEP tile |
| `model-light.png`, `model-dark.png` | `PartDesignExample` with a face selected: the face tools, the model tree, the properties |
| `sketch-light.png`, `sketch-dark.png` | Editing its sketch: the sketch tools and the sketch's Tasks panel (constraints) |

Each mode starts on a fresh profile. The 3D view is masked when comparing (OpenGL drawing differs between
graphics cards, and the 3D colors are checked by the theme tests), except the Tasks panel floating over
it, which is compared like the rest. To get the same pictures on any machine, the run uses a fixed
1280 x 800 window (fixed, so it can be bigger than a small screen such as CI's 1024 x 768) with the mouse
pointer outside it, the vendored Noto Sans (`tests/visual/fonts`) drawn by FreeType, no high-DPI scaling,
text and Qt's sizes at 96 DPI (100 %) whatever the display's scaling, copies of the example files dated
three days back, and status messages cleared. A screen matches when at most 0.2 % of its pixels differ by
more than 8 in a color channel (FreeCAD's own snapshot rule).

The pictures were retaken at 96 DPI on 2026-11-15. The first set, from earlier that day, was taken at
120 DPI (a display at 125 %) and had the model tree and properties on the bars' grey, a Windows 11-only style-switch artifact
since fixed (docs/adr/0010-studio-look.md, step 2).

```powershell
pixi run python tools/test/run_visual.py             # compare; differences go to build/test-logs/visual
pixi run python tools/test/run_visual.py --update    # after an intended change: write new pictures
```

After `--update`, look at every changed picture before committing it, and say in the commit why the
look changed. A baseline is never regenerated just to make the check pass.
