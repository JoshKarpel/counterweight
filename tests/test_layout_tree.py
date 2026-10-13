from collections.abc import Sequence

import pytest
import waxy
from pytest_mock import MockerFixture

from counterweight import layout
from counterweight.components import component
from counterweight.elements import AnyElement, Chunk, Div, Text
from counterweight.geometry import Rects
from counterweight.layout import (
    NO_LAYOUTS,
    ClearText,
    CreateLeaf,
    Layouts,
    LayoutTree,
    MeasurableText,
    Remove,
    SetChildren,
    SetText,
    _measure_text,
    layout_changes,
    layout_style,
    text_source,
)
from counterweight.shadow import ShadowTree, update_shadow
from counterweight.styles.styles import CellStyle, Color
from counterweight.styles.utilities import border, col, fill, row, text_wrap_stable

AVAILABLE = waxy.AvailableSize(width=waxy.Definite(40), height=waxy.Definite(12))


def frames(tree: LayoutTree, elements: Sequence[AnyElement]) -> ShadowTree:
    """Render each element as one frame through `tree`, and return the last frame's shadow tree."""
    shadow: ShadowTree | None = None
    for element in elements:
        next_shadow = update_shadow(element, shadow, NO_LAYOUTS).tree
        tree.compute(layout_changes(shadow, next_shadow), next_shadow, AVAILABLE)
        shadow = next_shadow
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


@component
def labeled(label: str) -> Text:
    return Text(content=label)


def keyed(*labels: str) -> Div:
    return Div(children=[labeled(label).with_key(label) for label in labels])


def ancestors(tree: LayoutTree, node: waxy.NodeId) -> list[waxy.NodeId]:
    parent = tree.tree.parent(node)
    return [] if parent is None else [parent, *ancestors(tree, parent)]


def nodes_by_text(tree: LayoutTree, shadow: ShadowTree) -> dict[str, waxy.NodeId]:
    return {
        node.element.content: tree.nodes[node.key]
        for node in shadow.nodes
        if isinstance(node.element, Text) and isinstance(node.element.content, str)
    }


def dirty_nodes(tree: LayoutTree) -> set[waxy.NodeId]:
    return {node for node in tree.nodes.values() if tree.tree.dirty(node)}


UNCHANGING = [
    panes("first pane", "second pane, which wraps onto more lines than the first"),
    canvas(["red", "green", "blue"]),
]


@pytest.mark.parametrize("element", UNCHANGING)
def test_frame_with_no_changes_has_no_layout_changes(element: AnyElement) -> None:
    previous = update_shadow(element, None, NO_LAYOUTS).tree

    assert layout_changes(previous, update_shadow(element, previous, NO_LAYOUTS).tree) == []


@pytest.mark.parametrize("element", UNCHANGING)
def test_frame_with_no_changes_dirties_no_node(element: AnyElement) -> None:
    tree = LayoutTree()
    shadow = frames(tree, [element])

    tree.apply(layout_changes(shadow, update_shadow(element, shadow, NO_LAYOUTS).tree))

    assert dirty_nodes(tree) == set()


def test_changed_text_is_one_set_text() -> None:
    previous = update_shadow(panes("alpha", "beta", "gamma"), None, NO_LAYOUTS).tree
    next = update_shadow(panes("alpha", "beta, longer now", "gamma"), previous, NO_LAYOUTS).tree

    [(changed, text)] = [
        (node, element)
        for node in next.nodes
        if isinstance(element := node.element, Text) and element.content == "beta, longer now"
    ]
    assert layout_changes(previous, next) == [SetText(key=changed.key, text=text_source(text))]


def test_reused_subtree_is_not_descended_into(mocker: MockerFixture) -> None:
    unchanging = panes("alpha", "beta")
    previous = update_shadow(Div(children=[Text(content="before"), unchanging]), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=[Text(content="after"), unchanging]), previous, NO_LAYOUTS).tree
    assert next.root.children[1] is previous.root.children[1]
    text_source = mocker.spy(layout, "text_source")

    layout_changes(previous, next)

    assert {call.args[0].content for call in text_source.call_args_list} == {"before", "after"}


def test_changed_text_dirties_only_itself_and_its_ancestors() -> None:
    tree = LayoutTree()
    shadow = frames(tree, [panes("alpha", "beta", "gamma")])
    next = update_shadow(panes("alpha", "beta, longer now", "gamma"), shadow, NO_LAYOUTS).tree

    tree.apply(layout_changes(shadow, next))

    changed = nodes_by_text(tree, next)["beta, longer now"]
    assert dirty_nodes(tree) == {changed, *ancestors(tree, changed)}


