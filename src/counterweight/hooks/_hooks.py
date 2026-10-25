from __future__ import annotations

import logging
from asyncio import Queue
from dataclasses import dataclass
from datetime import timedelta
from typing import overload

from counterweight._context_vars import current_event_queue
from counterweight._context_vars import current_focused
from counterweight._context_vars import current_hook_state
from counterweight._context_vars import current_instant
from counterweight._context_vars import current_layouts
from counterweight._context_vars import current_use_mouse_listeners
from counterweight._layout import INITIAL_RECTS
from counterweight._layout import Layouts
from counterweight._utils import forever
from counterweight.animation import FRAME_INTERVAL
from counterweight.controls import AnyControl
from counterweight.events import AnyEvent
from counterweight.events import ControlSent
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.geometry import ORIGIN
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Scroll
from counterweight.hooks._impls import NodeKey
from counterweight.hooks._types import Deps
from counterweight.hooks._types import Getter
from counterweight.hooks._types import Ref
from counterweight.hooks._types import Setter
from counterweight.hooks._types import Setup
from counterweight.hooks._types import Tick

logger = logging.getLogger(__name__)


@overload
def use_state[T](initial_value: Getter[T]) -> tuple[T, Setter[T]]: ...


@overload
def use_state[T](initial_value: T) -> tuple[T, Setter[T]]: ...


def use_state[T](initial_value: Getter[T] | T) -> tuple[T, Setter[T]]:
    """
    Parameters:
        initial_value: The initial value of the state.
            It can either be the initial value itself, or a zero-argument function that returns the initial value.

    Returns:
        The current value of the state (i.e., for the current render cycle).

        A function that can be called to update the value of the state (e.g., in an event handler).
            It can either be called with the new value of the state,
            or a function that takes the current value of the state and returns the new value of the state.
            When the new value depends on the current one, pass a function:
            a value computed from the state a render saw loses every update made since,
            such as from other key presses read before the next render
            (see [Updating state from its previous value](../hooks/use_state.md#updating-state-from-its-previous-value)).
            If the value is not equal to the current of the state,
            Counterweight will trigger a render cycle.
            It is the same object on every render,
            so it can be left out of an effect's `deps`, and including it never reruns the effect.
            Once the component unmounts, calling it does nothing.
    """
    return current_hook_state.get().use_state(initial_value)


def toggle(value: bool) -> bool:
    """
    Flips a flag: pass it to a [`use_state`][counterweight.hooks.use_state] setter, as `set_open(toggle)`,
    so each toggle flips the latest value, even when several land before the next render.
    It takes only a `bool`, so a type checker rejects it for state of any other type,
    where `operator.not_` would quietly turn the state into one.
    """
    return not value


def use_ref[T](initial_value: Getter[T] | T) -> Ref[T]:
    """
    Parameters:
        initial_value: the initial value of the ref.
            It can either be the initial value itself, or a zero-argument function that returns the initial value.

    Returns:
        A [`Ref`][counterweight.hooks.Ref] that holds a reference to the given value.
    """
    return current_hook_state.get().use_ref(initial_value)


def use_effect(setup: Setup, deps: Deps = None) -> None:
    """
    Parameters:
        setup: The setup function that will be called when the component first mounts
            or if its dependencies have changed (see below).

        deps: The dependencies of the effect.
            If any of the dependencies change, the previous invocation of the `setup` function will be cancelled
            and the `setup` function will be run again.
            If `None`, the `setup` function will be run every time the component renders.
    """
    return current_hook_state.get().use_effect(setup, deps)


def use_memo[T](compute: Getter[T], deps: tuple[object, ...]) -> T:
    """
    Parameters:
        compute: A zero-argument function that computes the value.
            It runs while the component renders: on the first render, and on every render whose `deps` changed.

        deps: The values `compute` depends on.
            If any of them change (compared with `==`), `compute` runs again.
            `()` computes the value once, when the component mounts.
            Unlike `use_effect`'s, these can't be `None`: to compute on every render, don't use this hook.

    Returns:
        The value `compute` returned when `deps` last changed.
            It is the same object on every render until then,
            so an element returned from it keeps the components below it from re-running,
            and a handler returned from it can be passed to a `memo` component without making it re-run.
            The cached value MUST depend only on `deps`;
            `check_purity` on `counterweight._app.app` catches a value that goes stale.
    """
    return current_hook_state.get().use_memo(compute, deps)


