from __future__ import annotations

import pytest

from mkdocs_hooks.screenshot_tabs import add_text_tabs

TEXT = {"layout-ratio": "┌──┐\n│ab│\n└──┘"}


def test_screenshot_becomes_image_and_text_tabs() -> None:
    markdown = "Intro.\n\n![Ratios](../assets/layout-ratio.svg)\n\nOutro.\n"

    assert add_text_tabs(markdown, TEXT.__getitem__) == "\n".join(
        [
            "Intro.",
            "",
            '=== "Screenshot"',
            "",
            "    ![Ratios](../assets/layout-ratio.svg)",
            "",
            '=== "Text"',
            "",
            "    ``` { .text .screenshot-text }",
            "    ┌──┐",
            "    │ab│",
            "    └──┘",
            "    ```",
            "",
            "Outro.",
            "",
        ]
    )


def test_indented_screenshot_keeps_its_indentation() -> None:
    markdown = '=== "Flexbox"\n\n    ![Ratios](../assets/layout-ratio.svg)\n'

    result = add_text_tabs(markdown, TEXT.__getitem__)

    assert '    === "Screenshot"\n\n        ![Ratios](../assets/layout-ratio.svg)' in result
    assert "        │ab│" in result


@pytest.mark.parametrize(
    "markdown",
    [
        "![Logo](../assets/favicon.png)\n",
        "See ![Ratios](../assets/layout-ratio.svg) inline.\n",
    ],
)
def test_other_images_are_left_alone(markdown: str) -> None:
    assert add_text_tabs(markdown, TEXT.__getitem__) == markdown


def test_screenshot_without_text_fails() -> None:
    with pytest.raises(KeyError):
        add_text_tabs("![Missing](../assets/missing.svg)\n", TEXT.__getitem__)
