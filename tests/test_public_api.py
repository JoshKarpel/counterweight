"""
Where the public API lives.
A module is public unless a part of its dotted name starts with an underscore,
and its `__all__` lists its public names;
a public module re-exports only names defined in private ones,
so each public name has exactly one home.
The examples (which `counterweight examples copy` hands to users) and the docs only reach the API through those homes.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path
from types import ModuleType

import pytest

import counterweight
from counterweight.examples import apps
from counterweight.examples import snippets
from counterweight.styles import utilities
from mkdocs_hooks.utility_tables import public_utilities

ROOT = Path(__file__).parent.parent
SOURCE = ROOT / "src" / "counterweight"


def is_public(module_name: str) -> bool:
    return not any(part.startswith("_") for part in module_name.split("."))


def library_modules() -> list[str]:
    """Every module in the library, without the examples, which aren't part of its API."""
    names = [
        info.name
        for info in pkgutil.walk_packages(counterweight.__path__, prefix="counterweight.")
        if not info.name.startswith("counterweight.examples")
    ]
    return ["counterweight", *names]


PUBLIC_MODULES = [name for name in library_modules() if is_public(name)]


def source_of(module: ModuleType) -> ast.Module:
    assert module.__file__ is not None
    return ast.parse(Path(module.__file__).read_text())


@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_public_module_lists_its_public_names(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert isinstance(getattr(module, "__all__", None), list)


@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_public_module_reexports_only_from_private_modules(module_name: str) -> None:
    module = importlib.import_module(module_name)
    exported = set(getattr(module, "__all__", ()))

    reexported_from_public = [
        f"{node.module}.{alias.name}"
        for node in source_of(module).body
        if isinstance(node, ast.ImportFrom) and node.module is not None and is_public(node.module)
        for alias in node.names
        if (alias.asname or alias.name) in exported
    ]

    assert reexported_from_public == []


def resolves_publicly(path: str) -> bool:
    """Whether a dotted path names a public module, or a name in one's `__all__` (or an attribute of such a name)."""
    parts = path.split(".")
    for split in range(len(parts), 0, -1):
        module_name = ".".join(parts[:split])
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        if not is_public(module_name):
            return False
        return split == len(parts) or parts[split] in getattr(module, "__all__", ())
    return False


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("counterweight.hooks", True),
        ("counterweight.app", True),
        ("counterweight.paint.Frame.svg", True),
        ("counterweight.elements.styled_cells", False),
        ("counterweight._app.render_loop", False),
        ("counterweight.hooks._hooks.use_state", False),
        ("nowhere.at_all", False),
    ],
)
def test_resolves_publicly(path: str, expected: bool) -> None:
    assert resolves_publicly(path) is expected


EXAMPLE_FILES = sorted(path for package in (apps, snippets) for path in Path(next(iter(package.__path__))).glob("*.py"))


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.name)
def test_example_imports_only_public_names(path: Path) -> None:
    private_imports = [
        f"{node.module}.{alias.name}"
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom) and node.module is not None and node.module.startswith("counterweight")
        if not node.module.startswith("counterweight.examples")
        for alias in node.names
        if not (
            resolves_publicly(f"{node.module}.{alias.name}") or (alias.name == "*" and resolves_publicly(node.module))
        )
    ]

    assert private_imports == []


# `::: counterweight.x.Y` renders an object's reference; `[text][counterweight.x.Y]` links to it.
REFERENCE = re.compile(r"^::: (counterweight[\w.]*)|\]\[(counterweight[\w.]*)\]", re.MULTILINE)

DOCUMENTED_FILES = sorted([*(ROOT / "docs").rglob("*.md"), *SOURCE.rglob("*.py")])


@pytest.mark.parametrize("path", DOCUMENTED_FILES, ids=lambda path: str(path.relative_to(ROOT)))
def test_docs_reference_objects_by_their_public_home(path: Path) -> None:
    references = [match.group(1) or match.group(2) for match in REFERENCE.finditer(path.read_text())]

    assert [reference for reference in references if not resolves_publicly(reference)] == []


RENDERED = re.compile(r"^::: (counterweight[\w.]*)$", re.MULTILINE)


@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_docs_render_every_public_name(module_name: str) -> None:
    """
    Every name in a public module's `__all__` has a `::: <module>.<name>` reference somewhere in the docs,
    or its module is rendered whole.
    The style utilities are the exception: the utilities page lists them, and its hook fails the build on any it misses.
    """
    rendered = {
        match.group(1) for path in (ROOT / "docs").rglob("*.md") for match in RENDERED.finditer(path.read_text())
    }
    module = importlib.import_module(module_name)
    listed_by_utilities_page = public_utilities(utilities) if module is utilities else {}

    assert [
        name
        for name in module.__all__
        if module_name not in rendered
        and f"{module_name}.{name}" not in rendered
        and name not in listed_by_utilities_page
    ] == []
