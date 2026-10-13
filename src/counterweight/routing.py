"""
Which handlers an input event reaches, given the last render's shadow tree and layouts:
the event's target, the ancestors it bubbles to from there, and the node that captured a press;
and where focus can go, given the same tree.
Handlers run here, but what their controls do is up to the render loop, which holds the focused key.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

from counterweight.controls import AnyControl
from counterweight.events import (
    InputEvent,
    InputHandler,
    KeyPressed,
    MouseDown,
    MouseEvent,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledUp,
    MouseUp,
    Receiver,
    response_controls,
)
from counterweight.focus import FocusHandle, Subtree
from counterweight.geometry import Position
from counterweight.layout import Layouts

if TYPE_CHECKING:
    from counterweight.hooks.impls import NodeKey
    from counterweight.shadow import ShadowTree


@dataclass(frozen=True, slots=True)
class Claim:
    """The node whose handler stopped an event, and the controls it returned."""

    key: NodeKey
    controls: tuple[AnyControl, ...]


@dataclass(frozen=True, slots=True)
class Press:
    """
    A press in progress: the buttons held since the first of them went down,
    and the node that claimed its first `MouseDown`, or `None` if nothing did.
    """

    buttons: frozenset[int]
    captor: NodeKey | None


@dataclass(frozen=True, slots=True)
class Focusable:
    """What a visible node's last `use_focus` call said about it."""

    handle: FocusHandle
    auto_focus: bool
    is_focusable: bool
    in_focus_order: bool


class DuplicateFocusHandle(Exception):
    """Raised when two mounted components are given the same `FocusHandle`, which leaves it naming neither."""


class UnsettledFocus(Exception):
    """
    Raised when re-rendering the components whose focus a render changed changes focus again,
    which only a component that hides itself because it gained focus can cause:
    one that lost focus already rendered unfocused if it became unfocusable, and draws nothing if it's hidden.
    """


@dataclass(frozen=True, slots=True)
class RoutingTable:
    """What routing reads from one render, built once per render rather than once per event."""

    screen: NodeKey
    """The node of the element the app wraps the root component in, which is never a target."""
    root: NodeKey
    """The root component's node, the last on every bubble path."""
    layouts: Layouts
    parents: Mapping[NodeKey, NodeKey | None]
    handlers: Mapping[NodeKey, InputHandler]
    """The handler of every visible node that has one."""
    focus: Mapping[NodeKey, Focusable]
    """Every visible node whose last run called `use_focus`, in tree order, unfocusable ones included."""
    focus_keys: Mapping[FocusHandle, NodeKey]
    """The key of every visible, focusable node, by its handle."""

    @classmethod
    def of(cls, shadow: ShadowTree, layouts: Layouts) -> RoutingTable:
        """
        The table for `shadow`, whose root is the screen element, and the `layouts` computed from it.
        Raises `DuplicateFocusHandle` if two mounted components, hidden or unfocusable ones included, share a handle.
        """
        (root,) = shadow.root.children

        if len({use_focus.handle for use_focus in shadow.focusable.values()}) != len(shadow.focusable):
            raise DuplicateFocusHandle(
                "Two mounted components were given the same FocusHandle. "
                "Give each focusable component its own, such as from its own use_state(FocusHandle)."
            )

        focus = {
            key: Focusable(
                handle=use_focus.handle,
                auto_focus=use_focus.auto_focus,
                is_focusable=use_focus.is_focusable,
                in_focus_order=use_focus.in_focus_order,
            )
            for key, use_focus in shadow.focusable.items()
            if key in layouts.by_key
        }

        return cls(
            screen=shadow.root.key,
            root=root.key,
            layouts=layouts,
            parents=shadow.parents,
            handlers={
                key: element.on_input for key, element, _ in layouts.in_paint_order if element.on_input is not None
            },
            focus=focus,
            focus_keys={focusable.handle: key for key, focusable in focus.items() if focusable.is_focusable},
        )

    def target_at(self, position: Position) -> NodeKey:
        """
        The topmost visible element whose border box contains `position`, the last such in paint order,
        or the root component's node if that's only the screen.
        """
        for key, _, layout in reversed(self.layouts.in_paint_order):
            if layout.border.contains(position):
                return self.root if key == self.screen else key
        return self.root

    def path(self, target: NodeKey) -> Iterator[NodeKey]:
        """`target`, then each of its ancestors up to the root component's node."""
        key: NodeKey | None = target
        while key is not None and key != self.screen:
            yield key
            key = self.parents[key]

    def bubble(self, event: InputEvent, target: NodeKey, focused: NodeKey | None) -> Claim | None:
        """
        Calls the handlers on `target`'s path in turn, until one responds with something other than `None`,
        or `None` if none does.
        """
        for key in self.path(target):
            if (controls := self.call(key, event, is_target=key == target, focused=focused)) is not None:
                return Claim(key=key, controls=controls)
        return None

    def deliver(self, event: InputEvent, key: NodeKey, focused: NodeKey | None) -> tuple[AnyControl, ...]:
        """Calls `key`'s handler alone, as the event's target, and returns its controls whatever it responds."""
        return self.call(key, event, is_target=True, focused=focused) or ()

    def call(
        self, key: NodeKey, event: InputEvent, is_target: bool, focused: NodeKey | None
    ) -> tuple[AnyControl, ...] | None:
        """
        The controls `key`'s handler responds to `event` with,
        or `None` if it doesn't handle the event, or if the node has no handler, is hidden, or has unmounted.
        """
        if (handler := self.handlers.get(key)) is None:
            return None
        focus = self.focus.get(key)
        receiver = Receiver(
            rects=self.layouts.by_key[key].rects,
            is_target=is_target,
            focus_handle=None if focus is None else focus.handle,
            is_focused=key == focused,
            subtree=Subtree(key=key),
        )
        return response_controls(handler(event, receiver))

    def can_focus(self, key: NodeKey) -> bool:
        """Whether the node with `key` is visible, and its last run called `use_focus` with `is_focusable=True`."""
        return (focus := self.focus.get(key)) is not None and focus.is_focusable

    def contains(self, subtree: Subtree, key: NodeKey) -> bool:
        """Whether the node with `key` is `subtree`'s node or one of its descendants."""
        ancestor: NodeKey | None = key
        while ancestor is not None:
            if ancestor == subtree.key:
                return True
            ancestor = self.parents.get(ancestor)
        return False

    def moved_focus(self, focused: NodeKey | None, within: Subtree | None, is_forward: bool) -> NodeKey | None:
        """
        The key that `FocusNext` (if `is_forward`) or `FocusPrevious` focuses, given the `focused` key:
        the next or previous node in the focus order among the focusable nodes in `within`, wrapping at its ends,
        starting from `focused`'s place in tree order if it's one of them, whether or not it's in the focus order,
        or from before the first or after the last if it isn't.
        It's `focused` if `within` holds no node in the focus order.
        """
        candidates = [
            key
            for key, focus in self.focus.items()
            if focus.is_focusable and (within is None or self.contains(within, key))
        ]
        if not is_forward:
            candidates.reverse()

        if focused in candidates:
            start = candidates.index(focused) + 1
            candidates = candidates[start:] + candidates[:start]

        return next((key for key in candidates if self.focus[key].in_focus_order), focused)

    def reconciled_focus(self, focused: NodeKey | None, mounted: Collection[NodeKey]) -> NodeKey | None:
        """
        The focused key after a render that built this table and `mounted` the components with those keys:
        `focused`, unless it can no longer be focused because it unmounted, is hidden, or is unfocusable,
        in which case it's cleared.
        Then, if nothing is focused, it's the first focusable node in tree order that mounted with `auto_focus`.
        """
        if focused is not None and self.can_focus(focused):
            return focused
        return next(
            (key for key, focus in self.focus.items() if focus.auto_focus and focus.is_focusable and key in mounted),
            None,
        )


