from __future__ import annotations

import io

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div
from counterweight.styles import Style
from counterweight.styles.utilities import (
    border,
    border_bottom,
    border_contract,
    border_left,
    border_right,
    border_top,
    border_x,
    size,
)


async def render_box(sides: Style, contract: int) -> str:
    @component
    def root() -> Div:
        return Div(style=sides | border_contract(contract) | size(7, 4))

    capture = io.StringIO()
    await app(root, headless=True, dimensions=(7, 4), autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()])
    return capture.getvalue().rstrip("\n")


@pytest.mark.parametrize(
    ("sides", "contract", "expected"),
    [
        (
            border_top | border_left,
            2,
            [
                "┌────  ",
                "│      ",
                "       ",
                "       ",
            ],
        ),
        (
            border_bottom | border_right,
            1,
            [
                "       ",
                "      │",
                "      │",
                " ─────┘",
            ],
        ),
        (
            border_x,
            1,
            [
                "       ",
                "│     │",
                "│     │",
                "       ",
            ],
        ),
        (
            border,
            3,
            [
                "┌─────┐",
                "│     │",
                "│     │",
                "└─────┘",
            ],
        ),
    ],
)
async def test_border_contract_shortens_edges_next_to_missing_sides(
    sides: Style, contract: int, expected: list[str]
) -> None:
    assert await render_box(sides, contract) == "\n".join(expected)
