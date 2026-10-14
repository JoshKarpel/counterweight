from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest
import waxy

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import InputEvent, InputHandler, InputResponse, MouseDown, Receiver
from counterweight.geometry import Position, Rects, Region
from counterweight.layout import child_clip
from counterweight.output import Frame
from counterweight.paint import BLANK, Cell, Paint, paint_layout
from counterweight.styles import Style
from counterweight.styles.styles import CellStyle, JoinedBorderKind, resolve_cell_style
from counterweight.styles.utilities import (
    border,
    border_double,
    border_light,
    border_y,
    clip_to_border,
    clip_to_padding,
    clip_to_screen,
    col,
    fill,
    height,
    inset_left,
    inset_top,
    overflow_clip,
    overflow_hidden,
    overflow_visible,
    overflow_x_hidden,
    overflow_y_hidden,
    pad_x,
    position_absolute,
    row,
    size,
    width,
    z,
)


async def frame_of(root: AnyElement, dimensions: tuple[int, int], events: Sequence[InputEvent] = ()) -> Frame:
    frames: list[Frame] = []

    @component
    def screen() -> AnyElement:
        return root

    await app(
        screen(),
        headless=True,
        dimensions=dimensions,
        autopilot=[*events, Screenshot(handler=frames.append), Quit()],
        check_purity=True,
    )
    return frames[0]


async def rows_of(root: AnyElement, dimensions: tuple[int, int]) -> list[str]:
    """Each row of the painted screen, with healing applied, as the app paints it."""
    return (await frame_of(root, dimensions)).text(ansi=False).split("\n")


def tall_box(overflow: Style) -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=col | border | height(4) | width(8) | overflow,
                children=tuple(Text(content=f"line {i}") for i in range(6)),
            ),
            Text(content="below"),
        ),
    )


async def test_hidden_overflow_paints_children_within_the_border_and_leaves_what_follows_intact() -> None:
    assert await rows_of(tall_box(overflow_hidden), (8, 6)) == [
        "┌──────┐",
        "│line 0│",
        "│line 1│",
        "└──────┘",
        "below   ",
        "        ",
    ]


async def test_visible_overflow_paints_past_the_border() -> None:
    assert await rows_of(tall_box(overflow_visible), (8, 6)) == [
        "┌──────┐",
        "│line 0│",
        "│line 1│",
        "└line 2┘",
        "below   ",
        " line 4 ",
    ]


async def test_clip_overflow_clips_as_hidden_does() -> None:
    assert await rows_of(tall_box(overflow_clip), (8, 6)) == await rows_of(tall_box(overflow_hidden), (8, 6))


WIDE_AND_TALL = Text(content="abcdef\nghijkl\nmnopqr", style=size(6, 3))


@pytest.mark.parametrize(
    ("overflow", "expected"),
    [
        (overflow_x_hidden, ["┌──┐  ", "│ab│  ", "│gh│  ", "└mn┘  "]),
        (overflow_y_hidden, ["┌──┐  ", "│abcdef", "│ghijkl", "└──┘  "]),
    ],
    ids=["x", "y"],
)
async def test_clipping_one_axis_leaves_the_other_unbounded(overflow: Style, expected: list[str]) -> None:
    rows = await rows_of(Div(style=border | size(4, 4) | overflow, children=(WIDE_AND_TALL,)), (6, 4))

    assert rows == [line[:6].ljust(6) for line in expected]


@pytest.mark.parametrize(
    ("overflow", "inset", "expected"),
    [
        (overflow_y_hidden, inset_left(-1), ["┌──┐  ", "abcdef", "ghijkl", "└──┘  "]),
        (overflow_x_hidden, inset_top(-1), ["┌ab┐  ", "│gh│  ", "│mn│  ", "└──┘  "]),
    ],
    ids=["y", "x"],
)
async def test_clipping_one_axis_leaves_the_start_of_the_other_unbounded(
    overflow: Style, inset: Style, expected: list[str]
) -> None:
    text = Text(content="abcdef\nghijkl\nmnopqr", style=position_absolute | inset | size(6, 3))
    rows = await rows_of(Div(style=border | size(4, 4) | overflow, children=(text,)), (6, 4))

    assert rows == expected


