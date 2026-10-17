"""
The cast markers in the docs (`<!-- cast: name -->`) become the element the player starts in.
A line that only resembles a marker is an HTML comment that renders as nothing, so a test catches it instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mkdocs_hooks.casts import CAST
from mkdocs_hooks.casts import cast_url
from mkdocs_hooks.casts import include_casts

DOCS = Path(__file__).parent.parent / "docs"
PAGES = sorted(DOCS.rglob("*.md"))

RECORDED = {"spinner", "use-clock-lap-timer"}.__contains__

LOOKS_LIKE_CAST = re.compile(r"^\s*<!--\s*cast\b")


def test_marker_becomes_the_element_the_player_starts_in() -> None:
    markdown = "Intro.\n\n<!-- cast: spinner -->\n\nOutro.\n"

    assert include_casts(markdown, "cookbook/spinners/", RECORDED) == (
        'Intro.\n\n<div class="asciicast" data-cast="../../assets/spinner.cast"></div>\n\nOutro.\n'
    )


def test_indented_marker_keeps_its_indentation() -> None:
    assert include_casts('=== "Tab"\n\n    <!-- cast: spinner -->\n', "", RECORDED) == (
        '=== "Tab"\n\n    <div class="asciicast" data-cast="assets/spinner.cast"></div>\n'
    )


@pytest.mark.parametrize(
    ("page_url", "url"),
    [
        ("", "assets/spinner.cast"),
        ("changelog/", "../assets/spinner.cast"),
        ("hooks/use_clock/", "../../assets/spinner.cast"),
    ],
)
def test_a_recordings_url_climbs_out_of_the_pages_directory(page_url: str, url: str) -> None:
    assert cast_url(page_url, "spinner") == url


@pytest.mark.parametrize(
    "markdown",
    [
        "<!-- a comment about the spinner cast -->\n",
        "See <!-- cast: spinner --> inline.\n",
    ],
)
def test_other_comments_are_left_alone(markdown: str) -> None:
    assert include_casts(markdown, "", RECORDED) == markdown


def test_a_marker_naming_a_missing_recording_fails() -> None:
    with pytest.raises(FileNotFoundError, match="missing"):
        include_casts("<!-- cast: missing -->\n", "", RECORDED)


@pytest.mark.parametrize("page", PAGES, ids=lambda page: str(page.relative_to(DOCS)))
def test_every_cast_marker_has_the_syntax_the_hook_reads(page: Path) -> None:
    malformed = [
        f"{number}: {line}"
        for number, line in enumerate(page.read_text().splitlines(), start=1)
        if LOOKS_LIKE_CAST.match(line) and not CAST.fullmatch(line)
    ]

    assert malformed == []


@pytest.mark.parametrize("page", PAGES, ids=lambda page: str(page.relative_to(DOCS)))
def test_every_cast_marker_names_a_recording_that_exists(page: Path) -> None:
    include_casts(page.read_text(), "", lambda name: (DOCS / "assets" / f"{name}.cast").exists())
