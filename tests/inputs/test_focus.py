from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from counterweight import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import ClearFocus
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import FocusPrevious
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.focus import DuplicateFocusHandle
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.focus import UnsettledFocus
from counterweight.geometry import Position
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import tab_focus
from counterweight.hooks import ChangedFocusHandle
from counterweight.hooks import DuplicateUseFocus
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.styles import Style
from counterweight.styles.utilities import col
from counterweight.styles.utilities import default
from counterweight.styles.utilities import display_none
from counterweight.styles.utilities import inset_left
from counterweight.styles.utilities import inset_top
from counterweight.styles.utilities import position_absolute
from counterweight.styles.utilities import size

PROBE = KeyPressed(key="?")
TOGGLE = KeyPressed(key="t")
TAB = KeyPressed(key=Key.Tab)
BACK_TAB = KeyPressed(key=Key.BackTab)


@dataclass(frozen=True, slots=True)
class Delivery:
    name: str
    event: InputEvent
    is_target: bool
    is_focused: bool


def recording(name: str, deliveries: list[Delivery], response: InputResponse = None) -> InputHandler:
    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        deliveries.append(
            Delivery(name=name, event=event, is_target=receiver.is_target, is_focused=receiver.is_focused)
        )
        return response

    return handler


def probed(deliveries: Sequence[Delivery]) -> list[str]:
    """The target of each `PROBE` key, which is the focused component, or the root when nothing is focused."""
    return [delivery.name for delivery in deliveries if delivery.event == PROBE and delivery.is_target]


def box(x: int, y: int, w: int, h: int) -> Style:
    return position_absolute | inset_left(x) | inset_top(y) | size(w, h)


def press(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


async def run(root: Component, autopilot: Sequence[InputEvent | AnyControl]) -> None:
    await app(root, headless=True, dimensions=(20, 10), autopilot=(*autopilot, Quit()), check_purity=True)


@component
def focusable(
    name: str,
    deliveries: list[Delivery],
    style: Style = default,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
    response: InputResponse = None,
    on_press: InputHandler | None = None,
    children: tuple[Component | AnyElement, ...] = (),
) -> Div:
    use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    handler = recording(name, deliveries, response)
    return Div(style=style, on_input=handler if on_press is None else first(handler, on_press), children=children)


def rooted(
    deliveries: list[Delivery],
    children: Callable[[bool], Sequence[Component | AnyElement]],
    on_input: InputHandler | None = None,
    toggled: InputResponse = (),
) -> Component:
    """
    A root that records what reaches it, toggles a flag on `TOGGLE`, responding with `toggled`,
    and renders `children(flag)`.
    `on_input` handles what the root doesn't.
    """

    @component
    def root() -> Div:
        flag, set_flag = use_state(False)

        def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
            deliveries.append(
                Delivery(name="root", event=event, is_target=receiver.is_target, is_focused=receiver.is_focused)
            )
            if event == TOGGLE:
                set_flag(not flag)
                return toggled
            return None if on_input is None else on_input(event, receiver)

        return Div(style=size(20, 10), on_input=handler, children=tuple(children(flag)))

    return root()


def three(deliveries: list[Delivery], **kwargs: object) -> Callable[[bool], Sequence[Component]]:
    """Three focusables, `a`, `b` and `c` in tree order, with `kwargs` passed to `b`."""
    return lambda _: [
        focusable("a", deliveries),
        focusable("b", deliveries, **kwargs),  # type: ignore[arg-type]
        focusable("c", deliveries),
    ]


# Routing keys


async def test_with_nothing_focused_only_the_root_receives_a_key_as_its_unfocused_target() -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, lambda _: [Div(on_input=recording("plain", deliveries))]), [PROBE])

    assert deliveries == [Delivery(name="root", event=PROBE, is_target=True, is_focused=False)]


async def test_a_key_reaches_the_focused_node_then_its_ancestors_and_not_its_siblings() -> None:
    deliveries: list[Delivery] = []

    @component
    def group() -> Div:
        return Div(
            on_input=recording("group", deliveries),
            children=(focusable("focused", deliveries, auto_focus=True),),
        )

    await run(rooted(deliveries, lambda _: [group(), focusable("sibling", deliveries)]), [PROBE])

    assert deliveries == [
        Delivery(name="focused", event=PROBE, is_target=True, is_focused=True),
        Delivery(name="group", event=PROBE, is_target=False, is_focused=False),
        Delivery(name="root", event=PROBE, is_target=False, is_focused=False),
    ]


