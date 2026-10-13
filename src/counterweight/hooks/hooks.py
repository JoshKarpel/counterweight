from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import overload

from counterweight._context_vars import (
    current_focused,
    current_hook_state,
    current_instant,
    current_layouts,
    current_use_mouse_listeners,
)
from counterweight._utils import forever
from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, Pasted, Receiver
from counterweight.focus import FocusHandle
from counterweight.geometry import Position, Rects
from counterweight.graphemes import graphemes
from counterweight.hooks.impls import NodeKey
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup, Tick
from counterweight.layout import INITIAL_RECTS, Layouts
from counterweight.text_editing import Edit, EditableText, key_edit, paste_edit, settled

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
            `check_purity` on `counterweight.app.app` catches a value that goes stale.
    """
    return current_hook_state.get().use_memo(compute, deps)


def use_clock(interval: timedelta) -> Tick:
    """
    Parameters:
        interval: How often the component reads the clock.
            Ticks start at whole multiples of `interval` past midnight on the wall clock
            (for an `interval` that divides a day),
            so components reading the clock every second and every minute both re-run as the minute turns.

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
    if interval <= timedelta():
        raise ValueError(f"use_clock needs a positive interval, but got {interval!r}")

    return current_hook_state.get().use_clock(interval, current_instant.get())


def use_rects() -> Rects:
    """
    Returns:
        A recording describing the rectangular areas of the
            `content`, `padding`, `border`, and `margin` of
            the calling component's top-level element
            *on the previous render cycle*.
            In the initial render, the returned rectangles will all be positioned
            at the top-left corner of the screen with `0` width and height.
            A component that calls `use_rects` also renders on the next render cycle after its rectangles move.
    """
    hooks = current_hook_state.get()
    rects = rects_in(current_layouts.get(), hooks.key)
    hooks.rects = rects
    return rects


def rects_in(layouts: Layouts, key: NodeKey) -> Rects:
    """The rectangles `use_rects` reports for the node with `key`, given the previous frame's `layouts`."""
    # A node absent from the previous frame's layouts was hidden or not yet mounted.
    return layouts.by_key.get(key, INITIAL_RECTS)


@dataclass(frozen=True, slots=True)
class Mouse:
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

    async def setup() -> None:
        use_mouse_listeners = current_use_mouse_listeners.get()

        use_mouse_listeners.add(set_mouse)

        try:
            await forever()
        finally:
            use_mouse_listeners.remove(set_mouse)

    use_effect(setup=setup, deps=())

    return mouse


@dataclass(frozen=True, slots=True)
class Hovered:
    content: bool
    padding: bool
    border: bool
    margin: bool


def use_hovered() -> Hovered:
    """
    Returns:
        A record describing which of the calling component's top-level element's
            `content`, `padding`, `border`, and `margin` rectangles the mouse is currently inside.
    """
    mouse = use_mouse()
    rects = use_rects()

    return Hovered(
        content=rects.content.contains(mouse.absolute),
        padding=rects.padding.contains(mouse.absolute),
        border=rects.border.contains(mouse.absolute),
        margin=rects.margin.contains(mouse.absolute),
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
        auto_focus: Whether the component takes focus when it mounts visible and focusable while nothing is focused.
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
            and keeps focus once it has it.

    Returns:
        Whether the component is focused, and its handle, which is the same object on every render.
    """
    hooks = current_hook_state.get()
    focus = hooks.use_focus(
        auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order
    )
    return Focus(is_focused=is_focusable and current_focused.get() == hooks.key, handle=focus.handle)


@dataclass(frozen=True, slots=True)
class TextInput:
    """What [`use_text_input`][counterweight.hooks.use_text_input] returns to the calling component."""

    before_cursor: str
    """The value's text before the cursor."""

    at_cursor: str
    """
    The grapheme cluster at the cursor,
    or a space when the cursor is at the end of the value, so there's always a cell to draw the cursor in.
    """

    after_cursor: str
    """The value's text after `at_cursor`."""

    cursor: int
    """How many of the value's grapheme clusters come before the cursor."""

    focus: Focus
    """Whether the calling component is focused, and its handle, as [`use_focus`][counterweight.hooks.use_focus] returns them."""

    on_input: InputHandler
    """
    The handler that edits the value, for the calling component to put on the element it returns.
    It returns `None` for every event while that element isn't focused,
    and for the key presses it doesn't edit with, such as Enter, Tab, Up and Down,
    so they bubble to the element's ancestors.
    """


def use_text_input(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> TextInput:
    """
    Edits one line of text, leaving how it's drawn to the calling component.
    The calling component owns the value, and the hook owns the cursor and makes the component focusable.

    Parameters:
        value: The text being edited.

        set_value: Called with a function from the latest value to the edited one for each edit,
            which it MUST call before returning, as a [`use_state`][counterweight.hooks.use_state] setter does.
            Several key presses can arrive between renders, as when typing fast,
            so an edit applies to the latest value rather than to `value`, which is the one this render saw.
            Validate or transform an edit by wrapping the setter:
            `lambda edit: set_value(lambda v: new if (new := edit(v)).isdigit() else v)` keeps only digits.
            Each edit also calls it before and after with a function that returns the value it's given,
            to read the latest value, and then the one the edit settled at:
            the cursor moves with an edit unless the setter left the value as it was before it.

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus].

        handle: Passed to [`use_focus`][counterweight.hooks.use_focus].

        is_focusable: Passed to [`use_focus`][counterweight.hooks.use_focus].

        in_focus_order: Passed to [`use_focus`][counterweight.hooks.use_focus].

    Returns:
        The value split around the cursor, for the calling component to draw,
        and the handler that edits it, for the calling component to put on the element it returns.
        The cursor starts at the end of the value, and stays where it is, clamped to the value,
        when the value changes other than by an edit.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    cursor, set_cursor = use_state(lambda: len(graphemes(value)))

    def apply(edit: Edit) -> None:
        # Both setters apply an updater immediately, so this reads the latest cursor, then the latest value,
        # and a second edit before the next render starts from the first one's result.
        def edit_cursor(latest_cursor: int) -> int:
            # This render's value stands until the setter reports a later one, which one that ignores calls never does.
            values = [value]

            def read_value(latest_value: str) -> str:
                values.append(latest_value)
                return latest_value

            set_value(read_value)
            before = EditableText.at(values[-1], latest_cursor)
            edited = edit(before)
            set_value(lambda _: edited.value)
            # A setter that validates or transforms the edit decides the value, so read back what it kept.
            set_value(read_value)
            return settled(before, edited, values[-1]).cursor

        set_cursor(edit_cursor)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None

        match event:
            case KeyPressed(key=key):
                edit = key_edit(key)
            case Pasted(text=text):
                edit = paste_edit(text)
            case _:
                return None

        if edit is None:
            return None

        apply(edit)
        return ()

    clusters = graphemes(value)
    shown = EditableText.at(value, cursor)
    return TextInput(
        before_cursor="".join(clusters[: shown.cursor]),
        at_cursor=clusters[shown.cursor] if shown.cursor < len(clusters) else " ",
        after_cursor="".join(clusters[shown.cursor + 1 :]),
        cursor=shown.cursor,
        focus=focus,
        on_input=on_input,
    )
