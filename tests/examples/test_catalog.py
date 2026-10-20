from __future__ import annotations

import subprocess
import sys
from collections import Counter
from types import ModuleType

import pytest

from counterweight.examples.apps import chat
from counterweight.examples.catalog import Example
from counterweight.examples.catalog import UnknownExample
from counterweight.examples.catalog import copied
from counterweight.examples.catalog import example_of
from counterweight.examples.catalog import examples
from counterweight.examples.catalog import find
from counterweight.examples.catalog import shown
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.examples.snippets import box_model
from counterweight.examples.snippets import layout_splitting

CATALOG = examples()


def test_every_example_has_a_name_of_its_own() -> None:
    assert [name for name, count in Counter(example.name for example in CATALOG).items() if count > 1] == []


def test_the_apps_come_first_then_the_snippets_by_section() -> None:
    order = [(example.kind != "app", example.section, example.name) for example in CATALOG]

    assert (order, CATALOG[0].kind, CATALOG[-1].kind) == (sorted(order), "app", "snippet")


@pytest.mark.parametrize("example", CATALOG, ids=lambda example: example.name)
def test_an_examples_roots_are_exactly_the_roots_its_scenes_render(example: Example) -> None:
    scenes: list[Still | Demo] = [*example.stills, *example.demos]

    assert {scene.root.func.__name__ for scene in scenes} == {root.__name__ for root in example.roots}


@pytest.mark.parametrize("example", CATALOG, ids=lambda example: example.name)
def test_an_example_has_a_title_and_a_description(example: Example) -> None:
    assert (bool(example.title), bool(example.description), example.title.endswith(".")) == (True, True, False)


def test_an_app_is_named_for_its_module_and_runs_its_root() -> None:
    assert find("chat", CATALOG) == (example_of(chat, "app"), chat.root)


def test_a_snippet_runs_its_first_root_unless_one_is_named() -> None:
    example, first = find("layout-splitting", CATALOG)
    _, named = find("layout-splitting:equal-grid", CATALOG)

    assert (first, named, example.root_name(named)) == (
        layout_splitting.equal_flex,
        layout_splitting.equal_grid,
        "layout-splitting:equal-grid",
    )


def test_a_snippet_with_one_root_names_it_by_the_snippets_name() -> None:
    example, root = find("box-model", CATALOG)

    assert (example.root_name(root), example.section, example.title) == ("box-model", "Layout", "The box model")


@pytest.mark.parametrize(
    ("name", "message"),
    [("no-such-example", "no example named 'no-such-example'"), ("box-model:nope", "box-model has no root named")],
)
def test_finding_a_name_that_names_nothing_fails(name: str, message: str) -> None:
    with pytest.raises(UnknownExample, match=message):
        find(name, CATALOG)


def test_an_example_without_a_docstring_fails() -> None:
    module = ModuleType("counterweight.examples.snippets.nameless")

    with pytest.raises(ValueError, match="no docstring"):
        example_of(module, "snippet")


def test_a_snippet_whose_title_names_no_section_fails() -> None:
    module = ModuleType("counterweight.examples.snippets.unsorted", "A title without a section.")

    with pytest.raises(ValueError, match="section"):
        example_of(module, "snippet")


def test_listing_the_examples_does_no_work_that_loads_the_emulator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from counterweight.examples.catalog import examples; examples();"
            " print('pyghostty._ffi' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


SOURCE = '''"""Title"""

# --8<-- [start:code]
x = 1
# --8<-- [end:code]


# --8<-- [start:scenes]
STILLS = []
# --8<-- [end:scenes]


if __name__ == "__main__":
    print(x)
'''


def test_a_shown_example_keeps_its_scenes_and_drops_the_markers() -> None:
    assert shown(SOURCE) == SOURCE.replace("# --8<-- [start:code]\n", "").replace("# --8<-- [end:code]\n", "").replace(
        "# --8<-- [start:scenes]\n", ""
    ).replace("# --8<-- [end:scenes]\n", "")


def test_a_copied_example_drops_its_scenes_and_the_markers() -> None:
    assert copied(SOURCE) == '"""Title"""\n\nx = 1\n\n\nif __name__ == "__main__":\n    print(x)\n'


def test_a_copied_example_is_the_module_as_it_runs() -> None:
    source = copied(box_model.__loader__.get_source(box_model.__name__))  # type: ignore[union-attr]

    assert ("STILLS" in source, "--8<--" in source, 'if __name__ == "__main__":' in source) == (False, False, True)
