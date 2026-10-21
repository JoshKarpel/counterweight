from collections.abc import Sequence
from dataclasses import dataclass

import pytest
import waxy
from hypothesis import given
from hypothesis import strategies as st
from more_itertools import one
from pytest_mock import MockerFixture

from counterweight import _layout as layout
from counterweight._layout import NO_LAYOUTS
from counterweight._layout import ClearSource
from counterweight._layout import CreateLeaf
from counterweight._layout import IntrinsicSize
from counterweight._layout import Layouts
from counterweight._layout import LayoutTree
from counterweight._layout import MeasurableText
from counterweight._layout import Remove
from counterweight._layout import SetChildren
from counterweight._layout import SetSource
from counterweight._layout import _measure_leaf
from counterweight._layout import layout_changes
from counterweight._layout import layout_style
from counterweight._layout import text_source
from counterweight._shadow import ShadowTree
from counterweight._shadow import update_shadow
from counterweight.components import component
from counterweight.elements import AnyElement
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.elements import Text
from counterweight.geometry import Rects
from counterweight.hooks._impls import NodeKey
from counterweight.styles._styles import CellStyle
from counterweight.styles._styles import Color
from counterweight.styles._styles import Style
from counterweight.styles._styles import TextWrap
from counterweight.styles.utilities import border
from counterweight.styles.utilities import col
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import height
from counterweight.styles.utilities import overflow_hidden
from counterweight.styles.utilities import row
from counterweight.styles.utilities import text_wrap_stable
from tests.test_layout import Sides
from tests.test_layout import TextInBox
from tests.test_layout import borders
from tests.test_layout import box_sizings
from tests.test_layout import boxed
from tests.test_layout import paddings
from tests.test_layout import texts_in_boxes

WIDTH, HEIGHT = 40, 12


def frames(tree: LayoutTree, elements: Sequence[AnyElement]) -> ShadowTree:
    """Render each element as one frame through `tree`, and return the last frame's shadow tree."""
    shadow: ShadowTree | None = None
    for element in elements:
        next_shadow = update_shadow(element, shadow, NO_LAYOUTS).tree
        tree.compute(layout_changes(shadow, next_shadow), next_shadow, WIDTH, HEIGHT, {})
        shadow = next_shadow
    assert shadow is not None
    return shadow


def panes(*texts: str) -> Div:
    return Div(
        style=col,
        children=tuple(
            Div(style=row | border, children=(Text(content=text, style=fill(1) | text_wrap_stable),)) for text in texts
        ),
    )


def canvas(colors: Sequence[str]) -> Div:
    return Div(
        children=(
            Text(
                content=tuple(
                    Chunk(content="▀", style=CellStyle(foreground=Color.from_name(color))) for color in colors
                )
            ),
            Text(content="label"),
        )
    )


@dataclass(frozen=True, slots=True)
class Blocks:
    """A painter that fills whatever box it's given with `grapheme`."""

    grapheme: str = "#"
    natural_size: tuple[int, int] = (4, 2)
    keeps_aspect_ratio: bool = True

    def draw(self, width: int, height: int) -> Rows:
        return ((StyledGrapheme(grapheme=self.grapheme),) * width,) * height


@component
def labeled(label: str) -> Text:
    return Text(content=label)


def keyed(*labels: str) -> Div:
    return Div(children=tuple(labeled(label).with_key(label) for label in labels))


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
    assert layout_changes(previous, next) == [SetSource(key=changed.key, source=text_source(text))]


