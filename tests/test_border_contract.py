from __future__ import annotations

import io

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div
from counterweight.styles.utilities import Side, border_contract, border_light, border_sides, size


async def render_box(sides: frozenset[Side], contract: int) -> str:
    @component
    def root() -> Div:
        return Div(style=border_light | border_sides(sides) | border_contract(contract) | size(7, 4))

    capture = io.StringIO()
    await app(root, headless=True, dimensions=(7, 4), autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()])
    return capture.getvalue().rstrip("\n")


@pytest.mark.parametrize(
    ("sides", "contract", "expected"),
    [
        (
            frozenset({"top", "left"}),
            2,
            [
                "┌────  ",
                "│      ",
                "       ",
                "       ",
            ],
        ),
        (
            frozenset({"bottom", "right"}),
            1,
            [
                "       ",
                "      │",
                "      │",
                " ─────┘",
            ],
        ),
        (
            frozenset({"left", "right"}),
            1,
            [
                "       ",
                "│     │",
                "│     │",
                "       ",
            ],
        ),
        (
            frozenset({"top", "bottom", "left", "right"}),
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
    sides: frozenset[Side], contract: int, expected: list[str]
) -> None:
    assert await render_box(sides, contract) == "\n".join(expected)