def use_clock(interval: timedelta | None) -> Tick:
    """
    Parameters:
        interval: How often the component reads the clock.
            Ticks start at whole multiples of `interval` past midnight on the wall clock,
            in the clock's timezone (for an `interval` that divides a day),
            so components reading the clock every second and every minute both re-run as the minute turns.
            `None` stops reading it, as a `null` delay pauses React's `useInterval`:
            every render returns the last reading, and the clock never re-runs the component,
            until a render gives it an interval again, which takes a fresh reading.

    Returns:
        A reading of the app's clock, taken when the component mounts,
            and again on the first render after each new tick starts,
            with the component re-running then if nothing else made it.
            Between those, every render returns the same reading,
            so the component's output stays a function of its arguments and hooks.
            Components that take a reading in the same frame get the same one, whatever their intervals.

    Raises:
        ValueError: If `interval` isn't positive.
    """
    if interval is not None and interval <= timedelta():
        raise ValueError(f"use_clock needs a positive interval, but got {interval!r}")

    return current_hook_state.get().use_clock(interval, current_instant.get())


@dataclass(frozen=True, slots=True)
class AnimationStart:
    """When an animation hook last started, on the clock's `since_start`, the `deps` it started for, and whether it ended."""

    deps: tuple[object, ...]
    at: timedelta
    is_done: bool = False


def use_progress(duration: timedelta, deps: tuple[object, ...] = (), *, interval: timedelta = FRAME_INTERVAL) -> float:
    """
    How far through an animation `duration` long the calling component is,
    from 0 when it starts, rising to 1, where it holds, as a CSS animation that plays once and fills forwards does.
    Shape the motion by passing the result to an [easing function][counterweight.animation.Easing].

    Parameters:
        duration: How long the animation takes. Zero ends it as soon as it starts, at 1.
        deps: The values the animation depends on.
            It starts when the component mounts, and again whenever any of them change (compared with `==`),
            as `use_effect` runs again, so a component that stays mounted can play it more than once.
        interval: How often it reads the clock while it moves.
            Once it reaches 1 it stops reading the clock, so a finished animation re-runs its component
            only once more, at the next `interval`, and never after that.

    Raises:
        ValueError: If `duration` is negative.
    """
    if duration < timedelta():
        raise ValueError(f"use_progress needs a duration that isn't negative, but got {duration!r}")

    started: Ref[AnimationStart | None] = use_ref(None)
    previous = started.current
    is_restarted = previous is None or previous.deps != deps
    tick = use_clock(interval if previous is None or is_restarted or not previous.is_done else None)
    at = tick.since_start if previous is None or is_restarted else previous.at
    progress = 1.0 if duration == timedelta() else min((tick.since_start - at) / duration, 1.0)
    started.current = AnimationStart(deps=deps, at=at, is_done=progress == 1.0)
    return progress


def use_loop(
    period: timedelta,
    deps: tuple[object, ...] = (),
    *,
    is_playing: bool = True,
    interval: timedelta = FRAME_INTERVAL,
) -> float:
    """
    Where in an animation that repeats every `period` the calling component is, from 0 up to (but not including) 1,
    as a CSS animation whose iteration count is `infinite` is.

    Parameters:
        period: How long one time through the animation takes.
        deps: The values the animation depends on.
            It starts when the component mounts, and again from 0 whenever any of them change (compared with `==`).
        is_playing: Whether it moves. While it doesn't, it stops reading the clock, holding where it is.
            One that starts while it isn't playing, as it mounts or as its `deps` change, holds at 0
            and starts when it plays.
            Unlike a paused CSS animation, one paused partway doesn't resume from there:
            it carries on from wherever the time since it started puts it.
        interval: How often it reads the clock while it plays.

    Raises:
        ValueError: If `period` isn't positive.
    """
    if period <= timedelta():
        raise ValueError(f"use_loop needs a positive period, but got {period!r}")

    started: Ref[AnimationStart | None] = use_ref(None)
    previous = started.current
    tick = use_clock(interval if is_playing else None)
    if previous is not None and previous.deps == deps:
        at = previous.at
    elif is_playing:
        at = tick.since_start
    else:
        # A paused clock's reading is stale, so a start waits for the fresh one the clock takes when it plays.
        started.current = None
        return 0.0
    started.current = AnimationStart(deps=deps, at=at)
    return ((tick.since_start - at) % period) / period


