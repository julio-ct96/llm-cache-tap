"""Dependency rules between the cachetap modules."""

import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "cachetap"

ALLOWED = {
    "config.py": set(),
    "record.py": set(),
    "segments.py": {"record"},
    "request_body.py": {"record"},
    "providers/base.py": set(),
    "providers/anthropic.py": {"record", "providers.base"},
    "providers/openai.py": {"record", "providers.base"},
    "providers/__init__.py": {"config", "record", "providers.anthropic", "providers.openai"},
    "response_body.py": {"providers", "record"},
    "linking.py": {"segments", "record"},
    "verdict.py": {"config", "providers", "record"},
    "store.py": {"config", "record"},
    "dashboard.py": {"config", "providers", "record", "store"},
}


def _files():
    return sorted(p for p in PACKAGE.rglob("*.py") if p != PACKAGE / "__init__.py")


def _name(path):
    return path.relative_to(PACKAGE).as_posix()


def _imports(path):
    """Return the cachetap modules imported by a file, e.g. {'config', 'providers.base'}."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "cachetap":
                found.update(alias.name for alias in node.names)
            elif node.module.startswith("cachetap."):
                prefix = node.module[len("cachetap."):]
                found.update(f"{prefix}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cachetap":
                    continue
                if alias.name.startswith("cachetap."):
                    found.add(alias.name[len("cachetap."):])
    return found


def _imports_tap(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "tap" or node.module.startswith("tap."):
                return True
        elif isinstance(node, ast.Import):
            if any(a.name == "tap" or a.name.startswith("tap.") for a in node.names):
                return True
    return False


class DependenciesTest(unittest.TestCase):
    def test_every_module_is_in_the_table(self):
        for path in _files():
            with self.subTest(module=_name(path)):
                self.assertIn(_name(path), ALLOWED)

    def test_every_table_row_exists(self):
        names = {_name(p) for p in _files()}
        for name in ALLOWED:
            with self.subTest(module=name):
                self.assertIn(name, names)

    def test_imports_stay_within_the_table(self):
        for path in _files():
            name = _name(path)
            if name not in ALLOWED:
                continue
            with self.subTest(module=name):
                extra = _imports(path) - ALLOWED[name]
                self.assertEqual(extra, set())

    def test_nobody_imports_tap(self):
        for path in _files():
            with self.subTest(module=_name(path)):
                self.assertFalse(_imports_tap(path))


if __name__ == "__main__":
    unittest.main()