def test_changed_chunk_dirties_its_text() -> None:
    tree = LayoutTree()
    shadow = frames(tree, [canvas(["red", "green", "blue"])])
    next = update_shadow(canvas(["red", "yellow", "blue"]), shadow, NO_LAYOUTS).tree

    tree.apply(layout_changes(shadow, next))

    [canvas_node] = [
        tree.nodes[node.key]
        for node in next.nodes
        if isinstance(node.element, Text) and not isinstance(node.element.content, str)
    ]
    assert tree.tree.dirty(canvas_node)


def test_moved_keyed_child_is_one_set_children() -> None:
    previous = update_shadow(keyed("a", "b", "c"), None, NO_LAYOUTS).tree
    next = update_shadow(keyed("c", "a", "b"), previous, NO_LAYOUTS).tree

    assert layout_changes(previous, next) == [
        SetChildren(key=next.root.key, children=tuple(child.key for child in next.root.children))
    ]


def test_text_becoming_a_div_keeps_its_key() -> None:
    nested_text = Text(content="nested")
    previous = update_shadow(Div(children=[Text(content="leaf")]), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=[Div(children=[nested_text])]), previous, NO_LAYOUTS).tree

    [was_text], [now_div] = previous.root.children, next.root.children
    [nested] = now_div.children
    assert (now_div.key, layout_changes(previous, next)) == (
        was_text.key,
        [
            CreateLeaf(key=nested.key, style=layout_style(nested_text.style), text=text_source(nested_text)),
            ClearText(key=now_div.key),
            SetChildren(key=now_div.key, children=(nested.key,)),
        ],
    )


def test_unmounted_subtree_removes_every_node_in_it() -> None:
    previous = update_shadow(Div(children=[Text(content="sibling"), panes("deep", "deeper")]), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=[Text(content="sibling")]), previous, NO_LAYOUTS).tree

    removed = [change.key for change in layout_changes(previous, next) if isinstance(change, Remove)]

    assert sorted(removed) == sorted(node.key for node in previous.root.children[1].walk())


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
    "reorder keyed children": [keyed("a", "b", "c"), keyed("c", "a"), keyed("b", "c", "a")],
    "replace the root": [Text(content="root"), labeled("root"), panes("root")],
}


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_mounting_and_unmounting_leaves_no_orphaned_nodes(elements: list[AnyElement]) -> None:
    tree = LayoutTree()
    shadow = frames(tree, elements)

    assert tree.tree.total_node_count() == len(tree.nodes) == len(shadow.nodes)


def without_keys(layouts: Layouts) -> tuple[tuple[AnyElement, Rects], ...]:
    """Each element and its layout in paint order, without the node keys, which differ between two trees."""
    return tuple((element, layout) for _, element, layout in layouts.in_paint_order)


def fresh_layout(element: AnyElement) -> tuple[tuple[AnyElement, Rects], ...]:
    shadow = update_shadow(element, None, NO_LAYOUTS).tree
    return without_keys(LayoutTree().compute(layout_changes(None, shadow), shadow, AVAILABLE))


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_reused_tree_lays_out_each_frame_as_a_fresh_tree_does(elements: list[AnyElement]) -> None:
    tree = LayoutTree()
    shadow: ShadowTree | None = None
    for element in elements:
        next_shadow = update_shadow(element, shadow, NO_LAYOUTS).tree

        assert without_keys(tree.compute(layout_changes(shadow, next_shadow), next_shadow, AVAILABLE)) == fresh_layout(
            element
        )

        shadow = next_shadow


def test_text_is_not_wrapped_again_at_a_width_it_was_measured_at(mocker: MockerFixture) -> None:
    text = MeasurableText.of(("the quick brown fox", CellStyle(), "stable"))
    wrap_cells = mocker.spy(layout, "wrap_cells")

    _measure_text(waxy.KnownSize(width=10.0), waxy.AvailableSize(waxy.MaxContent(), waxy.MaxContent()), text)
    _measure_text(waxy.KnownSize(), waxy.AvailableSize(waxy.Definite(10), waxy.MaxContent()), text)
    _measure_text(waxy.KnownSize(height=3.0), waxy.AvailableSize(waxy.Definite(10), waxy.Definite(5)), text)

    assert wrap_cells.call_count == 1