def test_reused_subtree_is_not_descended_into(mocker: MockerFixture) -> None:
    unchanging = panes("alpha", "beta")
    previous = update_shadow(Div(children=(Text(content="before"), unchanging)), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=(Text(content="after"), unchanging)), previous, NO_LAYOUTS).tree
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
    previous = update_shadow(Div(children=(Text(content="leaf"),)), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=(Div(children=(nested_text,)),)), previous, NO_LAYOUTS).tree

    [was_text], [now_div] = previous.root.children, next.root.children
    [nested] = now_div.children
    assert (now_div.key, layout_changes(previous, next)) == (
        was_text.key,
        [
            CreateLeaf(key=nested.key, style=layout_style(nested_text.style), source=text_source(nested_text)),
            ClearSource(key=now_div.key),
            SetChildren(key=now_div.key, children=(nested.key,)),
        ],
    )


def test_unmounted_subtree_removes_every_node_in_it() -> None:
    previous = update_shadow(Div(children=(Text(content="sibling"), panes("deep", "deeper"))), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=(Text(content="sibling"),)), previous, NO_LAYOUTS).tree

    removed = [change.key for change in layout_changes(previous, next) if isinstance(change, Remove)]

    assert sorted(removed) == sorted(node.key for node in previous.root.children[1].walk())


SEQUENCES = {
    "grow and shrink": [panes("a"), panes("a", "b", "c"), panes("a"), panes(), panes("a", "b")],
    "text becomes a div and back": [
        Div(children=(Text(content="leaf"),)),
        Div(children=(Div(style=border, children=(Text(content="nested"), Text(content="twice"))),)),
        Div(children=(Text(content="leaf again"),)),
    ],
    "text becomes an empty div": [
        Div(children=(Text(content="leaf"), Text(content="sibling"))),
        Div(children=(Div(), Text(content="sibling"))),
    ],
    "unmount a nested subtree": [
        Div(children=(panes("deep", "deeper"), Text(content="sibling"))),
        Div(children=(Text(content="sibling"),)),
    ],
    "reorder keyed children": [keyed("a", "b", "c"), keyed("c", "a"), keyed("b", "c", "a")],
    "replace the root": [Text(content="root"), labeled("root"), panes("root")],
    "an ancestor moves": [
        Div(style=col, children=(Text(content="above"), panes("moved"))),
        Div(style=col, children=(Text(content="above\nabove"), panes("moved"))),
    ],
    "text becomes a canvas and back": [
        Div(children=(Text(content="leaf"),)),
        Div(children=(Canvas(painter=Blocks()),)),
        Div(children=(Text(content="leaf again"),)),
    ],
    "canvas becomes a div and back": [
        Div(children=(Canvas(painter=Blocks()),)),
        Div(children=(Div(style=border, children=(Text(content="nested"),)),)),
        Div(children=(Canvas(painter=Blocks(grapheme="%")),)),
    ],
    "canvas changes its natural size": [
        Div(style=col, children=(Canvas(painter=Blocks()), Text(content="below"))),
        Div(style=col, children=(Canvas(painter=Blocks(natural_size=(6, 3))), Text(content="below"))),
        Div(style=col, children=(Canvas(painter=Blocks(natural_size=(6, 3), keeps_aspect_ratio=False)),)),
    ],
    "unmount a canvas": [
        Div(children=(Text(content="sibling"), Canvas(painter=Blocks()))),
        Div(children=(Text(content="sibling"),)),
    ],
    "a clip shrinks": [
        Div(style=col | overflow_hidden | height(6), children=(Text(content="a\nb\nc\nd"),)),
        Div(style=col | overflow_hidden | height(2), children=(Text(content="a\nb\nc\nd"),)),
    ],
}


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_mounting_and_unmounting_leaves_no_orphaned_nodes(elements: list[AnyElement]) -> None:
    tree = LayoutTree()
    shadow = frames(tree, elements)

    assert tree.tree.total_node_count() == len(tree.nodes) == len(shadow.nodes)


def without_keys(layouts: Layouts) -> tuple[tuple[AnyElement, Rects], ...]:
    """Each element and its layout in paint order, without the node keys, which differ between two trees."""
    return tuple((element, layout) for _, element, layout, _, _ in layouts.in_paint_order)


