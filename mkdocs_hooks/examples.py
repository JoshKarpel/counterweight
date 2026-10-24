"""
Show a section of an example module, an app or a snippet, as a Python code block, from a marker line in a page.

A page writes `<!-- example: layout_text.py:wrap-in-pane -->` on its own line where the code goes,
and the module brackets the section with `# --8<-- [start:wrap-in-pane]` and `# --8<-- [end:wrap-in-pane]`.
A marker with no section, `<!-- example: todo.py -->`, shows the whole module as `counterweight examples copy` writes it.
The marker sits outside any code block so that every Python block in a page is real Python,
which a formatter can format without rewriting a marker it reads as code.
"""

import re
from collections.abc import Callable
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

from counterweight.examples.catalog import copied

EXAMPLE = re.compile(
    r"^(?P<indent>[ \t]*)<!-- example: (?P<module>[\w-]+\.py)(?::(?P<section>[\w-]+))? -->[ \t]*$",
    re.MULTILINE,
)

EXAMPLES = Path(__file__).parent.parent / "src" / "counterweight" / "examples"


def section(source: str, name: str) -> str:
    """
    The lines of `source` between `# --8<-- [start:<name>]` and `# --8<-- [end:<name>]`, without the markers.

    Raises `ValueError` if `source` doesn't have exactly one such section, so a renamed section fails the build.
    """
    lines = source.splitlines()
    start = f"# --8<-- [start:{name}]"
    end = f"# --8<-- [end:{name}]"
    if lines.count(start) != 1 or lines.count(end) != 1 or lines.index(start) > lines.index(end):
        raise ValueError(f"Expected one section {name!r} bracketed by {start!r} and {end!r}")
    return "\n".join(lines[lines.index(start) + 1 : lines.index(end)])


def include_examples(markdown: str, read_module: Callable[[str], str]) -> str:
    """
    Replace every example marker line with a Python code block of that section of the module.

    `read_module` returns the source of an example module by file name.
    The code block keeps the marker's indentation, so an example inside a tab stays inside it,
    and its fence is longer than any run of backticks in the code, so a fence in a string doesn't close it.
    """

    def code_block(match: re.Match[str]) -> str:
        indent = match["indent"]
        source = read_module(match["module"])
        code = copied(source).strip() if match["section"] is None else section(source, match["section"])
        fence = "`" * (max([2, *(len(run) for run in re.findall(r"`+", code))]) + 1)
        return "\n".join(
            [
                f"{indent}{fence}python",
                *(f"{indent}{line}" if line else "" for line in code.splitlines()),
                f"{indent}{fence}",
            ]
        )

    return EXAMPLE.sub(code_block, markdown)


def read_example(module: str) -> str:
    """The source of the app or snippet module named `module`, such as `todo.py`."""
    (path,) = (path for kind in ("apps", "snippets") if (path := EXAMPLES / kind / module).exists())
    return path.read_text()


def on_page_markdown(markdown: str, /, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    return include_examples(markdown, read_example)
