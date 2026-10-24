"""
What the examples are, derived from their modules rather than kept by hand,
and the source each one shows and copies as.

An example is a module in `counterweight.examples.apps` or `counterweight.examples.snippets`.
Its docstring's first line is its title, after its docs section and a colon for a snippet,
and the rest is its description.
An app's root is its `root`, and a snippet's roots are its `ROOTS`.
Its scenes are its `STILLS` and, if it has any, its `DEMOS`.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Literal

import counterweight.examples.apps
import counterweight.examples.snippets
from counterweight.components import Component
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

type Root = Callable[[], Component]

APPS_SECTION = "Apps"

SECTION_MARKER = re.compile(r"^# --8<-- \[(?:start|end):[\w-]+\]$")

SCENES = re.compile(r"^# --8<-- \[start:scenes\]$.*?^# --8<-- \[end:scenes\]$\n", re.MULTILINE | re.DOTALL)


class UnknownExample(LookupError):
    """No example, or no root of one, has the name asked for."""


@dataclass(frozen=True, slots=True)
class Example:
    """One example module, an app or a snippet."""

    name: str
    """The module's name with hyphens for underscores, as `layout-splitting`."""
    kind: Literal["app", "snippet"]
    section: str
    """`Apps` for an app, and the docs section a snippet belongs to for a snippet."""
    title: str
    description: str
    roots: tuple[Root, ...]
    """What runs the example, the first by default."""
    stills: tuple[Still, ...]
    demos: tuple[Demo, ...]
    path: Path
    """The module's source file."""

    def root_name(self, root: Root) -> str:
        """What names `root` to the CLI: the example's name, then a colon and the root's for one of several."""
        if len(self.roots) == 1:
            return self.name
        return f"{self.name}:{hyphenated(root.__name__)}"

    def source(self) -> str:
        """The module's source, scenes and markers included."""
        return self.path.read_text()


def hyphenated(name: str) -> str:
    """A Python name as the CLI names it, with hyphens for underscores."""
    return name.replace("_", "-")


def example_of(module: ModuleType, kind: Literal["app", "snippet"]) -> Example:
    """
    The example `module` holds, read from its docstring and its roots.

    Raises:
        ValueError: If the module has no docstring, or a snippet's first line names no section.
    """
    doc = inspect.getdoc(module)
    if not doc:
        raise ValueError(f"The example {module.__name__} has no docstring to take its title from")
    first, _, rest = doc.partition("\n")
    if kind == "app":
        section, title = APPS_SECTION, first
        roots: tuple[Root, ...] = (module.root,)
    else:
        section, colon, title = first.partition(": ")
        if not colon:
            raise ValueError(f"The snippet {module.__name__}'s docstring doesn't start with its section and a colon")
        roots = module.ROOTS
    path = Path(inspect.getfile(module))
    return Example(
        name=hyphenated(path.stem),
        kind=kind,
        section=section,
        title=title,
        description=rest.strip(),
        roots=roots,
        stills=tuple(module.STILLS),
        demos=tuple(getattr(module, "DEMOS", ())),
        path=path,
    )


@cache
def examples() -> tuple[Example, ...]:
    """Every example, apps first, then snippets by section, each in order by name."""
    packages: tuple[tuple[ModuleType, Literal["app", "snippet"]], ...] = (
        (counterweight.examples.apps, "app"),
        (counterweight.examples.snippets, "snippet"),
    )
    found = [
        example_of(importlib.import_module(f"{package.__name__}.{module.name}"), kind)
        for package, kind in packages
        for module in pkgutil.iter_modules(package.__path__)
    ]
    return tuple(sorted(found, key=lambda example: (example.kind != "app", example.section, example.name)))


def find(name: str, catalog: tuple[Example, ...]) -> tuple[Example, Root]:
    """
    The example `name` names, and the root it runs:
    the one after a colon, as in `layout-splitting:equal-grid`, or the example's first.

    Raises:
        UnknownExample: If no example, or no root of it, has that name.
    """
    example_name, _, root_name = name.partition(":")
    example = next((example for example in catalog if example.name == example_name), None)
    if example is None:
        raise UnknownExample(f"There's no example named {example_name!r}")
    if not root_name:
        return example, example.roots[0]
    root = next((root for root in example.roots if hyphenated(root.__name__) == root_name), None)
    if root is None:
        names = ", ".join(example.root_name(root) for root in example.roots)
        raise UnknownExample(f"{example.name} has no root named {root_name!r}; its roots are {names}")
    return example, root


def shown(source: str) -> str:
    """An example module's source as it's shown: without the markers the docs pull its sections out by."""
    return "".join(line for line in source.splitlines(keepends=True) if not SECTION_MARKER.match(line.rstrip("\n")))


def copied(source: str) -> str:
    """
    An example module's source as it's copied, to run on its own:
    without its scenes, which only the docs and the tests use, and without the markers.
    """
    return re.sub(r"\n{3,}", "\n\n\n", shown(SCENES.sub("", source)))


def write_copy(example: Example, path: Path) -> Path:
    """
    Writes `example` as it's copied to `path`, or into it, named as the example's module is, if it's a directory.

    Raises:
        FileExistsError: If there's a file there already, which it leaves as it is.
    """
    destination = path / example.path.name if path.is_dir() else path
    with destination.open("x") as file:
        file.write(copied(example.source()))
    return destination