def fresh_layout(element: AnyElement) -> tuple[tuple[AnyElement, Rects], ...]:
    shadow = update_shadow(element, None, NO_LAYOUTS).tree
    return without_keys(LayoutTree().compute(layout_changes(None, shadow), shadow, WIDTH, HEIGHT, {}))


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_reused_tree_lays_out_each_frame_as_a_fresh_tree_does(elements: list[AnyElement]) -> None:
    assert laid_out_by_one_tree(elements) == [fresh_layout(element) for element in elements]


@given(st.lists(texts_in_boxes().map(TextInBox.element), min_size=2, max_size=4))
def test_reused_tree_lays_out_changing_text_as_a_fresh_tree_does(elements: list[AnyElement]) -> None:
    assert laid_out_by_one_tree(elements) == [fresh_layout(element) for element in elements]


def laid_out_by_one_tree(elements: Sequence[AnyElement]) -> list[tuple[tuple[AnyElement, Rects], ...]]:
    """Each of `elements` laid out in turn by one tree, which applies only what changed since the last, as frames are."""
    tree = LayoutTree()
    shadow: ShadowTree | None = None
    frames = []
    for element in elements:
        next_shadow = update_shadow(element, shadow, NO_LAYOUTS).tree
        frames.append(without_keys(tree.compute(layout_changes(shadow, next_shadow), next_shadow, WIDTH, HEIGHT, {})))
        shadow = next_shadow
    return frames


def test_text_is_not_wrapped_again_at_a_width_it_was_measured_at(mocker: MockerFixture) -> None:
    text = MeasurableText.of(("the quick brown fox", CellStyle(), "stable"))
    wrap_cells = mocker.spy(layout, "wrap_cells")

    _measure_leaf(waxy.KnownSize(width=12.0), waxy.AvailableSize(waxy.Definite(10), waxy.MaxContent()), text)
    _measure_leaf(waxy.KnownSize(), waxy.AvailableSize(waxy.Definite(10), waxy.MaxContent()), text)
    _measure_leaf(waxy.KnownSize(height=3.0), waxy.AvailableSize(waxy.Definite(10), waxy.Definite(5)), text)

    assert wrap_cells.call_count == 1


def test_node_that_did_not_move_keeps_its_rects_from_frame_to_frame() -> None:
    tree = LayoutTree()
    shadow = frames(tree, [panes("alpha", "beta")])
    before = dict(tree.placed)

    kept = []
    for _ in range(2):
        next = update_shadow(panes("alpha", "beta"), shadow, NO_LAYOUTS).tree
        layouts = tree.compute(layout_changes(shadow, next), next, WIDTH, HEIGHT, {})
        kept.append(all(layouts.by_key[key] is rects for key, (_, rects) in before.items()))
        shadow = next

    assert kept == [True, True]


def test_placements_are_kept_only_for_nodes_in_the_last_layout() -> None:
    tree = LayoutTree()

    shadow = frames(tree, [panes("a", "b", "c"), panes("a")])

    assert set(tree.placed) == {node.key for node in shadow.nodes}


def leaf_keys(shadow: ShadowTree, kind: type[Text | Canvas]) -> set[NodeKey]:
    return {node.key for node in shadow.nodes if isinstance(node.element, kind)}


@pytest.mark.parametrize("elements", SEQUENCES.values(), ids=SEQUENCES.keys())
def test_tree_keeps_texts_only_for_texts_and_drawings_only_for_canvases(elements: list[AnyElement]) -> None:
    tree = LayoutTree()
    shadow: ShadowTree | None = None

    kept = []
    for element in elements:
        next_shadow = update_shadow(element, shadow, NO_LAYOUTS).tree
        tree.compute(layout_changes(shadow, next_shadow), next_shadow, WIDTH, HEIGHT, {})
        kept.append(
            (set(tree.texts), set(tree.drawings)) == (leaf_keys(next_shadow, Text), leaf_keys(next_shadow, Canvas))
        )
        shadow = next_shadow

    assert kept == [True] * len(elements)


