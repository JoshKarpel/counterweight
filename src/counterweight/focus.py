"""
The values that name what a control acts on: which component to focus, which element to scroll,
and which part of the tree to move focus in.
They live outside the hooks and elements modules, since controls and events name them,
and those modules import both.
Beside them are the errors a render raises when two mounted nodes share a handle, or focus won't settle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from counterweight.hooks.impls import NodeKey


@dataclass(frozen=True, slots=True, eq=False, repr=False)
class FocusHandle:
    """
    An opaque token that names one focusable component, for [`FocusOn`][counterweight.controls.FocusOn].

    It's an identity token, equal only to itself, so it can exist before the component it names has mounted:
    a parent creates one with `use_state(FocusHandle)` and passes it to the child's
    [`use_focus`][counterweight.hooks.use_focus].
    """

    def __repr__(self) -> str:
        """Names the handle by its identity, since that's all that tells two handles apart."""
        return f"<FocusHandle at {id(self):#x}>"


@dataclass(frozen=True, slots=True, eq=False, repr=False)
class ElementHandle:
    """
    An opaque token that names one element, as a React ref names a DOM node:
    a scroll container for [`ScrollTo`][counterweight.controls.ScrollTo], [`ScrollBy`][counterweight.controls.ScrollBy]
    and [`use_scroll`][counterweight.hooks.use_scroll], or an element to bring into view with
    [`ScrollIntoView`][counterweight.controls.ScrollIntoView],
    such as the cursor's row a text area draws with its [`cursor_row`][counterweight.headless.TextArea.cursor_row].

    It's an identity token, equal only to itself, so it can exist before the element it names has mounted:
    a component creates one with `use_state(ElementHandle)` and passes it to an element's `handle`.
    Two mounted elements given the same handle raise `DuplicateElementHandle`.
    """

    def __repr__(self) -> str:
        """Names the handle by its identity, since that's all that tells two handles apart."""
        return f"<ElementHandle at {id(self):#x}>"


@dataclass(frozen=True, slots=True)
class Subtree:
    """
    An opaque name for an element and its descendants,
    which [`FocusNext`][counterweight.controls.FocusNext] and [`FocusPrevious`][counterweight.controls.FocusPrevious]
    take to move focus only among the focusable components inside it.
    [`ScrollTo`][counterweight.controls.ScrollTo], [`ScrollBy`][counterweight.controls.ScrollBy],
    [`ScrollIntoView`][counterweight.controls.ScrollIntoView],
    [`page_down`][counterweight.handlers.page_down] and [`page_up`][counterweight.handlers.page_up]
    take one in place of an [`ElementHandle`][counterweight.focus.ElementHandle], to name the element itself,
    so a handler can scroll its own element without a handle.
    A handler gets its own element's from its [`Receiver`][counterweight.events.Receiver].
    """

    key: NodeKey


class DuplicateElementHandle(Exception):
    """Raised when two mounted elements are given the same `ElementHandle`, which leaves it naming neither."""


class DuplicateFocusHandle(Exception):
    """Raised when two mounted components are given the same `FocusHandle`, which leaves it naming neither."""


class UnsettledFocus(Exception):
    """
    Raised when re-rendering the components whose focus a render changed changes focus again,
    which only a component that hides itself because it gained focus can cause:
    one that lost focus already rendered unfocused if it became unfocusable, and draws nothing if it's hidden.
    """
