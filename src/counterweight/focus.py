"""
The values that name focus targets: which component a control should focus, and which part of the tree to move it in.
They live outside the hooks package, since controls and events name them, and the hooks package imports both.
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


@dataclass(frozen=True, slots=True)
class Subtree:
    """
    An opaque name for an element and its descendants,
    which [`FocusNext`][counterweight.controls.FocusNext] and [`FocusPrevious`][counterweight.controls.FocusPrevious]
    take to move focus only among the focusable components inside it.
    A handler gets one from its [`Receiver`][counterweight.events.Receiver].
    """

    key: NodeKey