async def test_nested_clipping_containers_clip_to_the_intersection_of_their_padding_boxes() -> None:
    inner = Div(style=position_absolute | inset_left(2) | size(6, 3) | overflow_hidden, children=(WIDE_AND_TALL,))
    outer = Div(style=size(4, 2) | overflow_hidden, children=(inner,))

    assert await rows_of(outer, (8, 3)) == ["  ab    ", "  gh    ", "        "]


async def test_a_raised_descendant_of_a_clipping_container_is_still_clipped() -> None:
    menu = Text(content="menu", style=z(1) | position_absolute | inset_top(1) | inset_left(0))
    root = Div(
        style=col,
        children=(Div(style=size(6, 1) | overflow_hidden, children=(menu,)), Text(content="abcdef")),
    )

    assert await rows_of(root, (6, 2)) == ["      ", "abcdef"]


async def test_a_wide_cluster_straddling_a_clip_edge_leaves_a_space_on_the_visible_side() -> None:
    text = Text(content="日bc日", style=position_absolute | inset_left(-1))
    clipped = Div(style=position_absolute | inset_left(1) | size(4, 1) | overflow_hidden, children=(text,))

    paint = (await frame_of(Div(children=(clipped,)), (6, 1))).paint

    assert [cell.grapheme for cell in paint.rows().__next__()] == [" ", " ", "b", "c", " ", " "]
    assert paint[0, 0] == BLANK


@pytest.mark.parametrize(
    ("clip_to", "expected"),
    [(clip_to_padding, "┌─────┐"), (clip_to_border, "┌title┐")],
    ids=["padding", "border"],
)
async def test_a_title_on_the_border_of_a_fill_box_paints_only_when_it_clips_to_the_border(
    clip_to: Style, expected: str
) -> None:
    title = Text(content="title", style=position_absolute | inset_top(-1) | inset_left(0) | clip_to)
    root = Div(style=row, children=(Div(style=fill(1) | border, children=(title,)),))

    assert (await rows_of(root, (7, 3)))[0] == expected


async def test_a_child_clipped_to_the_border_box_is_still_cut_off_at_its_outer_edge() -> None:
    title = Text(content="long title", style=position_absolute | inset_top(-1) | inset_left(0) | clip_to_border)
    root = Div(style=row, children=(Div(style=fill(1) | border, children=(title,)), Text(content="x")))

    assert (await rows_of(root, (8, 3)))[0] == "┌long tx"


async def test_the_children_of_a_clipping_element_clipped_away_entirely_are_clipped_away_too() -> None:
    hidden_away = Div(
        style=position_absolute | inset_left(5) | size(2, 1) | overflow_hidden,
        children=(Div(style=size(2, 1) | overflow_hidden, children=(Text(content="x"),)),),
    )
    root = Div(style=size(4, 2) | overflow_hidden, children=(hidden_away,))

    assert await rows_of(root, (8, 2)) == ["        ", "        "]


SCREEN = Region(left=0, top=0, right=8, bottom=2)


def test_a_child_clip_is_none_when_the_parents_box_is_outside_the_clip() -> None:
    parent = rects(Region(left=5, top=0, right=8, bottom=2), clip=Region(left=0, top=0, right=4, bottom=2))

    assert child_clip(Region(left=0, top=0, right=4, bottom=2), SCREEN, parent, "padding", True, True) is None


@pytest.mark.parametrize("clip", [Region(left=1, top=0, right=3, bottom=1), None], ids=["clipped", "clipped-away"])
def test_an_unclipped_childs_clip_is_the_screen_whatever_its_parents_clip(clip: Region | None) -> None:
    parent = rects(Region(left=5, top=0, right=8, bottom=2), clip=Region(left=0, top=0, right=4, bottom=2))

    assert child_clip(clip, SCREEN, parent, "screen", True, True) is SCREEN


def popup(*children: AnyElement, style: Style = Style()) -> Div:
    """A raised, unclipped box, one row below the top of its parent and two cells right of its left edge."""
    return Div(
        style=z(1) | position_absolute | inset_top(1) | inset_left(2) | clip_to_screen | style,
        children=children or (Text(content="popup"),),
    )