KEY = NodeKey(1)


def test_changed_text_builds_cells_only_for_the_pieces_it_does_not_share_with_its_last_version(
    mocker: MockerFixture,
) -> None:
    tree = LayoutTree()
    tree.apply([CreateLeaf(key=KEY, style=waxy.Style(), source=("kept\nbefore", CellStyle(), "stable"))])
    styled_cells = mocker.spy(layout, "styled_cells")

    tree.apply([SetSource(key=KEY, source=("kept\nafter", CellStyle(), "stable"))])

    assert [call.args for call in styled_cells.call_args_list] == [("after", CellStyle())]


def test_text_of_one_piece_keeps_its_cells_when_only_its_wrap_changes() -> None:
    chunks = (Chunk(content="one piece", style=CellStyle(foreground=Color.from_name("red"))),)
    tree = LayoutTree()
    tree.apply([CreateLeaf(key=KEY, style=waxy.Style(), source=(chunks, CellStyle(), "stable"))])
    before = tree.texts[KEY].cells

    tree.apply([SetSource(key=KEY, source=(chunks, CellStyle(), "pretty"))])

    assert tree.texts[KEY].cells is before


@pytest.mark.parametrize("wrap", ["stable", "balance", "pretty"])
def test_wrapping_text_at_zero_width_has_no_lines(wrap: TextWrap) -> None:
    text = MeasurableText.of(("two\nlines", CellStyle(), wrap))

    measured = _measure_leaf(waxy.KnownSize(width=0.0), waxy.AvailableSize(waxy.Definite(0), waxy.MaxContent()), text)

    assert (text.lines_at(0), measured) == ((), waxy.Size(0.0, 0.0))


def test_text_that_does_not_wrap_is_as_tall_as_its_lines_at_zero_width() -> None:
    text = MeasurableText.of(("two\nlines", CellStyle(), "none"))

    measured = _measure_leaf(waxy.KnownSize(width=0.0), waxy.AvailableSize(waxy.Definite(0), waxy.MaxContent()), text)

    assert measured == waxy.Size(0.0, 2.0)


def test_canvas_with_an_equal_painter_has_no_layout_changes() -> None:
    previous = update_shadow(Div(children=(Canvas(painter=Blocks()),)), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=(Canvas(painter=Blocks()),)), previous, NO_LAYOUTS).tree

    assert layout_changes(previous, next) == []


def test_canvas_with_another_painter_of_the_same_natural_size_has_no_layout_changes() -> None:
    previous = update_shadow(Div(children=(Canvas(painter=Blocks()),)), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=(Canvas(painter=Blocks(grapheme="%")),)), previous, NO_LAYOUTS).tree

    assert layout_changes(previous, next) == []


def test_canvas_whose_natural_size_changes_is_one_set_source() -> None:
    previous = update_shadow(Div(children=(Canvas(painter=Blocks()),)), None, NO_LAYOUTS).tree
    next = update_shadow(Div(children=(Canvas(painter=Blocks(natural_size=(6, 2))),)), previous, NO_LAYOUTS).tree

    [node] = next.root.children
    assert layout_changes(previous, next) == [
        SetSource(key=node.key, source=IntrinsicSize(width=6, height=2, keeps_aspect_ratio=True)),
    ]


@pytest.mark.parametrize(
    ("painter", "expected"),
    [
        (Blocks(natural_size=(6, 2)), True),
        (Blocks(natural_size=(6, 2), keeps_aspect_ratio=False), False),
        (Blocks(natural_size=(0, 2)), False),
        (Blocks(natural_size=(6, 0)), False),
        (Blocks(natural_size=(1, 1)), True),
    ],
    ids=["keeps its ratio", "doesn't keep its ratio", "no width", "no height", "one cell"],
)
def test_canvas_keeps_its_painters_aspect_ratio_only_if_it_has_one(painter: Blocks, expected: bool) -> None:
    assert IntrinsicSize.of(painter).keeps_aspect_ratio is expected


