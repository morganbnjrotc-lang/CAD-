# 0003 — Native Windows development environment

- **Status:** accepted
- **Date:** 2026-11-11

## Context

The main development machine is a Windows 11 laptop (Ryzen AI 7 445, 16 GB RAM). FreeCAD
supports a pixi (conda-forge) build on Windows with MSVC. Two problems came up on the first attempt:

1. The conda toolchain passes unquoted paths to the linker, so it fails when the source tree's
   path contains a space (`C:\Users\Blaine Morgan\...`). A directory junction doesn't help, because pixi
   resolves the real path.
2. Windows Smart App Control blocked unsigned DLLs from the dependency environment, and would
   block every binary we build.

WSL2 was the alternative: Smart App Control could stay on, but OpenGL through WSLg is slower
and Windows-specific behavior would go untested.

## Decision

Build natively on Windows with pixi + Visual Studio 2022 Build Tools, from **`C:\dev\CAD`**
(no spaces), with Smart App Control turned off (Defender antivirus stays on). Cap build parallelism at 6
jobs for 16 GB of RAM.

## Consequences

- Fastest edit-build-run loop, and we test on the platform our users have.
- The repo must never be built from a path with spaces; documented in `AGENTS.md`.
- Smart App Control is off on this machine. Release builds will need code signing (Phase 10) so
  end users with Smart App Control on can run the app.
