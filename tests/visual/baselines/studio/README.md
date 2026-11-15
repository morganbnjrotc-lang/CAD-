# Studio's visual baselines

Reviewed pictures of Studio's main screens (PLAN 2.10), checked in CI by `tools/test/run_visual.py`.

| Picture | Screen |
|---|---|
| `home-light.png`, `home-dark.png` | Home at startup: recent files with previews and a STEP tile |
| `model-light.png`, `model-dark.png` | `PartDesignExample` with a face selected: the face tools, the model tree, the properties |
| `sketch-light.png`, `sketch-dark.png` | Editing its sketch: the sketch tools |

Each mode starts on a fresh profile. The 3D view (and the Tasks panel floating over it) is masked when
comparing: OpenGL drawing differs between graphics cards, and the 3D colors are checked by the theme
tests. To get the same pictures on any machine, the run uses a fixed 1280 x 800 window placed off the
screen, the vendored Noto Sans (`tests/visual/fonts`) drawn by FreeType, no high-DPI scaling, copies of the
example files dated three days back, and status messages cleared. A screen matches when at most 0.2 % of
its pixels differ by more than 8 in a color channel (FreeCAD's own snapshot rule).

```powershell
pixi run python tools/test/run_visual.py             # compare; differences go to build/test-logs/visual
pixi run python tools/test/run_visual.py --update    # after an intended change: write new pictures
```

After `--update`, look at every changed picture before committing it, and say in the commit why the
look changed. A baseline is never regenerated just to make the check pass.