def route_key(event: KeyPressed, focused: NodeKey | None, table: RoutingTable) -> tuple[AnyControl, ...]:
    """
    Bubbles `event` from the `focused` node, or from the root component's node if nothing is focused,
    and returns the controls of the handler that claimed it, if any.
    """
    return claimed_controls(table.bubble(event, table.root if focused is None else focused, focused))


def route_mouse(
    event: MouseEvent, press: Press | None, focused: NodeKey | None, table: RoutingTable
) -> tuple[Press | None, tuple[AnyControl, ...]]:
    """
    Routes `event` given the press in progress, if any,
    and returns the press for the next event with the controls the handlers returned.

    A press runs from the first button going down to the last one coming up, as in the web's Pointer Events.
    Its first `MouseDown` hit-tests and bubbles, and the node that claims it captures the press:
    the press's later events, each `MouseMoved` with a button held and each button's `MouseDown` and `MouseUp`,
    go to that node alone, wherever the pointer is, and stop there whatever it responds.
    The rest of a press nothing claimed, or whose captor has unmounted, reaches no handler,
    and neither does a `MouseUp` for a button the press doesn't hold,
    so an element never receives the end of a press it didn't see begin.
    A `MouseMoved` with no button held ends a press whose release the terminal never reported,
    and so does a `MouseDown` for a button the press already holds, which starts a new press.
    Wheel events aren't part of a press, and always hit-test.
    """
    match event:
        case MouseScrolledDown() | MouseScrolledUp():
            return press, claimed_controls(table.bubble(event, table.target_at(event.absolute), focused))
        case MouseDown(button=button) if press is not None and button not in press.buttons:
            return Press(buttons=press.buttons | {button}, captor=press.captor), captured(event, press, focused, table)
        case MouseDown(button=button):
            claim = table.bubble(event, table.target_at(event.absolute), focused)
            captor = None if claim is None else claim.key
            return Press(buttons=frozenset({button}), captor=captor), claimed_controls(claim)
        case MouseMoved(button=None):
            return None, claimed_controls(table.bubble(event, table.target_at(event.absolute), focused))
        case MouseMoved():
            return press, () if press is None else captured(event, press, focused, table)
        case MouseUp(button=button):
            if press is None or button not in press.buttons:
                return press, ()
            held = press.buttons - {button}
            return (Press(buttons=held, captor=press.captor) if held else None), captured(event, press, focused, table)
        case _ as unreachable:
            assert_never(unreachable)


def captured(event: MouseEvent, press: Press, focused: NodeKey | None, table: RoutingTable) -> tuple[AnyControl, ...]:
    """Delivers a later event of `press` to its captor, or to no handler if nothing claimed the press."""
    return () if press.captor is None else table.deliver(event, press.captor, focused)


def claimed_controls(claim: Claim | None) -> tuple[AnyControl, ...]:
    """The controls of `claim`, or none if nothing claimed the event."""
    return () if claim is None else claim.controls
