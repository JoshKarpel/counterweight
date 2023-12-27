from __future__ import annotations

from collections.abc import Iterator
from itertools import count, zip_longest

from pydantic import Field
from structlog import get_logger

from counterweight._context_vars import current_hook_idx, current_hook_state
from counterweight.components import Component
from counterweight.elements import AnyElement
from counterweight.hooks.impls import Hooks
from counterweight.types import FrozenForbidExtras

logger = get_logger()

next_id = count(0)


class ShadowNode(FrozenForbidExtras):
    id: int = Field(default_factory=lambda: next(next_id))
    generation: int = 0
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
    match next, previous:
        case Component(
            func=next_func,
            args=next_args,
            kwargs=next_kwargs,
            key=next_key,
        ) as next_component, ShadowNode(
            id=id,
            generation=generation,
            component=previous_component,
            children=previous_children,
            hooks=previous_hooks,
        ) if (
            previous_component is not None
            and next_func == previous_component.func
            and next_key == previous_component.key
        ):
            reset_current_hook_idx = current_hook_idx.set(0)
            reset_current_hook_state = current_hook_state.set(previous_hooks)

            element = next_component.func(*next_args, **next_kwargs)

            children = []
            for new_child, previous_child in zip_longest(element.children, previous_children):
                if new_child is None:
                    continue
                children.append(update_shadow(new_child, previous_child))

            new = ShadowNode(
                id=id,
                component=next_component,
                element=element,
                children=children,
                hooks=previous_hooks,  # the hooks are mutable and carry through renders
                generation=generation + 1,
            )

            current_hook_idx.reset(reset_current_hook_idx)
            current_hook_state.reset(reset_current_hook_state)

            logger.debug(
                "Updated shadow node",
                type="component",
                id=id,
                generation=new.generation,
            )
        case Component(func=next_func, args=next_args, kwargs=next_kwargs) as next_component, _:
            reset_current_hook_idx = current_hook_idx.set(0)

            hook_state = Hooks()
            reset_current_hook_state = current_hook_state.set(hook_state)

            element = next_func(*next_args, **next_kwargs)

            children = [update_shadow(child, None) for child in element.children]

            new = ShadowNode(
                component=next_component,
                element=element,
                children=children,
                hooks=hook_state,
            )

            current_hook_idx.reset(reset_current_hook_idx)
            current_hook_state.reset(reset_current_hook_state)
        case element, ShadowNode(
            children=previous_children,
            hooks=previous_hooks,
        ):
            children = []
            for new_child, previous_child in zip_longest(element.children, previous_children):
                if new_child is None:
                    continue
                children.append(update_shadow(new_child, previous_child))

            new = ShadowNode(
                component=None,
                element=element,
                children=children,
                hooks=previous_hooks,  # the hooks are mutable and carry through renders
            )
        case element, None:
            new = ShadowNode(
                component=None,
                element=element,
                children=[update_shadow(child, None) for child in element.children],
                hooks=Hooks(),
            )
        case _:
            raise Exception("Unreachable!")

    return new
