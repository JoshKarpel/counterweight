from counterweight import Inline
from counterweight import app
from counterweight._app import stale_readers
from counterweight._layout import NO_LAYOUTS
from counterweight._layout import Layouts
from counterweight._shadow import update_shadow
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.events import TerminalResized
from counterweight.focus import ElementHandle
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.styles.utilities import border
from counterweight.styles.utilities import col
from counterweight.styles.utilities import display_none
from counterweight.styles.utilities import margin
from counterweight.styles.utilities import overflow_hidden
from counterweight.styles.utilities import pad
from counterweight.styles.utilities import size

# Taking a screenshot lets the render loop run the frame that a state change before it queued.
SHOT = Screenshot(handler=lambda frame: None)
EMPTY = Region(left=0, top=0, right=0, bottom=0)
VISIBLE = Region(left=0, top=0, right=7, bottom=4)


@component
def measured(is_hidden: bool, recorded: list[Rects]) -> Div:
    recorded.append(use_rects())
    return Div(style=(size(7, 4) | display_none) if is_hidden else size(7, 4))


async def test_use_rects_reports_the_last_layout_and_empty_regions_once_hidden() -> None:
    recorded: list[Rects] = []

    @component
    def root() -> Div:
        is_hidden, set_is_hidden = use_state(False)

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_is_hidden(True)

        return Div(children=(measured(is_hidden, recorded),), on_input=on_input)

    await app(
        root(),
        headless=True,
        dimensions=(20, 10),
        autopilot=(KeyPressed(key="h"), Quit()),
    )

    # The warmup render, the first painted frame, the frame that hides it,
    # and the pass that frame re-renders it in once its layout changed, before painting.
    assert [rects.border for rects in recorded] == [EMPTY, VISIBLE, VISIBLE, EMPTY]


NESTED_BOXES = Rects(
    content=Region(left=3, top=3, right=8, bottom=6),
    padding=Region(left=2, top=2, right=9, bottom=7),
    border=Region(left=1, top=1, right=10, bottom=8),
    margin=Region(left=0, top=0, right=11, bottom=9),
    clip=Region(left=0, top=0, right=20, bottom=10),
    visible=Region(left=1, top=1, right=10, bottom=8),
    screen=Region(left=0, top=0, right=20, bottom=10),
)


async def test_use_rects_reports_each_box_and_the_purity_check_rereads_them() -> None:
    recorded: list[Rects] = []

    @component
    def boxed() -> Div:
        recorded.append(use_rects())
        return Div(style=margin(1) | border | pad(1) | size(9, 7))

    await app(boxed(), headless=True, dimensions=(20, 10), autopilot=(Quit(),), check_purity=True)

    # The painted frame's render, then the purity check's re-run of it.
    assert recorded[-2:] == [NESTED_BOXES, NESTED_BOXES]


async def test_a_component_that_mounts_after_the_first_frame_renders_again_once_its_rects_are_known() -> None:
    recorded: list[Rects] = []

    @component
    def root() -> Div:
        is_shown, set_is_shown = use_state(False)

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_is_shown(True)

        return Div(children=(measured(False, recorded),) if is_shown else (), on_input=on_input)

    await app(root(), headless=True, dimensions=(20, 10), autopilot=(KeyPressed(key="s"), SHOT, Quit()))

    # The render that mounts it, then the one its rects moving causes before that frame paints.
    assert [rects.border for rects in recorded] == [EMPTY, VISIBLE]


HANDLE = ElementHandle()
SIBLING = Region(left=0, top=1, right=7, bottom=5)


async def test_use_rects_with_a_handle_reports_the_rects_of_the_element_it_names() -> None:
    recorded: list[Rects] = []

    @component
    def beside() -> Div:
        recorded.append(use_rects(HANDLE))
        return Div(style=col, children=(Text(content="above"), Div(style=size(7, 4), handle=HANDLE)))

    await app(beside(), headless=True, dimensions=(20, 10), autopilot=(Quit(),))

    assert recorded[-1].border == SIBLING


