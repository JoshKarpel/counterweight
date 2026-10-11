from collections.abc import Sequence

import pytest
import waxy
from pytest_mock import MockerFixture

from counterweight import layout
from counterweight.elements import AnyElement, Chunk, Div, Text
from counterweight.layout import LayoutTree, MeasurableText, ResolvedLayout, _measure_text
from counterweight.shadow import ShadowNode, update_shadow
from counterweight.styles.styles import CellStyle, Color
from counterweight.styles.utilities import border, col, fill, row, text_wrap_stable

AVAILABLE = waxy.AvailableSize(width=waxy.Definite(40), height=waxy.Definite(12))


def frames(tree: LayoutTree, elements: Sequence[AnyElement]) -> ShadowNode:
    """Render each element as one frame through `tree`, and return the last frame's shadow tree."""
    shadow: ShadowNode | None = None
    for element in elements:
        shadow = update_shadow(element, shadow)
        tree.compute(shadow, AVAILABLE)
    if shadow is None:
        raise ValueError("No frames")
    return shadow


def panes(*texts: str) -> Div:
    return Div(
        style=col,
        children=[
            Div(style=row | border, children=[Text(content=text, style=fill(1) | text_wrap_stable)]) for text in texts
        ],
    )


def canvas(colors: Sequence[str]) -> Div:
    return Div(
        children=[
            Text(content=[Chunk(content="▀", style=CellStyle(foreground=Color.from_name(color))) for color in colors]),
            Text(content="label"),
        ]
    )


def ancestors(tree: LayoutTree, node: waxy.NodeId) -> list[waxy.NodeId]:
    parent = tree.tree.parent(node)
    return [] if parent is None else [parent, *ancestors(tree, parent)]


def nodes_by_text(tree: LayoutTree) -> dict[str, waxy.NodeId]:
    return {
        shadow.element.content: node
        for node, shadow in tree.shadows.items()
        if isinstance(shadow.element, Text) and isinstance(shadow.element.content, str)
    }


@pytest.mark.parametrize(
    "element",
    [
        panes("first pane", "second pane, which wraps onto more lines than the first"),
        canvas(["red", "green", "blue"]),
    ],
)
def test_frame_with_no_changes_dirties_no_node(element: AnyElement) -> None:
    tree = LayoutTree()
    shadow = frames(tree, [element])

    tree.update(update_shadow(element, shadow))

    assert [node for node in tree.shadows if tree.tree.dirty(node)] == []


def test_changed_text_dirties_only_itself_and_its_ancestors() -> None:
    tree = LayoutTree()
    shadow = frames(tree, [panes("alpha", "beta", "gamma")])

    tree.update(update_shadow(panes("alpha", "beta, longer now", "gamma"), shadow))

    changed = nodes_by_text(tree)["beta, longer now"]
    assert {node for node in tree.shadows if tree.tree.dirty(node)} == {changed, *ancestors(tree, changed)}


def test_changed_chunk_dirties_its_text() -> None:
    tree = LayoutTree()
    shadow = frames(tree, [canvas(["red", "green", "blue"])])

    tree.update(update_shadow(canvas(["red", "yellow", "blue"]), shadow))

    [canvas_node] = [
        node
        for node, shadow in tree.shadows.items()
        if isinstance(shadow.element, Text) and not isinstance(shadow.element.content, str)
    ]
    assert tree.tree.dirty(canvas_node)


SEQUENCES = {
    "grow and shrink": [panes("a"), panes("a", "b", "c"), panes("a"), panes(), panes("a", "b")],
    "text becomes a div and back": [
        Div(children=[Text(content="leaf")]),
        Div(children=[Div(style=border, children=[Text(content="nested"), Text(content="twice")])]),
        Div(children=[Text(content="leaf again")]),
    ],
    "text becomes an empty div": [
        Div(children=[Text(content="leaf"), Text(content="sibling")]),
        Div(children=[Div(), Text(content="sibling")]),
    ],
    "unmount a nested subtree": [
        Div(children=[panes("deep", "deeper"), Text(content="sibling")]),
        Div(children=[Text(content="sibling")]),
    ],
}


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_mounting_and_unmounting_leaves_no_orphaned_nodes(elements: list[AnyElement]) -> None:
    tree = LayoutTree()
    shadow = frames(tree, elements)

    assert tree.tree.total_node_count() == len(list(shadow.walk()))


def fresh_layout(element: AnyElement) -> list[tuple[AnyElement, ResolvedLayout]]:
    return LayoutTree().compute(update_shadow(element, None), AVAILABLE)


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_reused_tree_lays_out_each_frame_as_a_fresh_tree_does(elements: list[AnyElement]) -> None:
    tree = LayoutTree()
    shadow: ShadowNode | None = None
    for element in elements:
        shadow = update_shadow(element, shadow)

        assert tree.compute(shadow, AVAILABLE) == fresh_layout(element)


def test_text_is_not_wrapped_again_at_a_width_it_was_measured_at(mocker: MockerFixture) -> None:
    text = MeasurableText.of(("the quick brown fox", CellStyle(), "stable"))
    wrap_cells = mocker.spy(layout, "wrap_cells")

    _measure_text(waxy.KnownSize(width=10.0), waxy.AvailableSize(waxy.MaxContent(), waxy.MaxContent()), text)
    _measure_text(waxy.KnownSize(), waxy.AvailableSize(waxy.Definite(10), waxy.MaxContent()), text)
    _measure_text(waxy.KnownSize(height=3.0), waxy.AvailableSize(waxy.Definite(10), waxy.Definite(5)), text)

    assert wrap_cells.call_count == 1
