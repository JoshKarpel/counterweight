from __future__ import annotations

import io

import pytest
import waxy

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles import Style
from counterweight.styles.utilities import (
    border,
    border_heavy,
    border_left,
    border_left_0,
    border_none,
    border_right_0,
    border_top,
)


async def render_box(style: Style) -> str:
    @component
    def root() -> Div:
        return Div(style=style, children=[Text(content="ab")])

    capture = io.StringIO()
    await app(root, headless=True, dimensions=(6, 4), autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()])
    return capture.getvalue().rstrip("\n")


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        pytest.param(
            border,
            [
                "┌────┐",
                "│ab  │",
                "│    │",
                "└────┘",
            ],
            id="all-sides-default-kind",
        ),
        pytest.param(
            border | border_heavy,
            [
                "┏━━━━┓",
                "┃ab  ┃",
                "┃    ┃",
                "┗━━━━┛",
            ],
            id="kind-changes-characters",
        ),
        pytest.param(
            border_heavy,
            [
                "ab    ",
                "      ",
                "      ",
                "      ",
            ],
            id="kind-without-widths",
        ),
        pytest.param(
            border | border_none,
            [
                "ab    ",
                "      ",
                "      ",
                "      ",
            ],
            id="none-removes-border-and-space",
        ),
        pytest.param(
            border_top,
            [
                "──────",
                "ab    ",
                "      ",
                "      ",
            ],
            id="one-side",
        ),
        pytest.param(
            border_top | border_left,
            [
                "┌─────",
                "│ab   ",
                "│     ",
                "│     ",
            ],
            id="sides-compose",
        ),
        pytest.param(
            border | border_left_0 | border_right_0,
            [
                "──────",
                "ab    ",
                "      ",
                "──────",
            ],
            id="zeroes-compose",
        ),
        pytest.param(
            border_right_0 | border,
            [
                "┌────┐",
                "│ab  │",
                "│    │",
                "└────┘",
            ],
            id="later-border-wins",
        ),
    ],
)
async def test_border_widths_reserve_and_draw_the_same_edges(style: Style, expected: list[str]) -> None:
    assert await render_box(style) == "\n".join(expected)


@pytest.mark.parametrize("width", [waxy.Length(0), waxy.Length(1)])
def test_border_width_of_zero_or_one_cell_is_allowed(width: waxy.LengthPercentageValue) -> None:
    assert Style(layout=waxy.Style(border_top=width)).layout.border_top == width


@pytest.mark.parametrize("width", [waxy.Length(2), waxy.Percent(0.5)])
def test_border_width_other_than_zero_or_one_cell_raises(width: waxy.LengthPercentageValue) -> None:
    with pytest.raises(ValueError, match="border_top"):
        Style(layout=waxy.Style(border_top=width))