async def test_a_key_stops_at_the_focused_node_when_it_handles_it() -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, lambda _: [focusable("focused", deliveries, auto_focus=True, response=())]), [PROBE])

    assert [delivery.name for delivery in deliveries] == ["focused"]


async def test_a_receiver_carries_its_components_focus_handle_or_none() -> None:
    handle = FocusHandle()
    received: list[tuple[str, FocusHandle | None]] = []

    def receiving(name: str) -> InputHandler:
        return lambda _, receiver: received.append((name, receiver.focus_handle))

    @component
    def focused_box() -> Div:
        use_focus(handle=handle)
        return Div(
            style=box(0, 0, 10, 10), on_input=receiving("focusable"), children=(Div(on_input=receiving("inner")),)
        )

    @component
    def root() -> Div:
        return Div(style=size(20, 10), on_input=receiving("root"), children=(focused_box(),))

    await run(root(), [MouseScrolledDown(absolute=Position(1, 1))])

    assert received == [("focusable", handle), ("root", None)]


async def test_a_click_on_the_focused_element_carries_is_focused() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, lambda _: [focusable("focused", deliveries, style=box(0, 0, 5, 5), auto_focus=True)]),
        [MouseScrolledDown(absolute=Position(1, 1))],
    )

    assert [(delivery.name, delivery.is_focused) for delivery in deliveries] == [("focused", True), ("root", False)]


async def test_each_event_of_a_press_and_a_move_after_it_reaches_the_focused_element_as_focused() -> None:
    deliveries: list[Delivery] = []
    events: list[InputEvent] = [
        MouseDown(absolute=Position(1, 1), button=1),
        MouseDown(absolute=Position(2, 1), button=3),
        MouseMoved(absolute=Position(2, 2), button=1),
        MouseUp(absolute=Position(2, 2), button=3),
        MouseUp(absolute=Position(3, 2), button=1),
        MouseMoved(absolute=Position(3, 3), button=None),
    ]

    await run(
        rooted(
            deliveries,
            lambda _: [focusable("focused", deliveries, style=box(0, 0, 5, 5), auto_focus=True, response=())],
        ),
        events,
    )

    assert deliveries == [Delivery(name="focused", event=event, is_target=True, is_focused=True) for event in events]


# Moving focus


async def test_focus_next_focuses_the_first_in_tree_order_and_wraps_from_the_last() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, three(deliveries)),
        [FocusNext(), PROBE, FocusNext(), PROBE, FocusNext(), PROBE, FocusNext(), PROBE],
    )

    assert probed(deliveries) == ["a", "b", "c", "a"]


async def test_focus_previous_focuses_the_last_in_tree_order_and_moves_backwards() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, three(deliveries)),
        [FocusPrevious(), PROBE, FocusPrevious(), PROBE, FocusPrevious(), PROBE, FocusPrevious(), PROBE],
    )

    assert probed(deliveries) == ["c", "b", "a", "c"]


async def test_focus_next_skips_a_focusable_in_a_hidden_subtree() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(
            deliveries,
            lambda _: [
                focusable("a", deliveries),
                Div(style=display_none, children=(focusable("hidden", deliveries),)),
                focusable("c", deliveries),
            ],
        ),
        [FocusNext(), FocusNext(), PROBE],
    )

    assert probed(deliveries) == ["c"]


async def test_focus_next_focuses_a_component_that_mounted_in_the_last_render() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, lambda is_mounted: [focusable("late", deliveries)] if is_mounted else []),
        [TOGGLE, FocusNext(), PROBE],
    )

    assert probed(deliveries) == ["late"]


async def test_focus_on_focuses_its_component_and_does_nothing_once_it_has_unmounted() -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    def children(is_unmounted: bool) -> Sequence[Component]:
        return [focusable("named", deliveries, handle=handle)] if not is_unmounted else []

    await run(rooted(deliveries, children), [FocusOn(handle), PROBE, TOGGLE, FocusOn(handle), PROBE])

    assert probed(deliveries) == ["named", "root"]


def mounts_late(deliveries: list[Delivery], handle: FocusHandle) -> Callable[[bool], Sequence[Component]]:
    """A focused component `a`, then `late`, with `handle`, once the flag is set."""
    return lambda is_mounted: [
        focusable("a", deliveries, auto_focus=True),
        *([focusable("late", deliveries, handle=handle)] if is_mounted else []),
    ]


async def test_focus_on_focuses_a_component_that_mounts_in_the_render_its_handler_causes() -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    await run(rooted(deliveries, mounts_late(deliveries, handle), toggled=FocusOn(handle)), [TOGGLE, PROBE])

    assert probed(deliveries) == ["late"]


