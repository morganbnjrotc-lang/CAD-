# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preview images of model files (PLAN 2.8).

A .FCStd file is a zip archive; FreeCAD stores a picture of the model in it when saving
("thumbnails/Thumbnail.png", on by default). Other formats (STEP, STL, ...) carry none; the Home
page shows a placeholder for them instead of rendering them, which would cost time.
"""

import zipfile

THUMBNAIL = "thumbnails/Thumbnail.png"


def thumbnail_png(path):
    """The PNG bytes FreeCAD stored in a .FCStd file; None if there are none or it can't be read."""
    if not str(path).lower().endswith(".fcstd"):
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.read(THUMBNAIL)
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