# Taffy gives a leaf its known size as a border box, and the available space as its content box where it knows it,
# so a known size wider than the available space has a padding and border as wide as the difference,
# and takes the size measured on an unknown axis as a content box.
@pytest.mark.parametrize(
    ("known", "available", "expected"),
    [
        (waxy.KnownSize(), (waxy.MaxContent(), waxy.MaxContent()), waxy.Size(6.0, 2.0)),
        (waxy.KnownSize(width=3.0), (waxy.Definite(3), waxy.MaxContent()), waxy.Size(3.0, 1.0)),
        (waxy.KnownSize(width=5.0), (waxy.Definite(3), waxy.MaxContent()), waxy.Size(5.0, 1.0)),
        (waxy.KnownSize(height=4.0), (waxy.MaxContent(), waxy.Definite(4)), waxy.Size(12.0, 4.0)),
        (waxy.KnownSize(height=6.0), (waxy.MaxContent(), waxy.Definite(4)), waxy.Size(12.0, 6.0)),
        (waxy.KnownSize(width=5.0, height=5.0), (waxy.Definite(3), waxy.Definite(3)), waxy.Size(5.0, 5.0)),
    ],
    ids=["neither", "width", "width with a border", "height", "height with a border", "both"],
)
def test_canvas_that_keeps_its_aspect_ratio_measures_the_unknown_axis_by_it(
    known: waxy.KnownSize,
    available: tuple[waxy.Definite | waxy.MaxContent, waxy.Definite | waxy.MaxContent],
    expected: waxy.Size,
) -> None:
    intrinsic = IntrinsicSize(width=6, height=2, keeps_aspect_ratio=True)

    assert _measure_leaf(known, waxy.AvailableSize(*available), intrinsic) == expected


@pytest.mark.parametrize(
    ("known", "expected"),
    [
        (waxy.KnownSize(), waxy.Size(6.0, 2.0)),
        (waxy.KnownSize(width=3.0), waxy.Size(3.0, 2.0)),
        (waxy.KnownSize(height=4.0), waxy.Size(6.0, 4.0)),
    ],
    ids=["neither", "width", "height"],
)
def test_canvas_that_does_not_keep_its_aspect_ratio_measures_the_unknown_axis_at_its_natural_size(
    known: waxy.KnownSize, expected: waxy.Size
) -> None:
    intrinsic = IntrinsicSize(width=6, height=2, keeps_aspect_ratio=False)

    assert _measure_leaf(known, waxy.AvailableSize(waxy.Definite(3), waxy.Definite(4)), intrinsic) == expected


@given(
    natural_size=st.tuples(st.integers(1, 8), st.integers(1, 8)),
    borders=borders,
    paddings=paddings,
    box_sizing=box_sizings,
    width=st.integers(1, 30),
    is_stretched=st.booleans(),
)
def test_canvas_content_box_keeps_its_aspect_ratio_whatever_its_border_and_padding(
    natural_size: tuple[int, int],
    borders: Sides,
    paddings: Sides,
    box_sizing: waxy.BoxSizing,
    width: int,
    is_stretched: bool,
) -> None:
    canvas_width = waxy.Auto() if is_stretched else waxy.Length(width)
    canvas = Canvas(
        painter=Blocks(natural_size=natural_size),
        style=Style(layout=boxed(borders, paddings, box_sizing, canvas_width)),
    )
    parent_width = waxy.Length(width if is_stretched else WIDTH)
    element = Div(style=col | Style(layout=waxy.Style(size_width=parent_width)), children=(canvas,))

    content = one(rects.content for laid_out, rects in fresh_layout(element) if laid_out is canvas)

    natural_width, natural_height = natural_size
    assert abs(content.height - content.width * natural_height / natural_width) < 1
