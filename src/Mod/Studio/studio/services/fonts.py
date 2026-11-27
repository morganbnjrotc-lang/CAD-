# SPDX-License-Identifier: LGPL-2.1-or-later
"""The installed fonts by name and style (PLAN 4.1, docs/adr/0015).

Read straight from the font files (TrueType and OpenType, .ttf, .otf and a collection's first font in a .ttc,
the one FreeCAD's FreeType code draws), headless and without Qt: only the few tables needed are read.

- **family** and **style** as Windows' font list shows them: the font's typographic names (name IDs 16 and 17)
  when it has them, else its family and subfamily (1 and 2). Segoe UI Semibold is "Segoe UI", "Semibold".
- **weight** and **italic** (OS/2 table) order a family's styles: Light, Regular, Italic, Bold, Bold Italic.
- **metrics** in the font's units (head, hhea and OS/2 tables): units per em, ascender, descender, line gap,
  the capitals' and the small letters' heights. The text layout sizes text by its capitals (PLAN 4.1).
- **embeddable**: whether the font's license (OS/2 `fsType`) lets a file keep it for editing (PLAN 4.2):
  installable or editable embedding yes; restricted, preview and print only, or bitmaps only, no.
"""

import os
import struct
from dataclasses import dataclass

SUFFIXES = (".ttf", ".otf", ".ttc")
WINDOWS = 3  # name table platforms
MAC = 1
UNICODE = 0
ENGLISH_US = 0x409


@dataclass(frozen=True)
class Font:
    family: str
    style: str
    weight: int  # 100 thin … 400 regular … 700 bold … 900 black
    italic: bool
    path: str
    units_per_em: int
    ascender: int  # above the baseline, font units
    descender: int  # below it, negative
    line_gap: int
    cap_height: int
    x_height: int
    embeddable: bool

    @property
    def name(self) -> str:
        return f"{self.family} {self.style}"

    @property
    def line_spacing(self) -> int:
        """From one line's baseline to the next, in font units."""
        return self.ascender - self.descender + self.line_gap


def _tables(f):
    """The font's tables, {tag: (offset, length)}; for a collection, its first font's."""
    head = f.read(12)
    if head[:4] == b"ttcf":
        (first,) = struct.unpack(">I", f.read(4))
        f.seek(first)
        head = f.read(12)
    if head[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return None
    (count,) = struct.unpack(">H", head[4:6])
    records = f.read(16 * count)
    tables = {}
    for i in range(count):
        tag, _, offset, length = struct.unpack(">4sIII", records[16 * i:16 * i + 16])
        tables[tag.decode("latin-1")] = (offset, length)
    return tables


def _read(f, tables, tag):
    if tag not in tables:
        return None
    offset, length = tables[tag]
    f.seek(offset)
    return f.read(length)


def _names(data):
    """{name ID: text}, preferring Windows' US English names, then any Windows, Mac Roman or Unicode one."""
    _, count, strings = struct.unpack(">HHH", data[:6])
    found = {}
    for i in range(count):
        platform, encoding, language, name_id, length, offset = struct.unpack(">6H", data[6 + 12 * i:18 + 12 * i])
        raw = data[strings + offset:strings + offset + length]
        if platform == WINDOWS and encoding in (0, 1, 10):
            rank = 0 if language == ENGLISH_US else 1
            text = raw.decode("utf-16-be", "replace")
        elif platform == MAC and encoding == 0:
            rank, text = 2, raw.decode("mac-roman", "replace")
        elif platform == UNICODE:
            rank, text = 3, raw.decode("utf-16-be", "replace")
        else:
            continue
        if name_id not in found or rank < found[name_id][0]:
            found[name_id] = (rank, text.strip())
    return {name_id: text for name_id, (_, text) in found.items() if text}


def _embeddable(fs_type: int) -> bool:
    if fs_type & 0x0200:  # bitmap embedding only: no outlines
        return False
    usage = fs_type & 0x000F
    return usage == 0 or bool(usage & 0x0008)  # installable, or editable (the least restrictive bit wins)


def read(path):
    """The font in the file at `path`, or None when it isn't a font this can read."""
    try:
        with open(path, "rb") as f:
            tables = _tables(f)
            if not tables or "name" not in tables or "head" not in tables:
                return None
            names = _names(_read(f, tables, "name"))
            head = _read(f, tables, "head")
            hhea = _read(f, tables, "hhea")
            os2 = _read(f, tables, "OS/2")
    except (OSError, struct.error, ValueError):
        return None
    family = names.get(16) or names.get(1)
    style = names.get(17) or names.get(2) or "Regular"
    if not family:
        return None
    (units,) = struct.unpack(">H", head[18:20])
    ascender, descender, line_gap = struct.unpack(">hhh", hhea[4:10]) if hhea else (int(0.8 * units), -int(0.2 * units), 0)
    weight, italic, embeddable = 400, "italic" in style.lower() or "oblique" in style.lower(), True
    cap_height, x_height = round(0.7 * units), round(0.5 * units)  # when the font doesn't say
    if os2 and len(os2) >= 64:
        version, _, weight, _, fs_type = struct.unpack(">HhHHH", os2[:10])
        (selection,) = struct.unpack(">H", os2[62:64])
        italic = bool(selection & 0x0201)  # italic or oblique
        embeddable = _embeddable(fs_type)
        if weight < 10:  # a few old fonts count 1 to 9
            weight *= 100
        if version >= 2 and len(os2) >= 90:
            x, cap = struct.unpack(">hh", os2[86:90])
            x_height, cap_height = x or x_height, cap or cap_height
    return Font(family=family, style=style, weight=weight, italic=italic, path=path, units_per_em=units,
                ascender=ascender, descender=descender, line_gap=line_gap, cap_height=cap_height,
                x_height=x_height, embeddable=embeddable)


def folders():
    """Windows' fonts folder and the user's own (fonts installed for one user), those that exist."""
    candidates = [os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    return [folder for folder in candidates if os.path.isdir(folder)]


def _order(font):
    return (font.family.casefold(), font.weight, font.italic, font.style.casefold())


def installed(where=None):
    """The fonts in the folders `where` (default: `folders()`), each family and style once (the first
    folder's), in family order and each family's styles by weight."""
    seen, found = set(), []
    for folder in folders() if where is None else where:
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name.casefold())
        except OSError:
            continue
        for entry in entries:
            if not entry.name.lower().endswith(SUFFIXES) or not entry.is_file():
                continue
            font = read(entry.path)
            if font is None:
                continue
            key = (font.family.casefold(), font.style.casefold())
            if key not in seen:
                seen.add(key)
                found.append(font)
    return sorted(found, key=_order)


def families(found):
    """{family: its fonts, by weight then upright before italic}, families in alphabetical order."""
    result = {}
    for font in sorted(found, key=_order):
        result.setdefault(font.family, []).append(font)
    return result


def find(family, style, found=None):
    """The font of `family` and `style` (any case) among `found` (default: the installed ones), or None."""
    family, style = family.casefold(), style.casefold()
    for font in installed() if found is None else found:
        if font.family.casefold() == family and font.style.casefold() == style:
            return font
    return None
