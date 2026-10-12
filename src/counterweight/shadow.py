from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from itertools import chain

from counterweight._context_vars import current_hook_idx, current_hook_state, current_layouts, current_purity_checked
from counterweight.components import Component
from counterweight.elements import AnyElement
from counterweight.equivalence import equivalent
from counterweight.hooks.hooks import rects_in
from counterweight.hooks.impls import Hooks, InconsistentHookExecution, NodeKey
from counterweight.layout import Layouts

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShadowNode:
    component: Component | None
    element: AnyElement
    hooks: Hooks
    children: tuple[ShadowNode, ...] = ()

    @property
    def key(self) -> NodeKey:
        return self.hooks.key

    def walk(self) -> Iterator[ShadowNode]:
        """Yields every node in the subtree in pre-order, with an explicit stack so cost is linear in node count."""
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))


@dataclass(frozen=True, slots=True)
class ShadowUpdate:
    """
    One frame's shadow tree, with the hooks of the components that ran to build it
    and of every previous node it unmounted, so effects can follow exactly the renders that happened.
    """

    tree: ShadowNode
    ran: tuple[Hooks, ...]
    unmounted: tuple[Hooks, ...]


class DuplicateKey(Exception):
    """Raised when keyed sibling components share a key, which leaves no single previous child for each to continue."""


class ImpureComponent(Exception):
    """
    Raised when `check_purity` is on and a component that a render didn't re-run
    returns something different when called again with the same arguments and hooks,
    so its output depends on something else and the output the render kept is stale.
    """


def is_dirty(node: ShadowNode, dirty: frozenset[NodeKey], layouts: Layouts) -> bool:
    """
    Whether `node` has to re-run whatever its parent does:
    its state was set, or the rectangles `use_rects` last returned to it have moved since.
    """
    return node.key in dirty or (node.hooks.rects is not None and node.hooks.rects != rects_in(layouts, node.key))