async def test_a_focus_control_after_a_waiting_focus_on_wins() -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    await run(
        rooted(deliveries, mounts_late(deliveries, handle), toggled=(FocusOn(handle), ClearFocus())), [TOGGLE, PROBE]
    )

    assert probed(deliveries) == ["root"]


async def test_a_waiting_focus_on_wins_over_a_focus_control_before_it() -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    await run(
        rooted(deliveries, mounts_late(deliveries, handle), toggled=(ClearFocus(), FocusOn(handle))), [TOGGLE, PROBE]
    )

    assert probed(deliveries) == ["late"]


async def test_a_focus_on_that_waits_for_a_render_that_never_comes_does_not_focus_a_later_mount() -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    await run(rooted(deliveries, mounts_late(deliveries, handle)), [FocusOn(handle), PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["a", "a"]


async def test_a_focus_on_for_a_component_that_does_not_mount_leaves_focus_where_it_is() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, mounts_late(deliveries, FocusHandle()), toggled=FocusOn(FocusHandle())), [TOGGLE, PROBE]
    )

    assert probed(deliveries) == ["a"]


async def test_clear_focus_sends_keys_to_the_root() -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, three(deliveries)), [FocusNext(), ClearFocus(), PROBE])

    assert probed(deliveries) == ["root"]


async def test_auto_focus_takes_focus_only_when_nothing_is_focused_and_the_first_in_tree_order_wins() -> None:
    deliveries: list[Delivery] = []

    def children(is_late_shown: bool) -> Sequence[Component]:
        return [
            focusable("a", deliveries),
            focusable("first", deliveries, auto_focus=True),
            focusable("second", deliveries, auto_focus=True),
            *([focusable("late", deliveries, auto_focus=True)] if is_late_shown else []),
        ]

    await run(rooted(deliveries, children), [PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["first", "first"]


BODY = FocusHandle()


def body(deliveries: list[Delivery], in_focus_order: bool, is_late_shown: bool) -> Component:
    """A focusable component holding, once `is_late_shown`, one that mounts with `auto_focus`."""
    late = (focusable("late", deliveries, auto_focus=True),) if is_late_shown else ()
    return focusable("body", deliveries, handle=BODY, in_focus_order=in_focus_order, children=late)


@pytest.mark.parametrize(("in_focus_order", "expected"), [(False, ["body", "late"]), (True, ["body", "body"])])
async def test_auto_focus_takes_focus_from_a_focused_component_it_mounts_inside_only_if_tab_never_stops_there(
    in_focus_order: bool, expected: list[str]
) -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, lambda shown: [body(deliveries, in_focus_order, shown)]),
        [FocusOn(BODY), PROBE, TOGGLE, PROBE],
    )

    assert probed(deliveries) == expected