def nested_clips(child: AnyElement) -> Div:
    """`child` inside two nested boxes that hide their overflow, one row tall, above two rows of text."""
    return Div(
        style=col,
        children=(
            Div(
                style=size(6, 1) | overflow_hidden,
                children=(Div(style=size(4, 1) | overflow_hidden, children=(child,)),),
            ),
            Text(content="abcdefgh"),
            Text(content="ijklmnop"),
        ),
    )


@pytest.mark.parametrize(
    "parent",
    [lambda child: child, lambda child: Div(children=(child,))],
    ids=["in-a-clipping-parent", "in-a-parent-that-does-not-clip"],
)
async def test_an_unclipped_element_escapes_every_ancestors_clip(parent: Callable[[AnyElement], AnyElement]) -> None:
    assert await rows_of(nested_clips(parent(popup())), (8, 3)) == ["        ", "abpopuph", "ijklmnop"]


async def test_an_unclipped_element_escapes_an_ancestor_clipped_away_entirely() -> None:
    hidden_away = Div(style=position_absolute | inset_left(5) | size(2, 1) | overflow_hidden, children=(popup(),))
    root = Div(style=size(4, 1) | overflow_hidden, children=(hidden_away,))

    assert await rows_of(root, (12, 2)) == ["            ", "       popup"]


async def test_an_unclipped_elements_own_overflow_still_clips_its_descendants() -> None:
    clipping_popup = popup(Text(content="popup"), style=size(3, 1) | overflow_hidden)

    assert await rows_of(nested_clips(clipping_popup), (8, 3)) == ["        ", "abpopfgh", "ijklmnop"]


async def test_an_unclipped_element_is_covered_by_a_later_sibling_of_its_ancestor_with_a_higher_z() -> None:
    cover = Text(content="COVER", style=z(2) | position_absolute | inset_top(1) | inset_left(3))
    root = Div(style=col, children=(nested_clips(popup()), cover))

    assert await rows_of(root, (8, 3)) == ["        ", "abpCOVER", "ijklmnop"]


async def test_an_unclipped_element_receives_the_mouse_outside_its_ancestors_clips() -> None:
    presses: list[str] = []
    target = Div(style=size(5, 1), on_input=clicks_on("popup", presses))
    root = Div(on_input=clicks_on("root", presses), children=(nested_clips(popup(target)),))

    await frame_of(root, (8, 3), events=[MouseDown(absolute=Position(5, 1), button=1)])

    assert presses == ["popup"]


async def test_a_border_clipped_by_an_ancestor_leaves_no_healing_hint_behind() -> None:
    child = Div(style=border | border_light | position_absolute | inset_top(-1) | inset_left(-1) | size(4, 3))
    root = Div(style=border | border_light | size(6, 4) | overflow_hidden, children=(child,))

    assert await rows_of(root, (6, 4)) == [
        "┌────┐",
        "│  │ │",
        "│──┘ │",
        "└────┘",
    ]


async def test_a_border_flush_against_its_containers_padding_box_does_not_join_the_containers_border() -> None:
    child = Div(style=border | border_light | size(4, 2))
    root = Div(style=border | border_light | size(6, 4) | overflow_hidden, children=(child,))

    assert await rows_of(root, (6, 4)) == [
        "┌────┐",
        "│┌──┐│",
        "│└──┘│",
        "└────┘",
    ]


async def test_collapsed_borders_of_clipping_items_still_heal_across_their_edges() -> None:
    cell = Style(layout=waxy.Style(gap_width=waxy.Length(-1))) | row
    root = Div(
        style=cell | size(5, 3),
        children=(Div(style=fill(1) | border | border_light), Div(style=fill(1) | border | border_light)),
    )

    assert await rows_of(root, (5, 3)) == ["┌─┬─┐", "│ │ │", "└─┴─┘"]


LIGHT = JoinedBorderKind.Light.value
CORNER = Position(2, 0)


def rects(border_box: Region, clip: Region) -> Rects:
    """The rects of an element whose border box is `border_box`, with a border of 1 and no margin or padding."""
    inner = Region(
        left=border_box.left + 1, top=border_box.top + 1, right=border_box.right - 1, bottom=border_box.bottom - 1
    )
    return Rects(
        content=inner,
        padding=inner,
        border=border_box,
        margin=border_box,
        clip=clip,
        visible=border_box.intersection(clip),
    )