@dataclass(frozen=True, slots=True)
class ControlSender:
    """
    What [`use_controls`][counterweight.hooks.use_controls] returns:
    call it with a control to send it to the app, as `send_control(Quit())`.
    """

    queue: Queue[AnyEvent]

    def __call__(self, control: AnyControl) -> None:
        self.queue.put_nowait(ControlSent(control=control))


def use_controls() -> ControlSender:
    """
    Sends the app controls from outside an input handler,
    such as from an effect, or a callback a program or a timer calls.
    An input handler returns its controls instead.

    Returns:
        A sender that hands the app each control it's called with,
        which the app handles as it handles a control an input handler returns,
        after the events already waiting.
        Every render returns an equal sender, so it can be left out of an effect's `deps`,
        and including it never reruns the effect.
        It keeps working after the component unmounts, so a control sent as it goes, such as `Quit`, still arrives.
    """
    return ControlSender(queue=current_event_queue.get())


def use_rects(handle: ElementHandle | None = None) -> Rects:
    """
    Parameters:
        handle: The element to report on, by the [`ElementHandle`][counterweight.focus.ElementHandle]
            passed to its `handle`, as a React component measures another element through a ref,
            or `None` for the calling component's top-level element.

    Returns:
        A recording describing the rectangular areas of the
            `content`, `padding`, `border`, and `margin` of
            the element *as of the last layout*.
            In a component's first render, and for a `handle` that named no visible element in the last layout,
            the returned rectangles will all be positioned
            at the top-left corner of the screen with `0` width and height.
            A component that calls `use_rects` renders again as soon as any of the rectangles it read move,
            before the frame that moved them is painted.
    """
    hooks = current_hook_state.get()
    rects = rects_in(current_layouts.get(), hooks.key, handle)
    if hooks.rects is None:
        hooks.rects = {}
    hooks.rects[handle] = rects
    return rects


def rects_in(layouts: Layouts, reader: NodeKey, handle: ElementHandle | None = None) -> Rects:
    """
    The rectangles `use_rects(handle)` reports to the node with key `reader`, given the last `layouts`:
    those of the element `handle` names, or of `reader`'s own element if it's `None`.
    """
    key = reader if handle is None else layouts.handles.get(handle)
    # A node absent from the last layouts was hidden or not yet mounted.
    return INITIAL_RECTS if key is None else layouts.by_key.get(key, INITIAL_RECTS)


def use_scroll(handle: ElementHandle | None = None) -> Scroll:
    """
    Parameters:
        handle: The element to report on, by the [`ElementHandle`][counterweight.focus.ElementHandle]
            passed to its `handle`, as a React component reads another element's `scrollTop` through a ref,
            or `None` for the calling component's top-level element.

    Returns:
        How far the element is scrolled, and how far it can be,
            if it's a [scroll container](../layout/scrolling.md), *as of the last layout*, as `use_rects` does.
            A component that calls `use_scroll` renders again as soon as that scroll changes,
            whether a control scrolled it or its content changed size, before the frame that scrolled it is painted.
            It's all zeros in a component's first render, for an element that isn't a scroll container,
            and for a `handle` that named no visible element in the last layout.
    """
    hooks = current_hook_state.get()
    scroll = scroll_in(current_layouts.get(), hooks.key, handle)
    if hooks.scrolls is None:
        hooks.scrolls = {}
    hooks.scrolls[handle] = scroll
    return scroll


NO_SCROLL = Scroll(offset=ORIGIN, max_offset=ORIGIN, view_width=0, view_height=0)


def scroll_in(layouts: Layouts, reader: NodeKey, handle: ElementHandle | None) -> Scroll:
    """
    The scroll `use_scroll(handle)` reports to the node with key `reader`, given the last `layouts`:
    the scroll of the element `handle` names, or of `reader`'s own element if it's `None`.
    """
    key = reader if handle is None else layouts.handles.get(handle)
    return NO_SCROLL if key is None else layouts.scrolls.get(key, NO_SCROLL)


@dataclass(frozen=True, slots=True)
class Mouse:
    """Where the mouse is and which button is held, as [`use_mouse`][counterweight.hooks.use_mouse] returns it."""

    absolute: Position
    """The absolute position of the mouse on the screen (i.e., the top-left corner of the screen is `Position(x=0, y=0)`)."""

    motion: Position
    """The difference in the `absolute` position of the mouse since the last render cycle."""

    button: int | None
    """The button that is currently pressed, or `None` if no button is pressed."""