async def test_auto_focus_leaves_focus_on_a_component_out_of_the_focus_order_that_it_mounts_beside() -> None:
    deliveries: list[Delivery] = []

    def children(is_late_shown: bool) -> Sequence[Component]:
        late = [focusable("late", deliveries, auto_focus=True)] if is_late_shown else []
        return [body(deliveries, in_focus_order=False, is_late_shown=False), *late]

    await run(rooted(deliveries, children), [FocusOn(BODY), PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["body", "body"]


async def test_focusing_a_component_out_of_the_focus_order_as_it_mounts_focuses_an_auto_focus_one_inside_it() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(
            deliveries,
            lambda shown: [body(deliveries, in_focus_order=False, is_late_shown=True)] if shown else [],
            toggled=FocusOn(BODY),
        ),
        [TOGGLE, PROBE],
    )

    assert probed(deliveries) == ["late"]


async def test_use_focus_with_no_arguments_does_not_take_focus() -> None:
    deliveries: list[Delivery] = []

    @component
    def plain() -> Div:
        use_focus()
        return Div(on_input=recording("plain", deliveries))

    await run(rooted(deliveries, lambda _: [plain()]), [PROBE])

    assert probed(deliveries) == ["root"]


@component
def focus_label(name: str, auto_focus: bool = False, handle: FocusHandle | None = None) -> Text:
    focus = use_focus(auto_focus=auto_focus, handle=handle)
    return Text(content=f"{name}:{'on' if focus.is_focused else 'off'}")


def labels(*names: str, auto_focus: str | None = None) -> Component:
    @component
    def root() -> Div:
        return Div(style=col, children=tuple(focus_label(name, auto_focus=name == auto_focus) for name in names))

    return root()


def lines(frames: Sequence[Frame]) -> list[list[str]]:
    return [[line.strip() for line in frame.text(ansi=False).splitlines() if line.strip()] for frame in frames]


async def test_an_auto_focus_component_present_at_startup_is_focused_on_the_first_frame() -> None:
    frames: list[Frame] = []

    await run(labels("a", "b", auto_focus="b"), [Screenshot(handler=frames.append)])

    assert lines(frames) == [["a:off", "b:on"]]


async def test_a_focus_change_re_renders_so_is_focused_is_current() -> None:
    frames: list[Frame] = []

    await run(
        labels("a", "b", auto_focus="a"),
        [FocusNext(), Screenshot(handler=frames.append), ClearFocus(), Screenshot(handler=frames.append)],
    )

    assert lines(frames) == [["a:off", "b:on"], ["a:off", "b:off"]]


async def test_an_auto_focus_component_that_mounts_later_is_focused_in_the_first_frame_that_shows_it() -> None:
    frames: list[Frame] = []

    await run(
        rooted([], lambda is_mounted: [focus_label("late", auto_focus=True)] if is_mounted else []),
        [TOGGLE, Screenshot(handler=frames.append)],
    )

    assert lines(frames) == [["late:on"]]


async def test_a_key_after_an_auto_focus_component_mounts_later_reaches_it() -> None:
    deliveries: list[Delivery] = []

    def children(is_mounted: bool) -> Sequence[Component]:
        return [focusable("late", deliveries, auto_focus=True)] if is_mounted else []

    await run(rooted(deliveries, children), [TOGGLE, PROBE])

    assert probed(deliveries) == ["late"]


async def test_a_component_that_a_focus_on_names_as_it_mounts_is_focused_in_the_first_frame_that_shows_it() -> None:
    frames: list[Frame] = []
    handle = FocusHandle()

    await run(
        rooted(
            [], lambda is_mounted: [focus_label("late", handle=handle)] if is_mounted else [], toggled=FocusOn(handle)
        ),
        [TOGGLE, Screenshot(handler=frames.append)],
    )

    assert lines(frames) == [["late:on"]]


async def test_a_component_that_hides_itself_when_it_gains_focus_raises() -> None:
    @component
    def hides() -> Text:
        focus = use_focus(auto_focus=True)
        return Text(content="hides", style=display_none if focus.is_focused else default)

    with pytest.raises(UnsettledFocus, match="hid itself"):
        await run(rooted([], lambda is_mounted: [hides()] if is_mounted else []), [TOGGLE])


async def test_unmounting_the_focused_component_clears_focus() -> None:
    deliveries: list[Delivery] = []

    def children(is_unmounted: bool) -> Sequence[Component]:
        return [focusable("a", deliveries), *([] if is_unmounted else [focusable("b", deliveries, auto_focus=True)])]

    await run(rooted(deliveries, children), [PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["b", "root"]


async def test_unmounting_the_focused_component_does_not_focus_an_auto_focus_component_that_mounted_before() -> None:
    deliveries: list[Delivery] = []

    def children(is_unmounted: bool) -> Sequence[Component]:
        return [focusable("a", deliveries, auto_focus=True), *([] if is_unmounted else [focusable("b", deliveries)])]

    await run(rooted(deliveries, children), [FocusNext(), PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["b", "root"]


async def test_hiding_the_focused_component_clears_focus() -> None:
    deliveries: list[Delivery] = []

    def children(is_hidden: bool) -> Sequence[Component | AnyElement]:
        return [
            Div(style=display_none if is_hidden else default, children=(focusable("a", deliveries, auto_focus=True),))
        ]

    await run(rooted(deliveries, children), [PROBE, TOGGLE, PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["a", "root", "root"]


async def test_use_focus_keeps_its_handle_across_renders() -> None:
    handles: list[FocusHandle] = []

    @component
    def counter() -> Text:
        focus = use_focus(auto_focus=True)
        count, set_count = use_state(0)
        handles.append(focus.handle)

        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            set_count(count + 1)
            return ()

        return Text(content=str(count), on_input=on_input)

    await run(counter(), [PROBE, PROBE])

    assert len(handles) > 2
    assert all(handle is handles[0] for handle in handles)


async def test_calling_use_focus_twice_in_one_component_raises() -> None:
    @component
    def twice() -> Text:
        use_focus()
        use_focus()
        return Text(content="")  # pragma: never runs

    with pytest.raises(DuplicateUseFocus, match="use_focus"):
        await run(twice(), [])


async def test_with_tab_focus_on_the_root_a_focused_handler_that_claims_tab_keeps_focus() -> None:
    deliveries: list[Delivery] = []

    def children(_: bool) -> Sequence[Component]:
        return [focusable("a", deliveries, auto_focus=True, response=()), focusable("b", deliveries)]

    await run(rooted(deliveries, children, on_input=tab_focus), [TAB, PROBE])

    assert probed(deliveries) == ["a"]


async def test_with_tab_focus_on_the_root_tab_moves_focus() -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, three(deliveries), on_input=tab_focus), [TAB, PROBE, TAB, PROBE, BACK_TAB, PROBE])

    assert probed(deliveries) == ["a", "b", "a"]


@pytest.mark.parametrize(("x", "y", "expected"), [(2, 2, "inner"), (8, 8, "outer")])
async def test_with_focus_receiver_on_press_on_nested_focusables_a_click_focuses_the_innermost(
    x: int, y: int, expected: str
) -> None:
    deliveries: list[Delivery] = []

    def children(_: bool) -> Sequence[Component]:
        inner = focusable("inner", deliveries, style=box(1, 1, 3, 3), on_press=focus_receiver_on_press)
        return [
            focusable("outer", deliveries, style=box(0, 0, 10, 10), on_press=focus_receiver_on_press, children=(inner,))
        ]

    await run(rooted(deliveries, children), [*press(x, y), PROBE])

    assert probed(deliveries) == [expected]


# Scoped movement


@component
def scoped_group(
    deliveries: list[Delivery], on_input: InputHandler, children: tuple[Component | AnyElement, ...]
) -> Div:
    return Div(style=box(0, 2, 20, 3), on_input=first(recording("group", deliveries), on_input), children=children)


def xyz(deliveries: list[Delivery]) -> tuple[Component, ...]:
    return focusable("x", deliveries), focusable("y", deliveries), focusable("z", deliveries)


def before_group_after(
    deliveries: list[Delivery], group_input: InputHandler, group_children: tuple[Component | AnyElement, ...]
) -> Component:
    """`before`, which takes focus, then a group holding `group_children`, then `after`, with `tab_focus` on the root."""
    return rooted(
        deliveries,
        lambda _: [
            focusable("before", deliveries, auto_focus=True, style=box(0, 0, 20, 1)),
            scoped_group(deliveries, group_input, group_children),
            focusable("after", deliveries, style=box(0, 8, 20, 1)),
        ],
        on_input=tab_focus,
    )


def scroll_moves_focus_within(event: InputEvent, receiver: Receiver) -> InputResponse:
    match event:
        case MouseScrolledDown():
            return FocusNext(within=receiver.subtree)
        case _:
            return FocusPrevious(within=receiver.subtree) if isinstance(event, MouseScrolledUp) else None


async def test_scoped_movement_moves_only_among_the_subtrees_focusables_and_wraps() -> None:
    deliveries: list[Delivery] = []

    await run(
        before_group_after(deliveries, tab_focus, xyz(deliveries)),
        [FocusNext(), PROBE, TAB, PROBE, TAB, PROBE, TAB, PROBE, BACK_TAB, PROBE],
    )

    assert probed(deliveries) == ["x", "y", "z", "x", "z"]


@pytest.mark.parametrize(
    ("event", "expected"),
    [(MouseScrolledDown(absolute=Position(1, 3)), "x"), (MouseScrolledUp(absolute=Position(1, 3)), "z")],
    ids=["next", "previous"],
)
async def test_scoped_movement_from_focus_outside_the_subtree_goes_to_its_first_or_last(
    event: InputEvent, expected: str
) -> None:
    deliveries: list[Delivery] = []

    await run(before_group_after(deliveries, scroll_moves_focus_within, xyz(deliveries)), [PROBE, event, PROBE])

    assert probed(deliveries) == ["before", expected]


async def test_with_tab_focus_on_the_root_and_a_group_tab_cycles_inside_the_group_and_through_the_tree_outside() -> (
    None
):
    deliveries: list[Delivery] = []

    await run(
        before_group_after(deliveries, tab_focus, xyz(deliveries)),
        [TAB, PROBE, TAB, TAB, TAB, PROBE, FocusPrevious(), PROBE, BACK_TAB, PROBE, TAB, PROBE],
    )

    assert probed(deliveries) == ["x", "x", "before", "after", "before"]


async def test_scoped_movement_includes_a_subtrees_own_element_when_it_is_focusable() -> None:
    deliveries: list[Delivery] = []

    @component
    def self_scoped() -> Div:
        use_focus()
        return Div(on_input=first(recording("self", deliveries), tab_focus), children=(focusable("inner", deliveries),))

    await run(
        rooted(deliveries, lambda _: [focusable("before", deliveries, auto_focus=True), self_scoped()]),
        [FocusNext(), PROBE, TAB, PROBE, TAB, PROBE],
    )

    assert probed(deliveries) == ["self", "inner", "self"]


@pytest.mark.parametrize(
    "children",
    [
        lambda deliveries: (),
        lambda deliveries: (Div(style=display_none, children=(focusable("hidden", deliveries),)),),
        lambda deliveries: (focusable("unfocusable", deliveries, is_focusable=False),),
        lambda deliveries: (focusable("out of order", deliveries, in_focus_order=False),),
    ],
    ids=["empty", "hidden", "unfocusable", "out of the focus order"],
)
async def test_scoped_movement_does_nothing_for_a_subtree_with_no_visible_node_in_the_focus_order(
    children: Callable[[list[Delivery]], tuple[Component | AnyElement, ...]],
) -> None:
    deliveries: list[Delivery] = []

    await run(
        before_group_after(deliveries, scroll_moves_focus_within, children(deliveries)),
        [MouseScrolledDown(absolute=Position(1, 3)), PROBE],
    )

    assert probed(deliveries) == ["before"]


async def test_scoped_movement_does_nothing_for_a_subtree_that_has_unmounted() -> None:
    deliveries: list[Delivery] = []
    subtrees: list[Subtree] = []

    def remember_subtree(event: InputEvent, receiver: Receiver) -> InputResponse:
        subtrees.append(receiver.subtree)
        return ()

    def move_into_remembered(event: InputEvent, receiver: Receiver) -> InputResponse:
        return FocusNext(within=subtrees[0]) if event == KeyPressed(key="n") else None

    def children(is_unmounted: bool) -> Sequence[Component]:
        return [
            focusable("before", deliveries, auto_focus=True, style=box(0, 0, 20, 1)),
            *([] if is_unmounted else [scoped_group(deliveries, remember_subtree, xyz(deliveries))]),
        ]

    await run(
        rooted(deliveries, children, on_input=move_into_remembered),
        [MouseScrolledDown(absolute=Position(1, 3)), TOGGLE, KeyPressed(key="n"), PROBE],
    )

    assert probed(deliveries) == ["before"]


GROUP = ElementHandle()


@component
def handled_group(children: tuple[Component | AnyElement, ...]) -> Div:
    return Div(style=box(0, 2, 20, 3), handle=GROUP, children=children)


def before_handled_group(deliveries: list[Delivery]) -> Component:
    """`before`, which takes focus, then a group with the handle `GROUP` holding `x`, `y` and `z`."""
    return rooted(
        deliveries,
        lambda _: [focusable("before", deliveries, auto_focus=True), handled_group(xyz(deliveries))],
    )


@pytest.mark.parametrize(
    ("control", "expected"),
    [(FocusNext(within=GROUP), ["x", "y"]), (FocusPrevious(within=GROUP), ["z", "y"])],
    ids=["next", "previous"],
)
async def test_scoped_movement_moves_among_an_elements_focusables_named_by_its_handle(
    control: FocusNext | FocusPrevious, expected: list[str]
) -> None:
    deliveries: list[Delivery] = []

    await run(before_handled_group(deliveries), [control, PROBE, control, PROBE])

    assert probed(deliveries) == expected


async def test_scoped_movement_does_nothing_for_a_handle_that_names_no_mounted_element() -> None:
    deliveries: list[Delivery] = []

    await run(before_handled_group(deliveries), [FocusNext(within=ElementHandle()), PROBE])

    assert probed(deliveries) == ["before"]


async def test_a_parent_and_child_on_one_bubble_path_receive_different_subtrees() -> None:
    subtrees: list[Subtree] = []

    def remember_subtree(event: InputEvent, receiver: Receiver) -> InputResponse:
        subtrees.append(receiver.subtree)
        return None

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=remember_subtree,
            children=(Div(style=box(0, 0, 5, 5), on_input=remember_subtree),),
        )

    await run(root(), [MouseScrolledDown(absolute=Position(1, 1))])

    assert len(subtrees) == 2
    assert subtrees[0] != subtrees[1]


# Handles created by a parent


@component
def labelled(deliveries: list[Delivery], label_input: Callable[[FocusHandle], InputHandler]) -> Div:
    handle, _ = use_state(FocusHandle)
    return Div(
        style=size(20, 10),
        on_input=first(recording("root", deliveries), label_input(handle)),
        children=(focusable("a", deliveries), focusable("child", deliveries, handle=handle)),
    )


async def test_focus_on_focuses_a_child_given_the_parents_handle_from_its_first_render() -> None:
    deliveries: list[Delivery] = []

    def focus_on_key(handle: FocusHandle) -> InputHandler:
        return lambda event, _: FocusOn(handle) if event == KeyPressed(key="f") else None

    await run(labelled(deliveries, focus_on_key), [KeyPressed(key="f"), PROBE])

    assert probed(deliveries) == ["child"]


async def test_focus_on_does_nothing_for_a_handle_no_mounted_component_was_given() -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, three(deliveries)), [FocusNext(), FocusOn(FocusHandle()), PROBE])

    assert probed(deliveries) == ["a"]


async def test_use_focus_returns_the_handle_it_was_given() -> None:
    given = FocusHandle()
    returned: list[FocusHandle] = []

    @component
    def root() -> Text:
        returned.append(use_focus(handle=given).handle)
        return Text(content="")

    await run(root(), [])

    assert returned
    assert all(handle is given for handle in returned)


async def test_passing_a_different_handle_on_a_later_render_raises_naming_both_handles() -> None:
    handles: list[FocusHandle] = []

    @component
    def root() -> Text:
        handles.append(FocusHandle())
        use_focus(handle=handles[-1])
        return Text(content="")

    with pytest.raises(ChangedFocusHandle) as raised:
        await run(root(), [])

    first, passed = handles
    assert (repr(passed) in str(raised.value), repr(first) in str(raised.value)) == (True, True)


def test_a_focus_handles_repr_names_it_by_its_identity() -> None:
    handle = FocusHandle()

    assert repr(handle) == f"<FocusHandle at {id(handle):#x}>"


@pytest.mark.parametrize("is_focusable", [True, False], ids=["focusable", "unfocusable"])
async def test_two_mounted_components_given_one_handle_raise(is_focusable: bool) -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    def children(_: bool) -> Sequence[Component]:
        return [
            focusable("a", deliveries, handle=handle),
            focusable("b", deliveries, handle=handle, is_focusable=is_focusable),
        ]

    with pytest.raises(DuplicateFocusHandle):
        await run(rooted(deliveries, children), [])


# Unfocusable components


async def test_focus_next_and_previous_skip_an_unfocusable_component() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, three(deliveries, is_focusable=False)),
        [FocusNext(), FocusNext(), PROBE, FocusPrevious(), PROBE],
    )

    assert probed(deliveries) == ["c", "a"]