def test_a_clipped_healing_hint_does_not_displace_an_earlier_elements_live_hint_at_the_same_cell() -> None:
    screen = Region(left=0, top=0, right=6, bottom=3)
    earlier = (Div(style=border | border_light), rects(Region(left=2, top=0, right=5, bottom=3), clip=screen))
    later = (
        Div(style=border | border_double),
        rects(Region(left=2, top=0, right=6, bottom=3), clip=Region(left=3, top=0, right=6, bottom=3)),
    )

    _, hints = paint_layout([earlier, later], 6, 3)

    assert hints[CORNER] == LIGHT


def test_fill_writes_only_inside_its_clip() -> None:
    paint = Paint.blank(4, 3)
    x = Cell("x", resolve_cell_style(CellStyle()))

    paint.fill(Region(left=0, top=0, right=4, bottom=3), x, Region(left=1, top=1, right=3, bottom=2))

    assert ["".join("." if cell == BLANK else cell.grapheme for cell in row) for row in paint.rows()] == [
        "....",
        ".xx.",
        "....",
    ]


@pytest.mark.parametrize(("y", "expected"), [(0, "...."), (1, ".xx."), (2, "....")], ids=["above", "inside", "below"])
def test_write_row_writes_only_inside_its_clip(y: int, expected: str) -> None:
    paint = Paint.blank(4, 3)
    x = Cell("x", resolve_cell_style(CellStyle()))

    paint.write_row(0, y, (x, x, x, x), Region(left=1, top=1, right=3, bottom=2))

    assert "".join("." if cell == BLANK else cell.grapheme for cell in list(paint.rows())[y]) == expected


def clicks_on(name: str, clicks: list[str]) -> InputHandler:
    """A handler that records `name` for every event it receives and claims it."""

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        clicks.append(name)
        return ()

    return handler


@pytest.mark.parametrize(
    ("x", "expected"),
    [(1, "beside"), (4, "overflowing")],
    ids=["over-the-clipped-off-part", "over-the-visible-part"],
)
async def test_the_mouse_targets_the_element_painted_where_it_is(x: int, expected: str) -> None:
    presses: list[str] = []
    # Later in paint order than the element beside it, so only its clip keeps it from taking the press there.
    overflowing = Div(style=position_absolute | inset_left(-3) | size(6, 1), on_input=clicks_on("overflowing", presses))
    root = Div(
        style=row,
        children=(
            Div(style=size(3, 1), on_input=clicks_on("beside", presses)),
            Div(style=size(3, 1) | overflow_hidden, children=(overflowing,)),
        ),
    )

    await frame_of(root, (6, 1), events=[MouseDown(absolute=Position(x, 0), button=1)])

    assert presses == [expected]


SCROLLING = Style(
    layout=waxy.Style(overflow_y=waxy.Overflow.Scroll, scrollbar_width=2, flex_direction=waxy.FlexDirection.Column)
)


async def test_a_scroll_containers_padding_and_content_exclude_the_space_its_scrollbar_width_reserves() -> None:
    recorded: list[Rects] = []

    def record(event: InputEvent, receiver: Receiver) -> InputResponse:
        recorded.append(receiver.rects)
        return ()

    container = Div(
        style=SCROLLING | border | pad_x(3) | size(20, 6),
        on_input=record,
        children=tuple(Text(content=f"{i}") for i in range(10)),
    )

    await frame_of(Div(children=(container,)), (20, 6), events=[MouseDown(absolute=Position(5, 2), button=1)])

    (rects_seen,) = recorded
    assert (rects_seen.padding, rects_seen.content) == (
        Region(left=1, top=1, right=17, bottom=5),
        Region(left=4, top=1, right=14, bottom=5),
    )


async def test_the_space_a_scrollbar_width_reserves_beside_no_border_draws_no_border_side() -> None:
    container = Div(style=SCROLLING | border_y | border_light | size(5, 3), children=(Text(content="ab"),))

    assert await rows_of(Div(children=(container,)), (5, 3)) == ["─────", "ab   ", "─────"]
