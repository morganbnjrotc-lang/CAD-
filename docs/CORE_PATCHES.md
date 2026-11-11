# Core patches

Every change we make to files that come from upstream FreeCAD is listed here, so upstream merges stay
predictable. New behavior should live in `src/Mod/Studio`; an entry here means no extension
point was available.

| Date | File(s) | Change | Why | Merge notes |
|---|---|---|---|---|
| 2026-11-11 | `README.md` → `README.FreeCAD.md` | Renamed; new project README added | Our README describes the fork | Upstream edits to `README.md` should follow the rename; check after each merge |
| 2026-11-11 | `AGENTS.md` → `AGENTS.FreeCAD.md` | Renamed; new fork-specific `AGENTS.md` + `CLAUDE.md` added | Upstream's agent policy targets FreeCAD contributions, not this fork | Same as above |
