"""
Which handlers an input event reaches, given the last render's shadow tree and layouts,
with its scrolls moved by the scroll controls since:
the event's target, the ancestors it bubbles to from there, and the node that captured a press;
and where focus can go, given the same tree.
Handlers run here, but what their controls do is up to the render loop, which holds the focused key.
"""

from __future__ import annotations

from collections.abc import Collection
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import replace
from typing import TYPE_CHECKING
from typing import assert_never

from counterweight.controls import AnyControl
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollTo
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseEvent
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.events import response_controls
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.geometry import Position
from counterweight.geometry import Scroll
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
    element_keys: Mapping[ElementHandle, NodeKey]
    """The key of every mounted element given a `handle`, by its handle."""
    scrolls: Mapping[NodeKey, Scroll]
    """
    The scroll of every visible scroll container, as the render laid it out
    and as the `ScrollTo` and `ScrollBy` controls since have moved it, which is what receivers carry.
    """

    @classmethod
    def of(cls, shadow: ShadowTree, layouts: Layouts) -> RoutingTable:
        """The table for `shadow`, whose root is the screen element, and the `layouts` computed from it."""
        (root,) = shadow.root.children

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
                key: element.on_input for key, element, _, _ in layouts.in_paint_order if element.on_input is not None
            },
            focus=focus,
            focus_keys={focusable.handle: key for key, focusable in focus.items() if focusable.is_focusable},
            element_keys=shadow.handled,
            scrolls=layouts.scrolls,
        )

    def target_at(self, position: Position) -> NodeKey:
        """
        The topmost element painted at `position`, the last in paint order whose border box contains it
        inside its clip, or the root component's node if that's only the screen.
        """
        for key, _, layout, _ in reversed(self.layouts.in_paint_order):
            if (visible := layout.visible) is not None and visible.contains(position):
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
            rects=self.layouts.by_key[key],
            is_target=is_target,
            focus_handle=None if focus is None else focus.handle,
            is_focused=key == focused,
            subtree=Subtree(key=key),
            scroll=self.scrolls.get(key),
        )
        return response_controls(handler(event, receiver))

    def key_of(self, target: ElementHandle | Subtree) -> NodeKey | None:
        """The key of the element `target` names, or `None` for a handle that names no mounted element."""
        return named_key(target, self.element_keys)

    def scrolled(self, control: ScrollTo | ScrollBy) -> RoutingTable:
        """
        This table with the scroll container `control` names moved as it moves it,
        clamped to how far the container scrolled when it was laid out,
        or this table itself if that leaves it where it is, or `control` names no visible scroll container.
        """
        key = self.key_of(control.target)
        if key is None or (scroll := self.scrolls.get(key)) is None:
            return self
        if (moved := scroll.clamp(control.destination(scroll.offset))) == scroll.offset:
            return self
        return replace(self, scrolls={**self.scrolls, key: replace(scroll, offset=moved)})

    def can_focus(self, key: NodeKey) -> bool:
        """Whether the node with `key` is visible, and its last run called `use_focus` with `is_focusable=True`."""
        return (focus := self.focus.get(key)) is not None and focus.is_focusable

    def contains(self, subtree: Subtree, key: NodeKey) -> bool:
        """Whether the node with `key` is `subtree`'s node or one of its descendants."""
        return subtree.key in self.path(key)

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

    def reconciled_focus(
        self, focused: NodeKey | None, mounted: Collection[NodeKey], requested: FocusHandle | None
    ) -> NodeKey | None:
        """
        The focused key after a render that built this table and `mounted` the components with those keys:
        the node with the `requested` handle, from a `FocusOn` that named no focusable node before the render,
        if it's focusable now.
        Otherwise it's `focused`, unless it can no longer be focused because it unmounted, is hidden, or is unfocusable,
        in which case it's cleared.
        Then, if nothing is focused, it's the first focusable node in tree order that mounted with `auto_focus`.
        """
        if requested is not None and (key := self.focus_keys.get(requested)) is not None:
            return key
        if focused is not None and self.can_focus(focused):
            return focused
        return next(
            (key for key, focus in self.focus.items() if focus.auto_focus and focus.is_focusable and key in mounted),
            None,
        )


def named_key(target: ElementHandle | Subtree, element_keys: Mapping[ElementHandle, NodeKey]) -> NodeKey | None:
    """
    The key of the element `target` names, given the key of every mounted element with a handle, by its handle,
    or `None` for a handle that names no mounted element.
    """
    match target:
        case ElementHandle():
            return element_keys.get(target)
        case Subtree(key=key):
            return key
        case _ as unreachable:
            assert_never(unreachable)


def route_key(
    event: KeyPressed | Pasted,
    focused: NodeKey | None,
    table: RoutingTable,
    unclaimed_keys: Mapping[str, AnyControl],
) -> tuple[AnyControl, ...]:
    """
    Bubbles a key press or paste from the `focused` node, or from the root component's node if nothing is focused,
    and returns the controls of the handler that claimed it,
    or, for a key press no handler claimed, its control in `unclaimed_keys`, if it has one,
    as a browser takes a key's default action unless a listener prevents it.
    """
    claim = table.bubble(event, table.root if focused is None else focused, focused)
    if claim is not None:
        return claim.controls
    if isinstance(event, KeyPressed) and (control := unclaimed_keys.get(event.key)) is not None:
        return (control,)
    return ()


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
        case MouseScrolledDown() | MouseScrolledUp() | MouseScrolledLeft() | MouseScrolledRight():
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
