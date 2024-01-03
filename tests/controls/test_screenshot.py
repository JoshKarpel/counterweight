from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

import pytest

from counterweight.controls import Screenshot


@pytest.fixture
def svg() -> ElementTree:
    root = Element("parent")
    SubElement(root, "child")
    return ElementTree(element=root)


@pytest.mark.parametrize(
    "path_parts",
    (
        ("screenshot.svg",),
        ("subdir", "screenshot.svg"),
    ),
)
def test_to_file(tmp_path: Path, path_parts: tuple[str], svg: ElementTree) -> None:
    full_path = tmp_path.joinpath(*path_parts)
    screenshot = Screenshot.to_file(full_path)

    screenshot.handler(svg)

    assert full_path.stat().st_size > 0


def test_indent(tmp_path: Path, svg: ElementTree) -> None:
    path = tmp_path / "screenshot.svg"
    screenshot = Screenshot.to_file(path, indent=4)

    screenshot.handler(svg)

    assert "\n    " in path.read_text()
