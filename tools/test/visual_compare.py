# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compares a screenshot with its reviewed baseline (Studio's visual baselines, PLAN 2.10).

A screenshot matches when no more than `MAX_MISMATCH_PCT` of its pixels differ from the baseline by
more than `TOLERANCE` in any color channel, the same rule as FreeCAD's own snapshot tests
(src/Mod/Test/TestCoinNodeSnapshots.py). Masked rectangles (the 3D view: OpenGL drawing differs between
graphics cards) are left out. Pictures are numpy arrays, height x width x RGB, uint8.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

TOLERANCE = 8
MAX_MISMATCH_PCT = 0.2
MARK = (255, 0, 255)  # differing pixels in the diff picture


@dataclass
class Comparison:
    ok: bool
    mismatch_pct: float
    diff: np.ndarray | None = None  # the baseline, faded, with differing pixels marked
    reason: str = ""


def compare(actual, expected, masks=(), tolerance=TOLERANCE, max_mismatch_pct=MAX_MISMATCH_PCT) -> Comparison:
    """`masks`: (x, y, width, height) rectangles to leave out."""
    if actual.shape != expected.shape:
        return Comparison(False, 100.0, reason=f"size {actual.shape[1]}x{actual.shape[0]} instead of "
                                               f"{expected.shape[1]}x{expected.shape[0]}")
    differs = (np.abs(actual.astype(np.int16) - expected.astype(np.int16)) > tolerance).any(axis=2)
    considered = np.ones(differs.shape, dtype=bool)
    for x, y, width, height in masks:
        considered[max(y, 0):y + height, max(x, 0):x + width] = False
    differs &= considered
    total = int(considered.sum())
    pct = 100.0 * int(differs.sum()) / total if total else 0.0
    diff = (expected // 3 + 170).astype(np.uint8)  # faded, so the marks stand out
    diff[~considered] = (128, 128, 128)
    diff[differs] = MARK
    ok = pct <= max_mismatch_pct
    return Comparison(ok, pct, diff, "" if ok else f"{pct:.2f} % of pixels differ (at most {max_mismatch_pct} %)")


def load(path) -> np.ndarray:
    from PySide6 import QtGui

    image = QtGui.QImage(str(path)).convertToFormat(QtGui.QImage.Format_RGB888)
    if image.isNull():
        raise FileNotFoundError(path)
    rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    return rows[:, :image.width() * 3].reshape(image.height(), image.width(), 3).copy()


def save(picture, path) -> None:
    from PySide6 import QtGui

    picture = np.ascontiguousarray(picture, dtype=np.uint8)
    height, width, _ = picture.shape
    image = QtGui.QImage(picture.data, width, height, width * 3, QtGui.QImage.Format_RGB888)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not image.copy().save(str(path)):
        raise OSError(f"could not write {path}")
