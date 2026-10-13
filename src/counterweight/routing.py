"""
Which handlers an input event reaches, given the last render's shadow tree and layouts:
the event's target, the ancestors it bubbles to from there, and the node that captured a press.
Handlers run here, but what their controls do is up to the render loop.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
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

    @classmethod
    def of(cls, shadow: ShadowTree, layouts: Layouts) -> RoutingTable:
        """The table for `shadow`, whose root is the screen element, and the `layouts` computed from it."""
        (root,) = shadow.root.children
        return cls(
            screen=shadow.root.key,
            root=root.key,
            layouts=layouts,
            parents=shadow.parents,
            handlers={
                key: element.on_input for key, element, _ in layouts.in_paint_order if element.on_input is not None
            },
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

    def bubble(self, event: InputEvent, target: NodeKey) -> Claim | None:
        """
        Calls the handlers on `target`'s path in turn, until one responds with something other than `None`,
        or `None` if none does.
        """
        for key in self.path(target):
            if (controls := self.call(key, event, is_target=key == target)) is not None:
                return Claim(key=key, controls=controls)
        return None

    def deliver(self, event: InputEvent, key: NodeKey) -> tuple[AnyControl, ...]:
        """Calls `key`'s handler alone, as the event's target, and returns its controls whatever it responds."""
        return self.call(key, event, is_target=True) or ()

    def call(self, key: NodeKey, event: InputEvent, is_target: bool) -> tuple[AnyControl, ...] | None:
        """
        The controls `key`'s handler responds to `event` with,
        or `None` if it doesn't handle the event, or if the node has no handler, is hidden, or has unmounted.
        """
        if (handler := self.handlers.get(key)) is None:
            return None
        receiver = Receiver(rects=self.layouts.by_key[key].rects, is_target=is_target)
        return response_controls(handler(event, receiver))


def route_key(event: KeyPressed, table: RoutingTable) -> tuple[AnyControl, ...]:
    """Calls every visible handler, topmost first, each as the target, and returns all their controls."""
    return tuple(
        control
        for key, _, _ in reversed(table.layouts.in_paint_order)
        for control in table.call(key, event, is_target=True) or ()
    )


def route_mouse(
    event: MouseEvent, captor: NodeKey | None, table: RoutingTable
) -> tuple[NodeKey | None, tuple[AnyControl, ...]]:
    """
    Routes `event` given the node that captured the press in progress, if any,
    and returns the captor for the next event with the controls the handlers returned.

    A `MouseDown` hit-tests and bubbles, and the node that claims it captures the press:
    the press's later events, each `MouseMoved` with a button held and the `MouseUp`,
    go to that node alone, wherever the pointer is, and stop there whatever it responds.
    The rest of a press nothing claimed, or whose captor has unmounted, reaches no handler,
    so an element never receives the end of a press it didn't see begin.
    A `MouseMoved` with no button held ends a press whose release the terminal never reported.
    Wheel events aren't part of a press, and always hit-test.
    """
    match event:
        case MouseScrolledDown() | MouseScrolledUp():
            return captor, claimed_controls(table.bubble(event, table.target_at(event.absolute)))
        case MouseDown():
            claim = table.bubble(event, table.target_at(event.absolute))
            return (None if claim is None else claim.key), claimed_controls(claim)
        case MouseMoved(button=None):
            return None, claimed_controls(table.bubble(event, table.target_at(event.absolute)))
        case MouseMoved():
            return captor, () if captor is None else table.deliver(event, captor)
        case MouseUp():
            return None, () if captor is None else table.deliver(event, captor)
        case _ as unreachable:
            assert_never(unreachable)


def claimed_controls(claim: Claim | None) -> tuple[AnyControl, ...]:
    """The controls of `claim`, or none if nothing claimed the event."""
    return () if claim is None else claim.controls
