import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.markdown import MarkdownStyles, markdown
from counterweight.styles.styles import Style, TextWrap
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

SAMPLE = """\
It was the *best of times*, it was the *worst of times*,
it was the age of **wisdom**, it was the age of **foolishness**.
"""

WRAP_STYLE: dict[TextWrap, Style] = {
    "none": text_wrap_none | overflow_hidden,
    "stable": text_wrap_stable,
    "pretty": text_wrap_pretty,
    "balance": text_wrap_balance,
}


@component
def wrap_pane(mode: TextWrap) -> Div:
    return Div(
        style=fill(1) | col | border | pad_x(1),
        children=(
            Text(
                content=f" {mode} ",
                style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border,
            ),
            markdown(SAMPLE, MarkdownStyles(paragraph=WRAP_STYLE[mode])),
        ),
    )


@component
def root() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row | fill(1),
                children=tuple(wrap_pane(mode) for mode in WRAP_STYLE),
            ),
        ),
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root(), "text-wrap", (120, 14))]


if __name__ == "__main__":
    asyncio.run(app(root()))