_INITIAL_MOUSE = Mouse(absolute=Position(-1, -1), motion=Position(0, 0), button=None)


def use_mouse() -> Mouse:
    """
    Returns:
        A record describing the current state of the mouse.
    """
    # Why bother making this a state hook when we could instead store the mouse state directly in a context var?
    # Triggering a state change is a way to signal to the render loop that a component cares about the mouse state
    # without needing to invent a new mechanism dedicated to mouse events,
    # and thus makes them work a lot more like key events.
    mouse, set_mouse = use_state(_INITIAL_MOUSE)
    use_mouse_listeners = current_use_mouse_listeners.get()

    async def setup() -> None:
        use_mouse_listeners.add(set_mouse)

        try:
            await forever()
        finally:
            use_mouse_listeners.remove(set_mouse)

    use_effect(setup=setup, deps=())

    return mouse


@dataclass(frozen=True, slots=True)
class Hovered:
    """
    Which of an element's boxes the mouse is over, as [`use_hovered`][counterweight.hooks.use_hovered] returns it.
    Each box holds the ones inside it, so the mouse over the content box is over all four.
    """

    content: bool
    """Whether the mouse is over the content box."""
    padding: bool
    """Whether the mouse is over the padding box: the content and the padding around it."""
    border: bool
    """Whether the mouse is over the border box: the padding box and the border around it."""
    margin: bool
    """Whether the mouse is over the margin box: the border box and the margin around it."""


def use_hovered() -> Hovered:
    """
    Returns:
        A record describing which of the calling component's top-level element's
            `content`, `padding`, `border`, and `margin` rectangles the mouse is currently inside,
            counting only the parts inside its [`clip`][counterweight.geometry.Rects.clip],
            so the mouse over a part its ancestors clip away is outside all of them.
    """
    mouse = use_mouse()
    rects = use_rects()

    position = mouse.absolute
    if rects.clip is None or not rects.clip.contains(position):
        return Hovered(content=False, padding=False, border=False, margin=False)

    return Hovered(
        content=rects.content.contains(position),
        padding=rects.padding.contains(position),
        border=rects.border.contains(position),
        margin=rects.margin.contains(position),
    )


@dataclass(frozen=True, slots=True)
class Focus:
    """What [`use_focus`][counterweight.hooks.use_focus] returns to the calling component."""

    is_focused: bool
    """Whether the calling component is focused, so it receives key presses, as of this render."""

    handle: FocusHandle
    """The handle that names the calling component, for [`FocusOn`][counterweight.controls.FocusOn]."""


def use_focus(
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Focus:
    """
    Makes the calling component focusable.
    Its top-level element, the one it returns, is the one that's focused,
    so a component that handles key presses puts its handler on that element.
    A component can call it only once.

    Parameters:
        auto_focus: Whether the component takes focus when it mounts visible and focusable while nothing is focused,
            or inside the focused component while that one is out of the focus order,
            as an element with `autofocus` takes focus from a document's body, which no Tab reaches either.
            When several mount in the same render, the first in tree order takes focus.
            A component that mounts hidden or unfocusable doesn't take focus when it's shown or made focusable later.

        handle: The handle that names the component, which a parent creates with `use_state(FocusHandle)`
            to focus a child it renders with [`FocusOn`][counterweight.controls.FocusOn].
            If `None`, `use_focus` creates one on the first render and keeps it.
            Every render MUST pass the same handle as the first,
            or `use_focus` raises `ChangedFocusHandle`,
            and two mounted components given the same handle raise `DuplicateFocusHandle`.

        is_focusable: Whether the component can be focused, like a browser's `disabled` attribute when `False`.
            Nothing can focus an unfocusable component,
            and making the focused component unfocusable clears focus.
            It still receives the mouse events routed to it.

        in_focus_order: Whether [`FocusNext`][counterweight.controls.FocusNext]
            and [`FocusPrevious`][counterweight.controls.FocusPrevious] stop on the component,
            like a browser's `tabindex="-1"` when `False`.
            A component out of the focus order can still be focused with
            [`FocusOn`][counterweight.controls.FocusOn], `auto_focus`, or a press,
            and keeps focus once it has it, until an `auto_focus` component mounts inside it.

    Returns:
        Whether the component is focused, and its handle, which is the same object on every render.
    """
    hooks = current_hook_state.get()
    focus = hooks.use_focus(
        auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order
    )
    return Focus(is_focused=is_focusable and current_focused.get() == hooks.key, handle=focus.handle)
