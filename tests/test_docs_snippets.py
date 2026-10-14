"""
The docs' snippet includes (`--8<-- "file.py:section"`) keep the syntax `pymdownx.snippets` reads.
A line that only resembles one (as a formatter that reads it as Python leaves it, `--8 < --"file.py:section"`)
renders as literal text without failing the docs build, so this catches it instead.
"""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).parent.parent / "docs"

LOOKS_LIKE_SNIPPET = re.compile(r"^\s*-+\s*8\s*<")
SNIPPET = re.compile(r"""^[ \t]*-+8<-+(?:[ \t]+(?:"[^"\n]+"|'[^'\n]+'))?$""")


@pytest.mark.parametrize("page", sorted(DOCS.rglob("*.md")), ids=lambda page: str(page.relative_to(DOCS)))
def test_every_snippet_include_has_the_syntax_pymdownx_snippets_reads(page: Path) -> None:
    malformed = [
        f"{number}: {line}"
        for number, line in enumerate(page.read_text().splitlines(), start=1)
        if LOOKS_LIKE_SNIPPET.match(line) and not SNIPPET.match(line)
    ]

    assert malformed == []
