from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import zip_longest
from time import perf_counter_ns

from structlog import get_logger

from counterweight._context_vars import current_hook_idx, current_hook_state
from counterweight.components import Component
from counterweight.elements import AnyElement
from counterweight.hooks.impls import Hooks

logger = get_logger()


@dataclass(slots=True)
class ShadowNode:
    component: Component | None
    element: AnyElement
    hooks: Hooks
    children: list[ShadowNode] = field(default_factory=list)

    def walk(self) -> Iterator[ShadowNode]:
        yield self
        for child in self.children:
            if isinstance(child, ShadowNode):
                yield from child.walk()


def update_shadow(next: Component | AnyElement, previous: ShadowNode | None) -> tuple[ShadowNode, int]:
    """Returns the updated shadow node and the nanoseconds spent in user component functions."""
    user_ns = 0
    match next, previous:
        case Component(
            func=next_func,
            args=next_args,
            kwargs=next_kwargs,
            key=next_key,
        ) as next_component, ShadowNode(
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

            _start = perf_counter_ns()
            element = next_component.func(*next_args, **next_kwargs)
            user_ns += perf_counter_ns() - _start

            children = []
            for new_child, previous_child in zip_longest(element.children, previous_children):
                if new_child is None:
                    continue
                child_node, child_ns = update_shadow(new_child, previous_child)
                children.append(child_node)
                user_ns += child_ns

            new = ShadowNode(
                component=next_component,
                element=element,
                children=children,
                hooks=previous_hooks,  # the hooks are mutable and carry through renders
            )

            current_hook_idx.reset(reset_current_hook_idx)
            current_hook_state.reset(reset_current_hook_state)

            # logger.debug(
            #     "Updated shadow node",
            #     type="component",
            #     id=id,
            #     generation=new.generation,
            # )
        case Component(func=next_func, args=next_args, kwargs=next_kwargs) as next_component, _:
            reset_current_hook_idx = current_hook_idx.set(0)

            hook_state = Hooks()
            reset_current_hook_state = current_hook_state.set(hook_state)

            _start = perf_counter_ns()
            element = next_func(*next_args, **next_kwargs)
            user_ns += perf_counter_ns() - _start

            children = []
            for child in element.children:
                child_node, child_ns = update_shadow(child, None)
                children.append(child_node)
                user_ns += child_ns

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
                child_node, child_ns = update_shadow(new_child, previous_child)
                children.append(child_node)
                user_ns += child_ns

            new = ShadowNode(
                component=None,
                element=element,
                children=children,
                hooks=previous_hooks,  # the hooks are mutable and carry through renders
            )
        case element, None:
            children = []
            for child in element.children:
                child_node, child_ns = update_shadow(child, None)
                children.append(child_node)
                user_ns += child_ns

            new = ShadowNode(
                component=None,
                element=element,
                children=children,
                hooks=Hooks(),
            )
        case _:
            raise Exception("Unreachable!")

    return new, user_ns
