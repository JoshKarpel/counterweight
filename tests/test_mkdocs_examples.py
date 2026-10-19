"""
The example markers in the docs (`<!-- example: module.py:section -->`, or `<!-- example: module.py -->`)
become the code they name.
A line that only resembles a marker is an HTML comment that renders as nothing, so a test catches it instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mkdocs_hooks.examples import EXAMPLE
from mkdocs_hooks.examples import include_examples
from mkdocs_hooks.examples import read_example
from mkdocs_hooks.examples import section

DOCS = Path(__file__).parent.parent / "docs"
PAGES = sorted(DOCS.rglob("*.md"))

MODULES = {
    "panes.py": "\n".join(
        [
            "import x",
            "",
            "# --8<-- [start:split-panes]",
            "def panes() -> Div:",
            "",
            "    return Div()",
            "# --8<-- [end:split-panes]",
        ]
    ),
}

LOOKS_LIKE_EXAMPLE = re.compile(r"^\s*<!--\s*example\b")


def test_marker_becomes_a_python_code_block_of_its_section() -> None:
    markdown = "Intro.\n\n<!-- example: panes.py:split-panes -->\n\nOutro.\n"

    assert include_examples(markdown, MODULES.__getitem__) == "\n".join(
        [
            "Intro.",
            "",
            "```python",
            "def panes() -> Div:",
            "",
            "    return Div()",
            "```",
            "",
            "Outro.",
            "",
        ]
    )


def test_marker_without_a_section_becomes_the_module_as_copied() -> None:
    source = "\n".join(
        [
            "import x",
            "# --8<-- [start:panes]",
            "panes = 1",
            "# --8<-- [end:panes]",
            "# --8<-- [start:scenes]",
            "STILLS = []",
            "# --8<-- [end:scenes]",
            "",
        ]
    )

    assert include_examples("<!-- example: app.py -->\n", {"app.py": source}.__getitem__) == "\n".join(
        ["```python", "import x", "panes = 1", "```", ""]
    )


def test_indented_marker_keeps_its_indentation_on_every_line_but_blank_ones() -> None:
    markdown = '=== "Flexbox"\n\n    <!-- example: panes.py:split-panes -->\n'

    result = include_examples(markdown, MODULES.__getitem__)

    assert "    ```python\n    def panes() -> Div:\n\n        return Div()\n    ```" in result


@pytest.mark.parametrize(
    ("code", "fence"),
    [
        ("x = '`a`'", "```"),
        ('README = """\n```python\nx = 1\n```\n"""', "````"),
        ('README = """\n`````\n"""', "``````"),
    ],
    ids=["inline", "fenced", "long-fence"],
)
def test_the_fence_is_longer_than_any_backticks_in_the_code(code: str, fence: str) -> None:
    source = f"# --8<-- [start:readme]\n{code}\n# --8<-- [end:readme]\n"

    result = include_examples("<!-- example: readme.py:readme -->\n", {"readme.py": source}.__getitem__)

    assert result == f"{fence}python\n{code}\n{fence}\n"


@pytest.mark.parametrize(
    "markdown",
    [
        "<!-- a comment about panes.py:split-panes -->\n",
        "See <!-- example: panes.py:split-panes --> inline.\n",
    ],
)
def test_other_comments_are_left_alone(markdown: str) -> None:
    assert include_examples(markdown, MODULES.__getitem__) == markdown


@pytest.mark.parametrize(
    "source",
    [
        "# --8<-- [start:other]\nx = 1\n# --8<-- [end:other]\n",
        "# --8<-- [start:split-panes]\nx = 1\n",
        "# --8<-- [end:split-panes]\nx = 1\n# --8<-- [start:split-panes]\n",
        "# --8<-- [start:split-panes]\n# --8<-- [end:split-panes]\n" * 2,
    ],
    ids=["missing", "unterminated", "reversed", "repeated"],
)
def test_a_section_not_bracketed_exactly_once_fails(source: str) -> None:
    with pytest.raises(ValueError, match="split-panes"):
        section(source, "split-panes")


def test_a_missing_module_fails() -> None:
    with pytest.raises(KeyError):
        include_examples("<!-- example: missing.py:split-panes -->\n", MODULES.__getitem__)


@pytest.mark.parametrize("page", PAGES, ids=lambda page: str(page.relative_to(DOCS)))
def test_every_example_marker_has_the_syntax_the_hook_reads(page: Path) -> None:
    malformed = [
        f"{number}: {line}"
        for number, line in enumerate(page.read_text().splitlines(), start=1)
        if LOOKS_LIKE_EXAMPLE.match(line) and not EXAMPLE.fullmatch(line)
    ]

    assert malformed == []


@pytest.mark.parametrize("page", PAGES, ids=lambda page: str(page.relative_to(DOCS)))
def test_every_example_marker_names_a_section_that_exists(page: Path) -> None:
    include_examples(page.read_text(), read_example)
