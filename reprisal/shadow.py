from __future__ import annotations

from collections.abc import Iterator
from itertools import zip_longest

from pydantic import Field

from reprisal._context_vars import current_hook_idx, current_hook_state
from reprisal.components import AnyElement, Component, Element
from reprisal.hooks.impls import Hooks
from reprisal.types import FrozenForbidExtras


class ShadowNode(FrozenForbidExtras):
    component: Component
    element: AnyElement
    children: list[ShadowNode | Element] = Field(default_factory=list)
    hooks: Hooks

    def walk(self) -> Iterator[ShadowNode]:
        yield self
        for child in self.children:
            if isinstance(child, ShadowNode):
                yield from child.walk()

    def concrete_element_tree(self) -> AnyElement:
        return self.element.copy(
            update={
                "children": [child.element if isinstance(child, ShadowNode) else child for child in self.children],
            }
        )


def render_shadow_node_from_previous(component: Component, previous: ShadowNode | None) -> ShadowNode:
    if previous is None or component.func != previous.component.func:
        reset_current_hook_idx = current_hook_idx.set(0)

        hook_state = Hooks()
        reset_current_hook_state = current_hook_state.set(hook_state)

        element = component.func(*component.args, **component.kwargs)

        children: list[ShadowNode | Element] = []
        for child in element.children:
            if isinstance(child, Component):
                children.append(render_shadow_node_from_previous(child, None))
            else:
                children.append(child)

        new = ShadowNode(
            component=component,
            element=element,
            children=children,
            hooks=hook_state,
        )
    else:
        reset_current_hook_idx = current_hook_idx.set(0)

        reset_current_hook_state = current_hook_state.set(previous.hooks)

        element = component.func(*component.args, **component.kwargs)

        children = []
        for new_child, previous_child in zip_longest(element.children, previous.children):
            if isinstance(new_child, Component):
                if isinstance(previous_child, ShadowNode):
                    children.append(render_shadow_node_from_previous(new_child, previous_child))
                else:
                    children.append(render_shadow_node_from_previous(new_child, None))
            else:
                children.append(new_child)

        new = ShadowNode(
            component=component,
            element=element,
            children=children,
            hooks=previous.hooks,  # the hooks are mutable and carry through renders
        )

    current_hook_idx.reset(reset_current_hook_idx)
    current_hook_state.reset(reset_current_hook_state)

    return new
