# SPDX-License-Identifier: LGPL-2.1-or-later
"""Architecture fitness tests: enforce the layer rules from docs/adr/0002-layered-architecture.md.

Layers inside the `studio` package, top to bottom: viewmodels -> interaction -> services.
None of them may import GUI toolkits; a layer may not import a layer above it.
"""

import ast
import unittest
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parents[1] / "studio"

# Top-level modules that pull in a GUI, Qt or the 3D scene graph.
GUI_MODULES = frozenset(
    {"FreeCADGui", "PySide", "PySide2", "PySide6", "shiboken2", "shiboken6", "pivy"}
)

# For each headless layer: the studio layers it must NOT import (i.e. the ones above it).
LAYER_RULES = {
    "services": {"interaction", "viewmodels"},
    "interaction": {"viewmodels"},
    "viewmodels": set(),
}


def imported_modules(source: str, module_name: str) -> set:
    """Return absolute dotted names of everything `source` imports.

    `module_name` is the dotted name of the module the source belongs to, used to resolve
    relative imports (e.g. `from ..viewmodels import x` inside studio.services.foo).
    """
    package_parts = module_name.split(".")[:-1]
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - node.level + 1]
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            found.add(prefix)
            found.update(f"{prefix}.{alias.name}" for alias in node.names)
    return found


def violations(imports: set, layer: str) -> set:
    """Imports that break the rules for `layer`."""
    bad = set()
    for name in imports:
        parts = name.split(".")
        if parts[0] in GUI_MODULES:
            bad.add(name)
        elif parts[0] == "studio" and len(parts) > 1 and parts[1] in LAYER_RULES[layer]:
            bad.add(name)
    return bad


class ImportCheckerTest(unittest.TestCase):
    """The checker itself must catch violations, or the layer test proves nothing."""

    def test_detects_gui_imports_in_every_form(self):
        source = (
            "import FreeCADGui\n"
            "from PySide import QtGui\n"
            "import PySide6.QtWidgets\n"
            "from pivy import coin\n"
        )
        found = violations(imported_modules(source, "studio.services.example"), "services")
        self.assertTrue({"FreeCADGui", "PySide", "PySide6.QtWidgets", "pivy"} <= found, found)

    def test_detects_upward_layer_imports_absolute_and_relative(self):
        source = (
            "from studio.viewmodels import panel\n"
            "from ..interaction import tool\n"
        )
        found = violations(imported_modules(source, "studio.services.example"), "services")
        self.assertIn("studio.viewmodels", found)
        self.assertIn("studio.interaction", found)

    def test_allows_downward_and_kernel_imports(self):
        source = (
            "import FreeCAD\n"
            "import Part\n"
            "from studio.services import modeling\n"
            "from ..services import modeling\n"
        )
        found = violations(imported_modules(source, "studio.viewmodels.example"), "viewmodels")
        self.assertEqual(found, set())


class LayerDependencyTest(unittest.TestCase):
    def test_every_layer_package_exists(self):
        for layer in LAYER_RULES:
            with self.subTest(layer=layer):
                self.assertTrue(
                    (STUDIO_ROOT / layer / "__init__.py").is_file(),
                    f"missing layer package studio/{layer}",
                )

    def test_layers_respect_dependency_rules(self):
        for layer in LAYER_RULES:
            for path in sorted((STUDIO_ROOT / layer).rglob("*.py")):
                relative = path.relative_to(STUDIO_ROOT.parent).with_suffix("")
                module_name = ".".join(relative.parts)
                with self.subTest(module=module_name):
                    source = path.read_text(encoding="utf-8")
                    bad = violations(imported_modules(source, module_name), layer)
                    self.assertEqual(bad, set(), f"{module_name} breaks the {layer} layer rules")
