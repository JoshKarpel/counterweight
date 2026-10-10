from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from time import perf_counter_ns

from structlog import get_logger

from counterweight._context_vars import current_hook_idx, current_hook_state
from counterweight.components import Component
from counterweight.elements import AnyElement
from counterweight.hooks.impls import Hooks, InconsistentHookExecution

logger = get_logger()


@dataclass(slots=True)
class ShadowNode:
    component: Component | None
    element: AnyElement
    hooks: Hooks
    children: list[ShadowNode] = field(default_factory=list)

    def walk(self) -> Iterator[ShadowNode]:
        """Yields every node in the subtree in pre-order, with an explicit stack so cost is linear in node count."""
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))


class DuplicateKey(Exception):
    """Raised when keyed sibling components share a key, which leaves no single previous child for each to continue."""


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
            previous_hook_count = len(previous_hooks.data)
            reset_current_hook_idx = current_hook_idx.set(0)
            reset_current_hook_state = current_hook_state.set(previous_hooks)
            try:
                _start = perf_counter_ns()
                element = next_component.func(*next_args, **next_kwargs)
                user_ns += perf_counter_ns() - _start
                hook_count = current_hook_idx.get()
            finally:
                current_hook_idx.reset(reset_current_hook_idx)
                current_hook_state.reset(reset_current_hook_state)

            if hook_count != previous_hook_count:
                raise InconsistentHookExecution(
                    f"{next_func.__name__} called {hook_count} hooks on this render, "
                    f"but {previous_hook_count} on its previous render. "
                    "A component must call the same hooks in the same order on every render."
                )

            children, children_ns = reconcile_children(element.children, previous_children)
            user_ns += children_ns

            new = ShadowNode(
                component=next_component,
                element=element,
                children=children,
                hooks=previous_hooks,  # the hooks are mutable and carry through renders
            )

            # logger.debug(
            #     "Updated shadow node",
            #     type="component",
            #     id=id,
            #     generation=new.generation,
            # )
        case Component(func=next_func, args=next_args, kwargs=next_kwargs) as next_component, _:
            hook_state = Hooks()
            reset_current_hook_idx = current_hook_idx.set(0)
            reset_current_hook_state = current_hook_state.set(hook_state)
            try:
                _start = perf_counter_ns()
                element = next_func(*next_args, **next_kwargs)
                user_ns += perf_counter_ns() - _start
            finally:
                current_hook_idx.reset(reset_current_hook_idx)
                current_hook_state.reset(reset_current_hook_state)

            children, children_ns = reconcile_children(element.children, [])
            user_ns += children_ns

            new = ShadowNode(
                component=next_component,
                element=element,
                children=children,
                hooks=hook_state,
            )
        case element, ShadowNode(
            component=None,
            children=previous_children,
            hooks=previous_hooks,
        ):
            children, children_ns = reconcile_children(element.children, previous_children)
            user_ns += children_ns

            new = ShadowNode(
                component=None,
                element=element,
                children=children,
                hooks=previous_hooks,  # the hooks are mutable and carry through renders
            )
        case element, None | ShadowNode():
            children, children_ns = reconcile_children(element.children, [])
            user_ns += children_ns

            new = ShadowNode(
                component=None,
                element=element,
                children=children,
                hooks=Hooks(),
            )
        case _:
            # Not assert_never: mypy narrows this tuple match unsoundly to tuple[Never, Never], even with an arm missing.
            raise Exception("Unreachable!")

    return new, user_ns


def mark_unmounted(previous: ShadowNode, current: ShadowNode) -> None:
    """
    Marks the hooks of every node in `previous` that didn't carry over into `current` as unmounted,
    so a setter captured by an unmounted component stops triggering renders.
    Hooks are compared by `id()` because they are mutable, and so unhashable.
    """
    current_hook_ids = {id(node.hooks) for node in current.walk()}
    for node in previous.walk():
        if id(node.hooks) not in current_hook_ids:
            node.hooks.mount_status.is_mounted = False


def reconcile_children(
    next_children: Sequence[Component | AnyElement], previous_children: Sequence[ShadowNode]
) -> tuple[list[ShadowNode], int]:
    """
    Pairs each next child with the previous child it continues, as React does:
    a keyed child with the previous sibling that had the same key, wherever it was,
    and an unkeyed child with the unkeyed previous sibling at the same index.
    Returns the reconciled children and the nanoseconds spent in user component functions.
    """
    previous_by_key: dict[str | int, ShadowNode] = {}
    previous_by_index: dict[int, ShadowNode] = {}
    for index, node in enumerate(previous_children):
        if node.component is not None and node.component.key is not None:
            previous_by_key[node.component.key] = node
        else:
            previous_by_index[index] = node

    seen_keys: set[str | int] = set()
    children = []
    user_ns = 0
    for index, next_child in enumerate(next_children):
        if isinstance(next_child, Component) and next_child.key is not None:
            if next_child.key in seen_keys:
                raise DuplicateKey(f"Sibling components share the key {next_child.key!r}")
            seen_keys.add(next_child.key)
            previous_child = previous_by_key.get(next_child.key)
        else:
            previous_child = previous_by_index.get(index)

        child_node, child_ns = update_shadow(next_child, previous_child)
        children.append(child_node)
        user_ns += child_ns

    return children, user_ns
