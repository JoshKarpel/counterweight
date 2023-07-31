from __future__ import annotations

from collections.abc import Iterator
from itertools import zip_longest

from pydantic import Field
from structlog import get_logger

from reprisal._context_vars import current_hook_idx, current_hook_state
from reprisal.components import AnyElement, Component
from reprisal.hooks.impls import Hooks
from reprisal.types import FrozenForbidExtras

logger = get_logger()


class ShadowNode(FrozenForbidExtras):
    component: Component | None
    element: AnyElement
    children: list[ShadowNode] = Field(default_factory=list)
    hooks: Hooks

    def walk(self) -> Iterator[ShadowNode]:
        yield self
        for child in self.children:
            if isinstance(child, ShadowNode):
                yield from child.walk()


def update_shadow(next: Component | AnyElement, previous: ShadowNode | None) -> ShadowNode:
    if previous is not None and (
        (  # if the keys are not None, and they match, then we can reuse the previous component
            previous.component is not None
            and isinstance(next, Component)
            and next.key is not None
            and previous.component.key is not None
            and next.key == previous.component.key
        )  # we can also reuse the previous component if there are no changes except possibly in props
        or (previous.component is not None and isinstance(next, Component) and next.func == previous.component.func)
    ):
        reset_current_hook_idx = current_hook_idx.set(0)

        reset_current_hook_state = current_hook_state.set(previous.hooks)

        # we already know next is a Component here
        element = next.func(*next.args, **next.kwargs)

        children = []
        for new_child, previous_child in zip_longest(element.children, previous.children):
            if new_child is None:
                continue
            children.append(update_shadow(new_child, previous_child))

        new = ShadowNode(
            component=next if isinstance(next, Component) else None,
            element=element,
            children=children,
            hooks=previous.hooks,  # the hooks are mutable and carry through renders
        )
    else:
        # start from scratch
        reset_current_hook_idx = current_hook_idx.set(0)

        hook_state = Hooks()
        reset_current_hook_state = current_hook_state.set(hook_state)

        if isinstance(next, Component):
            element = next.func(*next.args, **next.kwargs)
        else:
            element = next

        children = [update_shadow(child, None) for child in element.children]

        new = ShadowNode(
            component=next if isinstance(next, Component) else None,
            element=element,
            children=children,
            hooks=hook_state,
        )

    current_hook_idx.reset(reset_current_hook_idx)
    current_hook_state.reset(reset_current_hook_state)

    return new
