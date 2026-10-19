"""
Play a docs recording in a page, from a marker line.

A page writes `<!-- cast: spinner -->` on its own line where the player goes,
and `docs.generate_screenshots` writes `docs/assets/spinner.cast` from a module's `DEMOS`.
The marker becomes an element `docs/assets/casts.js` starts asciinema-player in,
since the player is a script and Markdown can only hold the element it starts in.
"""

import re
from collections.abc import Callable
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

CAST = re.compile(r"^(?P<indent>[ \t]*)<!-- cast: (?P<name>[\w.-]+) -->[ \t]*$", re.MULTILINE)


def cast_url(page_url: str, name: str) -> str:
    """
    The URL of the recording `name` from the page at `page_url`, relative so the site works under any path.
    Raw HTML isn't rewritten as Markdown links are, so it climbs out of the page's directory itself.
    """
    return "../" * page_url.count("/") + f"assets/{name}.cast"


def include_casts(markdown: str, page_url: str, is_recorded: Callable[[str], bool]) -> str:
    """
    Replace every cast marker line with the element the player starts in.

    `is_recorded` says whether a recording exists, by name.

    Raises:
        FileNotFoundError: If a marker names a recording that doesn't exist, so a renamed recording fails the build.
    """

    def player(match: re.Match[str]) -> str:
        name = match["name"]
        if not is_recorded(name):
            raise FileNotFoundError(f"No recording docs/assets/{name}.cast for the cast marker {match[0].strip()!r}")
        return f'{match["indent"]}<div class="asciicast" data-cast="{cast_url(page_url, name)}"></div>'

    return CAST.sub(player, markdown)


def on_page_markdown(markdown: str, /, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    assets = Path(config.docs_dir) / "assets"
    return include_casts(markdown, page.url, lambda name: (assets / f"{name}.cast").exists())
