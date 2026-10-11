from __future__ import annotations

import io
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
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


async def _render(root_fn: Callable[[], Component], dimensions: tuple[int, int]) -> str:
    capture = io.StringIO()
    await app(
        root_fn,
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()],
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
            children=[
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ],
        )

    assert await _render(root, (9, 3)) == "\n".join(
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
            children=[
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ],
        )

    assert await _render(root, (13, 3)) == "\n".join(
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
            children=[
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ],
        )

    assert await _render(root, (5, 5)) == "\n".join(
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
            children=[
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
                Div(style=border | size(5, 3)),
            ],
        )

    assert await _render(root, (5, 7)) == "\n".join(
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
                children=[Text(content=label, style=text_justify_center)],
            )

        return Div(
            style=row | container_style,
            children=[
                Div(
                    style=col | container_style,
                    children=[box("A1"), box("A2")],
                ),
                Div(
                    style=col | container_style,
                    children=[
                        Div(style=row | container_style, children=[box("B1"), box("B2")]),
                        Div(style=row | container_style, children=[box("C1"), box("C2"), box("C3"), box("C4")]),
                        Div(style=row | container_style, children=[box("D1"), box("D2"), box("D3")]),
                    ],
                ),
            ],
        )

    assert await _render(root, (60, 20)) == "\n".join(
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