async def test_use_rects_with_a_handle_on_no_mounted_element_reports_empty_regions() -> None:
    recorded: list[Rects] = []

    @component
    def unnamed() -> Div:
        recorded.append(use_rects(ElementHandle()))
        return Div(style=size(7, 4))

    await app(unnamed(), headless=True, dimensions=(20, 10), autopilot=(Quit(),))

    assert recorded[-1].border == EMPTY


async def test_a_component_reading_its_own_and_another_elements_rects_renders_again_once_either_moves() -> None:
    recorded: list[tuple[int, int]] = []

    @component
    def both() -> Div:
        own = use_rects()
        inner = use_rects(HANDLE)
        recorded.append((own.border.height, inner.border.height))
        grown, set_grown = use_state(False)

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_grown(True)

        return Div(
            style=col | size(7, 6),
            on_input=on_input,
            children=(Div(style=size(7, 4 if grown else 2), handle=HANDLE),),
        )

    await app(both(), headless=True, dimensions=(20, 10), autopilot=(KeyPressed(key="g"), SHOT, Quit()))

    assert recorded[-1] == (6, 4)


def test_stale_readers_are_the_nodes_whose_rects_moved() -> None:
    @component
    def reads() -> Div:
        use_rects(HANDLE)
        return Div()

    shadow = update_shadow(Div(children=(reads(), Div(handle=HANDLE))), None, NO_LAYOUTS).tree
    reader, named = shadow.root.children
    moved = Layouts(in_paint_order=(), by_key={named.key: NESTED_BOXES}, scrolls={}, handles={HANDLE: named.key})

    assert (list(stale_readers(shadow, NO_LAYOUTS)), list(stale_readers(shadow, moved))) == ([], [reader.key])


@component
def reads_the_screen(recorded: list[Region]) -> Div:
    recorded.append(use_rects().screen)
    return Div(style=size(3, 2))


async def test_screen_is_the_terminal_in_full_screen_and_empty_on_the_initial_render() -> None:
    recorded: list[Region] = []

    await app(reads_the_screen(recorded), headless=True, dimensions=(20, 10), autopilot=(Quit(),))

    assert (recorded[0], recorded[-1]) == (EMPTY, Region(left=0, top=0, right=20, bottom=10))


@component
def nests(*children: Component | AnyElement) -> Div:
    return Div(style=col, children=children)


@component
def clips(*children: Component) -> Div:
    return Div(style=size(10, 5) | overflow_hidden, children=children)


async def test_screen_is_the_region_inline() -> None:
    recorded: list[Region] = []

    await app(
        nests(reads_the_screen(recorded)),
        headless=True,
        dimensions=(20, 10),
        viewport=Inline(),
        autopilot=(Quit(),),
    )

    assert recorded[-1] == Region(left=0, top=0, right=20, bottom=2)


async def test_screen_is_the_same_for_an_element_at_any_depth() -> None:
    shallow: list[Region] = []
    deep: list[Region] = []

    await app(
        nests(
            reads_the_screen(shallow),
            Div(style=margin(1) | border | pad(1), children=(Div(style=pad(2), children=(reads_the_screen(deep),)),)),
        ),
        headless=True,
        dimensions=(20, 12),
        autopilot=(Quit(),),
    )

    assert deep[-1] == shallow[-1] == Region(left=0, top=0, right=20, bottom=12)


async def test_a_component_that_read_the_screen_renders_again_after_a_resize_that_moves_none_of_its_boxes() -> None:
    recorded: list[Region] = []

    # Inside a parent that clips it, so its clip doesn't change with the screen either.
    await app(
        clips(reads_the_screen(recorded)),
        headless=True,
        dimensions=(20, 10),
        autopilot=(TerminalResized(dimensions=(30, 12)), SHOT, Quit()),
    )

    assert recorded[-1] == Region(left=0, top=0, right=30, bottom=12)