@pytest.mark.parametrize("in_focus_order", [True, False])
async def test_focus_on_does_nothing_for_an_unfocusable_component(in_focus_order: bool) -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    await run(
        rooted(deliveries, three(deliveries, handle=handle, is_focusable=False, in_focus_order=in_focus_order)),
        [FocusOn(handle), PROBE],
    )

    assert probed(deliveries) == ["root"]


async def test_auto_focus_does_not_focus_a_component_that_mounts_unfocusable_nor_once_it_becomes_focusable() -> None:
    deliveries: list[Delivery] = []

    def children(is_focusable: bool) -> Sequence[Component]:
        return [focusable("a", deliveries, auto_focus=True, is_focusable=is_focusable)]

    await run(rooted(deliveries, children), [PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["root", "root"]


async def test_auto_focus_passes_over_a_component_that_mounts_unfocusable_to_a_later_one() -> None:
    deliveries: list[Delivery] = []

    def children(_: bool) -> Sequence[Component]:
        return [
            focusable("unfocusable", deliveries, auto_focus=True, is_focusable=False),
            focusable("focusable", deliveries, auto_focus=True),
        ]

    await run(rooted(deliveries, children), [PROBE])

    assert probed(deliveries) == ["focusable"]


async def test_making_the_focused_component_unfocusable_clears_focus() -> None:
    deliveries: list[Delivery] = []

    def children(is_unfocusable: bool) -> Sequence[Component]:
        return [focusable("a", deliveries, auto_focus=True, is_focusable=not is_unfocusable)]

    await run(rooted(deliveries, children), [PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["a", "root"]


async def test_making_a_component_focusable_again_returns_it_to_its_place_without_focusing_it() -> None:
    deliveries: list[Delivery] = []

    def children(is_focusable: bool) -> Sequence[Component]:
        return [
            focusable("a", deliveries),
            focusable("b", deliveries, is_focusable=is_focusable),
            focusable("c", deliveries),
        ]

    await run(rooted(deliveries, children), [FocusNext(), FocusNext(), PROBE, TOGGLE, PROBE, FocusPrevious(), PROBE])

    assert probed(deliveries) == ["c", "c", "b"]


async def test_a_component_keeps_its_handle_when_it_becomes_unfocusable_and_focusable_again() -> None:
    handles: list[FocusHandle] = []

    @component
    def root() -> Text:
        is_focusable, set_is_focusable = use_state(True)
        handles.append(use_focus(is_focusable=is_focusable).handle)

        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            set_is_focusable(not is_focusable)
            return ()

        return Text(content="", on_input=on_input)

    await run(root(), [TOGGLE, TOGGLE])

    assert len(handles) > 2
    assert all(handle is handles[0] for handle in handles)


async def test_a_press_on_an_unfocusable_component_with_focus_receiver_on_press_is_claimed_and_keeps_focus() -> None:
    deliveries: list[Delivery] = []

    def children(_: bool) -> Sequence[Component]:
        return [
            focusable("a", deliveries, auto_focus=True, style=box(0, 0, 20, 1)),
            focusable(
                "unfocusable",
                deliveries,
                style=box(0, 2, 20, 1),
                is_focusable=False,
                on_press=focus_receiver_on_press,
            ),
        ]

    await run(rooted(deliveries, children), [*press(1, 2), PROBE])

    assert ([delivery.name for delivery in deliveries if delivery.event != PROBE], probed(deliveries)) == (
        ["unfocusable", "unfocusable"],
        ["a"],
    )


# Components out of the focus order


async def test_focus_next_and_previous_skip_a_component_out_of_the_focus_order() -> None:
    deliveries: list[Delivery] = []

    await run(
        rooted(deliveries, three(deliveries, in_focus_order=False)),
        [FocusNext(), FocusNext(), PROBE, FocusPrevious(), PROBE],
    )

    assert probed(deliveries) == ["c", "a"]


async def test_focus_on_focuses_a_component_out_of_the_focus_order() -> None:
    deliveries: list[Delivery] = []
    handle = FocusHandle()

    await run(rooted(deliveries, three(deliveries, handle=handle, in_focus_order=False)), [FocusOn(handle), PROBE])

    assert probed(deliveries) == ["b"]


async def test_auto_focus_focuses_a_component_out_of_the_focus_order() -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, three(deliveries, auto_focus=True, in_focus_order=False)), [PROBE])

    assert probed(deliveries) == ["b"]


async def test_a_press_with_focus_receiver_on_press_focuses_a_component_out_of_the_focus_order() -> None:
    deliveries: list[Delivery] = []

    def children(_: bool) -> Sequence[Component]:
        return [
            focusable(
                "out of order",
                deliveries,
                style=box(0, 2, 20, 1),
                in_focus_order=False,
                on_press=focus_receiver_on_press,
            )
        ]

    await run(rooted(deliveries, children), [*press(1, 2), PROBE])

    assert probed(deliveries) == ["out of order"]


async def test_taking_the_focused_component_out_of_the_focus_order_leaves_it_focused() -> None:
    deliveries: list[Delivery] = []

    def children(is_out_of_order: bool) -> Sequence[Component]:
        return [focusable("a", deliveries, auto_focus=True, in_focus_order=not is_out_of_order)]

    await run(rooted(deliveries, children), [PROBE, TOGGLE, PROBE])

    assert probed(deliveries) == ["a", "a"]


@pytest.mark.parametrize(("control", "expected"), [(FocusNext(), "c"), (FocusPrevious(), "a")])
async def test_from_a_focused_component_out_of_the_focus_order_movement_goes_to_its_neighbors(
    control: AnyControl, expected: str
) -> None:
    deliveries: list[Delivery] = []

    await run(rooted(deliveries, three(deliveries, auto_focus=True, in_focus_order=False)), [control, PROBE])

    assert probed(deliveries) == [expected]


async def test_a_component_that_hides_itself_when_a_focus_on_focuses_it_as_it_mounts_raises() -> None:
    handle = FocusHandle()

    @component
    def hides() -> Text:
        focus = use_focus(handle=handle)
        return Text(content="hides", style=display_none if focus.is_focused else default)

    with pytest.raises(UnsettledFocus, match="hid itself"):
        await run(rooted([], lambda is_mounted: [hides()] if is_mounted else [], toggled=FocusOn(handle)), [TOGGLE])
