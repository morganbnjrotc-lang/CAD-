# 0001 — Fork FreeCAD, keep its kernel, replace its presentation

- **Status:** accepted
- **Date:** 2026-11-11

## Context

We want a full CAD/CAM app (parametric modeling, sketcher, assemblies, drawings, CAM) that is
local, fast and much easier to use. Writing a geometry kernel, constraint solver, document
model and CAM engine from scratch would take years. FreeCAD already has all of them (OpenCASCADE,
its sketch solver, Ondsel assembly solver, CAM ops, TechDraw), but its UI is split into
workbenches and is widely seen as hard to use.

## Decision

Fork FreeCAD with full history. Keep its kernel and document model (`src/Base`, `src/App`,
the modeling modules) and build a new presentation and interaction layer on top. Track
FreeCAD as the `upstream` remote and merge it regularly.

## Consequences

- We get years of geometry, file-format and solver work for free, plus ongoing upstream fixes.
- The license is LGPL-2.1-or-later and stays that way.
- We inherit FreeCAD's startup cost and build weight; Phase 1–2 work (slim build, lazy loading) has to bring those down.
- Every edit to upstream files makes merges harder, so see [0002](0002-layered-architecture.md) and `docs/CORE_PATCHES.md`.
