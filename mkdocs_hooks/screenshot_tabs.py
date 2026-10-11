"""
Show each docs screenshot as two tabs: the SVG image, and its plain-text twin to copy from.

`docs.examples.generate_screenshots` writes `docs/assets/<name>.txt` beside every `<name>.svg`,
so pages link only the SVG, and this hook adds the text when the site is built.
"""

import re
from collections.abc import Callable
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

SCREENSHOT = re.compile(
    r"^(?P<indent>[ \t]*)!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]*/assets/(?P<name>[\w.-]+)\.svg)\)[ \t]*$",
    re.MULTILINE,
)


def add_text_tabs(markdown: str, read_text: Callable[[str], str]) -> str:
    """
    Replace every line that is only a screenshot image with tabs showing the image and its text.

    `read_text` returns the text screenshot for an asset name.
    The tabs keep the image's indentation, so a screenshot inside another tab stays inside it.
    """

    def tabs(match: re.Match[str]) -> str:
        indent = match["indent"]
        inner = indent + " " * 4
        text = "\n".join(inner + line for line in read_text(match["name"]).splitlines())
        return "\n".join(
            [
                f'{indent}=== "Screenshot"',
                "",
                f"{inner}![{match['alt']}]({match['src']})",
                "",
                f'{indent}=== "Text"',
                "",
                f"{inner}``` {{ .text .screenshot-text }}",
                text,
                f"{inner}```",
            ]
        )

    return SCREENSHOT.sub(tabs, markdown)


def on_page_markdown(markdown: str, /, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    assets = Path(config.docs_dir) / "assets"
    return add_text_tabs(markdown, lambda name: (assets / f"{name}.txt").read_text())
