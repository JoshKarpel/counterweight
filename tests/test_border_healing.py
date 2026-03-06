from __future__ import annotations

import waxy

from counterweight.border_healing import heal_borders
from counterweight.elements import AnyElement, Div, Text
from counterweight.hooks.impls import Hooks
from counterweight.layout import ResolvedLayout, compute_layout
from counterweight.paint import paint_layout, paint_to_str
from counterweight.shadow import ShadowNode
from counterweight.styles.styles import Style
from counterweight.styles.utilities import (
    align_children_center,
    align_self_stretch,
    border_collapse,
    border_double,
    border_light,
    col,
    grow,
    justify_children_center,
    row,
    size,
    text_justify_center,
)


def _shadow(element: AnyElement, children: list[ShadowNode] | None = None) -> ShadowNode:
    return ShadowNode(component=None, element=element, hooks=Hooks(), children=children or [])


def _layout(root: ShadowNode, w: int = 60, h: int = 20) -> list[tuple[AnyElement, ResolvedLayout]]:
    return compute_layout(root, waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h)))


def _layout_screened(root: ShadowNode, w: int = 60, h: int = 20) -> list[tuple[AnyElement, ResolvedLayout]]:
    screen_style = Style(
        layout=waxy.Style(display=waxy.Display.Grid, size_width=waxy.Length(w), size_height=waxy.Length(h))
    )
    screen = _shadow(Div(style=screen_style), children=[root])
    return compute_layout(screen, waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h)))


def _render(root: ShadowNode, w: int = 60, h: int = 20) -> str:
    elements = _layout(root, w, h)
    paint, hints = paint_layout(elements)
    paint |= heal_borders(paint, hints)
    return paint_to_str(paint)


def _render_screened(root: ShadowNode, w: int = 60, h: int = 20) -> str:
    elements = _layout_screened(root, w, h)
    paint, hints = paint_layout(elements)
    paint |= heal_borders(paint, hints)
    return paint_to_str(paint)


# ---------------------------------------------------------------------------
# Row: healed seam characters ┬ / ┴
# ---------------------------------------------------------------------------


def test_row_collapse_two_siblings_heals_seam() -> None:
    child_a = _shadow(Div(style=border_light | size(5, 3)))
    child_b = _shadow(Div(style=border_light | size(5, 3)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b])

    assert _render(root) == "\n".join(
        [
            "┌───┬───┐",
            "│   │   │",
            "└───┴───┘",
        ]
    )


def test_row_collapse_three_siblings_heals_both_seams() -> None:
    child_a = _shadow(Div(style=border_light | size(5, 3)))
    child_b = _shadow(Div(style=border_light | size(5, 3)))
    child_c = _shadow(Div(style=border_light | size(5, 3)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b, child_c])

    assert _render(root) == "\n".join(
        [
            "┌───┬───┬───┐",
            "│   │   │   │",
            "└───┴───┴───┘",
        ]
    )


# ---------------------------------------------------------------------------
# Col: healed seam characters ├ / ┤
# ---------------------------------------------------------------------------


def test_col_collapse_two_siblings_heals_seam() -> None:
    child_a = _shadow(Div(style=border_light | size(5, 3)))
    child_b = _shadow(Div(style=border_light | size(5, 3)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b])

    assert _render(root) == "\n".join(
        [
            "┌───┐",
            "│   │",
            "├───┤",
            "│   │",
            "└───┘",
        ]
    )


def test_col_collapse_three_siblings_heals_both_seams() -> None:
    child_a = _shadow(Div(style=border_light | size(5, 3)))
    child_b = _shadow(Div(style=border_light | size(5, 3)))
    child_c = _shadow(Div(style=border_light | size(5, 3)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    assert _render(root) == "\n".join(
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


def test_doc_example_border_healing() -> None:
    container_style = grow(1) | align_self_stretch | border_collapse
    box_style = grow(1) | align_self_stretch | justify_children_center | align_children_center

    def box(label: str) -> ShadowNode:
        return _shadow(
            Div(style=box_style | border_double),
            children=[_shadow(Text(content=label, style=text_justify_center))],
        )

    root = _shadow(
        Div(style=row | container_style),
        children=[
            _shadow(
                Div(style=col | container_style),
                children=[box("A1"), box("A2")],
            ),
            _shadow(
                Div(style=col | container_style),
                children=[
                    _shadow(Div(style=row | container_style), children=[box("B1"), box("B2")]),
                    _shadow(Div(style=row | container_style), children=[box("C1"), box("C2"), box("C3"), box("C4")]),
                    _shadow(Div(style=row | container_style), children=[box("D1"), box("D2"), box("D3")]),
                ],
            ),
        ],
    )

    assert _render_screened(root) == "\n".join(
        [
            "╔════════════════════════════╦══════════════╦══════════════╗",
            "║                            ║              ║              ║",
            "║                            ║              ║              ║",
            "║                            ║      B1      ║      B2      ║",
            "║             A1             ║              ║              ║",
            "║                            ║              ║              ║",
            "║                            ╠══════╦═══════╬══════╦═══════╣",
            "║                            ║      ║       ║      ║       ║",
            "║                            ║      ║       ║      ║       ║",
            "╠════════════════════════════╣   C1 ║   C2  ║  C3  ║   C4  ║",
            "║                            ║      ║       ║      ║       ║",
            "║                            ║      ║       ║      ║       ║",
            "║                            ╠══════╩══╦════╩════╦═╩═══════╣",
            "║                            ║         ║         ║         ║",
            "║             A2             ║         ║         ║         ║",
            "║                            ║    D1   ║    D2   ║    D3   ║",
            "║                            ║         ║         ║         ║",
            "║                            ║         ║         ║         ║",
            "║                            ║         ║         ║         ║",
            "╚════════════════════════════╩═════════╩═════════╩═════════╝",
        ]
    )