def dirty_paths(
    tree: ShadowNode, dirty: frozenset[NodeKey], layouts: Layouts
) -> tuple[frozenset[NodeKey], frozenset[NodeKey]]:
    """
    The keys of every dirty node in `tree` (see `is_dirty`),
    and the paths to them: those keys and the keys of all their ancestors.
    """
    dirty_nodes: set[NodeKey] = set()
    paths: set[NodeKey] = set()
    parents: dict[NodeKey, NodeKey] = {}
    stack = [tree]
    while stack:
        node = stack.pop()
        for child in node.children:
            parents[child.key] = node.key
        stack.extend(node.children)

        if not is_dirty(node, dirty, layouts):
            continue

        dirty_nodes.add(node.key)
        key: NodeKey | None = node.key
        while key is not None and key not in paths:
            paths.add(key)
            key = parents.get(key)

    return frozenset(dirty_nodes), frozenset(paths)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What one `update_shadow` call reads, and the hooks it collects as it goes."""

    layouts: Layouts
    dirty_nodes: frozenset[NodeKey]
    paths: frozenset[NodeKey]
    check_purity: bool
    ran: list[Hooks] = field(default_factory=list)
    unmounted: list[Hooks] = field(default_factory=list)


def update_shadow(
    next: Component | AnyElement,
    previous: ShadowNode | None,
    layouts: Layouts,
    dirty: frozenset[NodeKey] = frozenset(),
    check_purity: bool = False,
) -> ShadowUpdate:
    """
    Builds the next shadow tree from `previous`, re-running only the components that have to:
    those in `dirty` or whose rectangles moved (see `is_dirty`), and those whose parent passed them a new `Component`,
    unless it's a `memo` component equal to its previous one (see `continues`).
    A component that doesn't re-run keeps its previous node, whole subtree included,
    unless a dirty node is below it, in which case its children are reconciled again to reach it.
    `layouts` are the previous frame's, which `use_rects` reads.
    With `check_purity`, every component that doesn't re-run is also called, and raises `ImpureComponent`
    if what it returns isn't equivalent to the element it kept (see `check_is_pure`).
    """
    dirty_nodes, paths = (frozenset(), frozenset()) if previous is None else dirty_paths(previous, dirty, layouts)
    reconciliation = Reconciliation(layouts=layouts, dirty_nodes=dirty_nodes, paths=paths, check_purity=check_purity)
    tree = update_node(next, previous, reconciliation)

    if check_purity:
        ran = {hooks.key for hooks in reconciliation.ran}
        for node in tree.walk():
            if node.key not in ran:
                check_is_pure(node, layouts)

    return ShadowUpdate(tree=tree, ran=tuple(reconciliation.ran), unmounted=tuple(reconciliation.unmounted))


def update_node(
    next: Component | AnyElement, previous: ShadowNode | None, reconciliation: Reconciliation
) -> ShadowNode:
    """
    Returns the updated shadow node, marking every previous node that the new tree doesn't continue as unmounted.
    """
    match next, previous:
        case Component(
            func=next_func,
            key=next_key,
        ) as next_component, ShadowNode(
            component=previous_component,
            element=previous_element,
            children=previous_children,
            hooks=previous_hooks,
        ) as previous_node if (
            previous_component is not None
            and next_func == previous_component.func
            and next_key == previous_component.key
        ):
            if not continues(next_component, previous_component) or previous_node.key in reconciliation.dirty_nodes:
                previous_hook_count = len(previous_hooks.data)
                element, hook_count = call_component(
                    next_component, previous_hooks, reconciliation.layouts, reconciliation.check_purity
                )
                reconciliation.ran.append(previous_hooks)

                if hook_count != previous_hook_count:
                    raise InconsistentHookExecution(
                        f"{next_func} called {hook_count} hooks on this render, "
                        f"but {previous_hook_count} on its previous render. "
                        "A component must call the same hooks in the same order on every render."
                    )

                new = ShadowNode(
                    component=next_component,
                    element=element,
                    children=reconcile_children(element.children, previous_children, reconciliation),
                    hooks=previous_hooks,  # the hooks are mutable and carry through renders
                )
            elif previous_node.key not in reconciliation.paths:
                new = previous_node
            else:
                new = ShadowNode(
                    component=previous_component,
                    element=previous_element,
                    children=reconcile_children(previous_element.children, previous_children, reconciliation),
                    hooks=previous_hooks,
                )
        case Component() as next_component, _:
            hook_state = Hooks()
            element, _ = call_component(next_component, hook_state, reconciliation.layouts, reconciliation.check_purity)
            reconciliation.ran.append(hook_state)

            new = ShadowNode(
                component=next_component,
                element=element,
                children=reconcile_children(element.children, (), reconciliation),
                hooks=hook_state,
            )
        case element, ShadowNode(
            component=None,
            element=previous_element,
            children=previous_children,
            hooks=previous_hooks,
        ) as previous_node:
            if element is previous_element and previous_node.key not in reconciliation.paths:
                new = previous_node
            else:
                new = ShadowNode(
                    component=None,
                    element=element,
                    children=reconcile_children(element.children, previous_children, reconciliation),
                    hooks=previous_hooks,  # the hooks are mutable and carry through renders
                )
        case element, None | ShadowNode():
            new = ShadowNode(
                component=None,
                element=element,
                children=reconcile_children(element.children, (), reconciliation),
                hooks=Hooks(),
            )
        case _:
            # Not assert_never: mypy narrows this tuple match unsoundly to tuple[Never, Never], even with an arm missing.
            raise Exception("Unreachable!")

    # A previous node is continued exactly when its hooks carry over.
    if previous is not None and new.hooks is not previous.hooks:
        unmount(previous, reconciliation)

    return new


def continues(next: Component, previous: Component) -> bool:
    """
    Whether `next` continues `previous` without re-running for its own sake:
    it's the same object, which a parent that didn't re-run hands its children,
    or it's a `memo` component equal to `previous`, which compares its function, arguments and key.
    """
    return next is previous or (next.memo and next == previous)


def check_is_pure(node: ShadowNode, layouts: Layouts) -> None:
    """
    Calls a reused node's component again, against its `Hooks.detached` hooks, and raises `ImpureComponent`
    if the element it returns isn't `equivalent` to the one the node kept.
    It compares child components without calling them; each reused child is checked on its own node.
    """
    if node.component is None:
        return

    element, _ = call_component(node.component, node.hooks.detached(), layouts, check_purity=True)
    if not equivalent(element, node.element):
        raise ImpureComponent(
            f"{node.component.func.__qualname__} returned a different element when called again "
            "with the same arguments and hooks, so it depends on something else, such as a module-level value, "
            "and the output kept from its last run is stale. "
            "A component must depend only on its arguments and its hooks."
        )


def call_component(component: Component, hooks: Hooks, layouts: Layouts, check_purity: bool) -> tuple[AnyElement, int]:
    """
    Calls a component function with `hooks` as the current hook state and the previous frame's `layouts`,
    restoring the outer hook context even if it raises.
    With `check_purity`, each `use_memo` that keeps its cached value also checks it (see `Hooks.use_memo`).
    Returns the element and how many hooks it called.
    """
    reset_current_hook_idx = current_hook_idx.set(0)
    reset_current_hook_state = current_hook_state.set(hooks)
    reset_current_layouts = current_layouts.set(layouts)
    reset_current_purity_checked = current_purity_checked.set(component if check_purity else None)
    # use_rects isn't positional, so a run that stops calling it must stop the node re-running when its layout moves.
    hooks.rects = None
    try:
        element = component.func(*component.args, **component.kwargs)
        return element, current_hook_idx.get()
    finally:
        current_hook_idx.reset(reset_current_hook_idx)
        current_hook_state.reset(reset_current_hook_state)
        current_layouts.reset(reset_current_layouts)
        current_purity_checked.reset(reset_current_purity_checked)


def unmount(discarded: ShadowNode, reconciliation: Reconciliation) -> None:
    """
    Marks every node in a subtree that the new tree discards as unmounted,
    so a setter captured by an unmounted component stops triggering renders, and collects their hooks.
    """
    for node in discarded.walk():
        node.hooks.mount_status.is_mounted = False
        reconciliation.unmounted.append(node.hooks)


def reconcile_children(
    next_children: Sequence[Component | AnyElement],
    previous_children: Sequence[ShadowNode],
    reconciliation: Reconciliation,
) -> tuple[ShadowNode, ...]:
    """
    Pairs each next child with the previous child it continues, as React does:
    a keyed child with the previous sibling that had the same key, wherever it was,
    and an unkeyed child with the unkeyed previous sibling at the same index.
    Previous children that no next child continues are unmounted.
    """
    if not next_children and not previous_children:
        return ()

    previous_by_key: dict[str, ShadowNode] = {}
    previous_by_index: dict[int, ShadowNode] = {}
    for index, node in enumerate(previous_children):
        if node.component is not None and node.component.key is not None:
            previous_by_key[node.component.key] = node
        else:
            previous_by_index[index] = node

    seen_keys: set[str] = set()
    children = []
    for index, next_child in enumerate(next_children):
        if isinstance(next_child, Component) and next_child.key is not None:
            if next_child.key in seen_keys:
                raise DuplicateKey(f"Sibling components share the key {next_child.key!r}")
            seen_keys.add(next_child.key)
            previous_child = previous_by_key.pop(next_child.key, None)
        else:
            previous_child = previous_by_index.pop(index, None)

        children.append(update_node(next_child, previous_child, reconciliation))

    for unmatched in chain(previous_by_key.values(), previous_by_index.values()):
        unmount(unmatched, reconciliation)

    return tuple(children)
