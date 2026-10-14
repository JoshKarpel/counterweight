from __future__ import annotations

import io

import pytest

from counterweight.app import app
from counterweight.border_healing import heal_borders
from counterweight.components import Component, component
from counterweight.controls import Quit, Screenshot, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.geometry import Position
from counterweight.paint import BLANK, Cell, Paint
from counterweight.styles.styles import CellStyle, JoinedBorderKind, resolve_cell_style
from counterweight.styles.utilities import (
    align_self_stretch,
    border,
    border_collapse,
    border_double,
    center_children,
    col,
    fill,
    row,
    size,
    text_justify_center,
)


async def _render(root: Component, dimensions: tuple[int, int]) -> str:
    capture = io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()],
        check_purity=True,
    )
    return capture.getvalue().rstrip("\n")


# ---------------------------------------------------------------------------
# Row: healed seam characters ┬ / ┴
# ---------------------------------------------------------------------------


async def test_row_collapse_two_siblings_heals_seam() -> None:
    @component
    def root() -> Div:
        return Div(
            style=row | border_collapse,
            children=(
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ),
        )

    assert await _render(root(), (9, 3)) == "\n".join(
        [
            "┌───┬───┐",
            "│   │   │",
            "└───┴───┘",
        ]
    )


async def test_row_collapse_three_siblings_heals_both_seams() -> None:
    @component
    def root() -> Div:
        return Div(
            style=row | border_collapse,
            children=(
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ),
        )

    assert await _render(root(), (13, 3)) == "\n".join(
        [
            "┌───┬───┬───┐",
            "│   │   │   │",
            "└───┴───┴───┘",
        ]
    )


# ---------------------------------------------------------------------------
# Col: healed seam characters ├ / ┤
# ---------------------------------------------------------------------------


async def test_col_collapse_two_siblings_heals_seam() -> None:
    @component
    def root() -> Div:
        return Div(
            style=col | border_collapse,
            children=(
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ),
        )

    assert await _render(root(), (5, 5)) == "\n".join(
        [
            "┌───┐",
            "│   │",
            "├───┤",
            "│   │",
            "└───┘",
        ]
    )


async def test_col_collapse_three_siblings_heals_both_seams() -> None:
    @component
    def root() -> Div:
        return Div(
            style=col | border_collapse,
            children=(
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ),
        )

    assert await _render(root(), (5, 7)) == "\n".join(
        [
            "┌───┐",
            "│   │",
            "├───┤",
            "│   │",
            "├───┤",
            "│   │",
            "└───┘",
        ]
    )


# ---------------------------------------------------------------------------
# Complex layout: doc example (A1/A2 col | B1/B2, C1-C4, D1-D3 nested rows)
# ---------------------------------------------------------------------------


async def test_doc_example_border_healing() -> None:
    container_style = fill(1) | align_self_stretch | border_collapse
    box_style = fill(1) | align_self_stretch | center_children

    @component
    def root() -> Div:
        def box(label: str) -> Div:
            return Div(
                style=box_style | border | border_double,
                children=(Text(content=label, style=text_justify_center),),
            )

        return Div(
            style=row | container_style,
            children=(
                Div(
                    style=col | container_style,
                    children=(box("A1"), box("A2")),
                ),
                Div(
                    style=col | container_style,
                    children=(
                        Div(style=row | container_style, children=(box("B1"), box("B2"))),
                        Div(style=row | container_style, children=(box("C1"), box("C2"), box("C3"), box("C4"))),
                        Div(style=row | container_style, children=(box("D1"), box("D2"), box("D3"))),
                    ),
                ),
            ),
        )

    assert await _render(root(), (60, 20)) == "\n".join(
        [
            "╔═════════════════════════════╦═════════════╦══════════════╗",
            "║                             ║             ║              ║",
            "║                             ║             ║              ║",
            "║                             ║     B1      ║      B2      ║",
            "║                             ║             ║              ║",
            "║             A1              ║             ║              ║",
            "║                             ╠══════╦══════╬═══════╦══════╣",
            "║                             ║      ║      ║       ║      ║",
            "║                             ║      ║      ║       ║      ║",
            "║                             ║      ║      ║       ║      ║",
            "╠═════════════════════════════╣  C1  ║  C2  ║  C3   ║  C4  ║",
            "║                             ║      ║      ║       ║      ║",
            "║                             ║      ║      ║       ║      ║",
            "║                             ╠══════╩═╦════╩════╦══╩══════╣",
            "║             A2              ║        ║         ║         ║",
            "║                             ║        ║         ║         ║",
            "║                             ║   D1   ║    D2   ║    D3   ║",
            "║                             ║        ║         ║         ║",
            "║                             ║        ║         ║         ║",
            "╚═════════════════════════════╩════════╩═════════╩═════════╝",
        ]
    )


LIGHT = JoinedBorderKind.Light.value
STYLE = resolve_cell_style(CellStyle())


def paint_of(*rows: str) -> Paint:
    """A paint with one cell per character of `rows`, where `.` is a blank cell."""
    return Paint(
        width=len(rows[0]),
        height=len(rows),
        cells=[BLANK if grapheme == "." else Cell(grapheme, STYLE) for line in rows for grapheme in line],
    )


def healed(paint: Paint, *corners: Position) -> dict[Position, str]:
    return {position: cell.grapheme for position, cell in heal_borders(paint, dict.fromkeys(corners, LIGHT)).items()}


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        pytest.param(("...", "─┌.", "..."), "┬", id="joins-the-left-neighbor-to-the-corners-own-sides"),
        pytest.param(("...", ".┐─", "..."), "┬", id="joins-the-right-neighbor"),
        pytest.param(("...", ".└.", ".│."), "├", id="joins-the-neighbor-below"),
        pytest.param((".│.", ".┌.", "..."), "├", id="joins-the-neighbor-above"),
    ],
)
def test_heal_borders_joins_a_corner_to_the_borders_beside_it(rows: tuple[str, ...], expected: str) -> None:
    assert healed(paint_of(*rows), Position(1, 1)) == {Position(1, 1): expected}


def test_heal_borders_skips_corners_drawn_over_or_off_screen_and_heals_the_rest() -> None:
    paint = paint_of("...", "─T─", "─┐─")

    assert healed(paint, Position(5, 5), Position(1, 1), Position(1, 2)) == {Position(1, 2): "┬"}


async def test_toggling_border_healing_redraws_borders_healed_or_not() -> None:
    frames: list[str] = []

    @component
    def root() -> Div:
        return Div(
            style=row | border_collapse, children=(Div(style=border | size(5, 3)), Div(style=border | size(5, 3)))
        )

    await app(
        root(),
        headless=True,
        dimensions=(9, 3),
        autopilot=[
            ToggleBorderHealing(),
            Screenshot(handler=lambda frame: frames.append(frame.text(ansi=False))),
            ToggleBorderHealing(),
            Screenshot(handler=lambda frame: frames.append(frame.text(ansi=False))),
            Quit(),
        ],
    )

    assert frames == [
        "┌───┌───┐\n│   │   │\n└───└───┘",
        "┌───┬───┐\n│   │   │\n└───┴───┘",
    ]
