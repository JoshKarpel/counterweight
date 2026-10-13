from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import chain

from counterweight._context_vars import (
    current_focused,
    current_hook_idx,
    current_hook_state,
    current_layouts,
    current_purity_checked,
)
from counterweight.components import Component
from counterweight.elements import AnyElement
from counterweight.equivalence import equivalent
from counterweight.hooks.hooks import rects_in
from counterweight.hooks.impls import Hooks, InconsistentHookExecution, NodeKey, UseFocus
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
        """The key of the mounted node this continues, which its hooks carry across frames."""
        return self.hooks.key

    def detached(self) -> ShadowNode:
        """A copy of the subtree whose hooks are `Hooks.detached`, so rendering against it changes nothing this keeps."""
        return ShadowNode(
            component=self.component,
            element=self.element,
            hooks=self.hooks.detached(),
            children=tuple(child.detached() for child in self.children),
        )

    def walk(self) -> Iterator[ShadowNode]:
        """Yields every node in the subtree in pre-order, with an explicit stack so cost is linear in node count."""
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))


@dataclass(frozen=True, slots=True)
class ShadowTree:
    """
    A shadow tree with its nodes indexed once, when it's built,
    so whatever needs every node, or a node's ancestors, reads the index instead of walking the tree again.
    """

    root: ShadowNode
    nodes: tuple[ShadowNode, ...] = field(init=False, repr=False, compare=False)
    """Every node, in pre-order."""
    parents: Mapping[NodeKey, NodeKey | None] = field(init=False, repr=False, compare=False)
    """The key of each node's parent, by the node's key, with `None` for the root's."""
    measured: tuple[ShadowNode, ...] = field(init=False, repr=False, compare=False)
    """
    The nodes whose last run called `use_rects`.
    A node's `rects` change only when it runs, which only happens while building the next tree.
    """
    focusable: Mapping[NodeKey, UseFocus] = field(init=False, repr=False, compare=False)
    """The `use_focus` hook of each node whose last run called `use_focus`, hidden ones included, in pre-order."""

    def __post_init__(self) -> None:
        nodes = []
        parents: dict[NodeKey, NodeKey | None] = {self.root.key: None}
        measured = []
        focusable = {}
        for node in self.root.walk():
            nodes.append(node)
            for child in node.children:
                parents[child.key] = node.key
            if node.hooks.rects is not None:
                measured.append(node)
            if node.hooks.focus is not None:
                focusable[node.key] = node.hooks.focus

        object.__setattr__(self, "nodes", tuple(nodes))
        object.__setattr__(self, "parents", parents)
        object.__setattr__(self, "measured", tuple(measured))
        object.__setattr__(self, "focusable", focusable)


@dataclass(frozen=True, slots=True)
class ShadowUpdate:
    """
    One frame's shadow tree, with the hooks of the components that ran to build it
    and of every previous node it unmounted, so effects can follow exactly the renders that happened,
    and the keys of the components it mounted, which `auto_focus` reads.
    """

    tree: ShadowTree
    ran: tuple[Hooks, ...]
    unmounted: tuple[Hooks, ...]
    mounted: frozenset[NodeKey]

    def followed_by(self, later: ShadowUpdate) -> ShadowUpdate:
        """
        One update for this one and a `later` one built from its tree before any effects ran,
        so a node that ran in both runs its effects once,
        and one that mounted here but `later` unmounted counts as neither ran nor mounted.
        """
        unmounted_later = {hooks.key for hooks in later.unmounted}
        ran = {hooks.key: hooks for hooks in chain(self.ran, later.ran) if hooks.key not in unmounted_later}
        return ShadowUpdate(
            tree=later.tree,
            ran=tuple(ran.values()),
            unmounted=self.unmounted + later.unmounted,
            mounted=(self.mounted | later.mounted) - unmounted_later,
        )


class DuplicateKey(Exception):
    """Raised when keyed sibling components share a key, which leaves no single previous child for each to continue."""


class ImpureComponent(Exception):
    """
    Raised when `check_purity` is on and re-running every component builds a different tree from the one a render built,
    so some component's output depends on something besides its arguments and hooks:
    the output a render kept for it is stale, or calling it twice doesn't give the same result.
    """


def is_dirty(node: ShadowNode, dirty: frozenset[NodeKey], layouts: Layouts) -> bool:
    """
    Whether `node` has to re-run whatever its parent does:
    its state was set, or the rectangles `use_rects` last returned to it have moved since.
    """
    return node.key in dirty or (node.hooks.rects is not None and node.hooks.rects != rects_in(layouts, node.key))


def dirty_paths(
    tree: ShadowTree, dirty: frozenset[NodeKey], layouts: Layouts
) -> tuple[frozenset[NodeKey], frozenset[NodeKey]]:
    """
    The keys of every dirty node in `tree` (see `is_dirty`),
    and the paths to them: those keys and the keys of all their ancestors.
    Only a node in `dirty` or one that called `use_rects` can be dirty,
    so it visits only those and their ancestors, not the whole tree.
    """
    dirty_nodes = frozenset(
        chain(
            (key for key in dirty if key in tree.parents),
            (node.key for node in tree.measured if is_dirty(node, dirty, layouts)),
        )
    )

    paths: set[NodeKey] = set()
    for dirty_key in dirty_nodes:
        key: NodeKey | None = dirty_key
        while key is not None and key not in paths:
            paths.add(key)
            key = tree.parents[key]

    return dirty_nodes, frozenset(paths)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What one `update_shadow` call reads, and the hooks it collects as it goes."""

    layouts: Layouts
    focused: NodeKey | None
    dirty_nodes: frozenset[NodeKey]
    paths: frozenset[NodeKey]
    check_purity: bool
    ran: list[Hooks] = field(default_factory=list)
    unmounted: list[Hooks] = field(default_factory=list)
    mounted: list[NodeKey] = field(default_factory=list)


def update_shadow(
    next: Component | AnyElement,
    previous: ShadowTree | None,
    layouts: Layouts,
    dirty: frozenset[NodeKey] = frozenset(),
    check_purity: bool = False,
    focused: NodeKey | None = None,
) -> ShadowUpdate:
    """
    Builds the next shadow tree from `previous`, re-running only the components that have to:
    those in `dirty` or whose rectangles moved (see `is_dirty`), and those whose parent passed them a new `Component`,
    unless it's a `memo` component equal to its previous one (see `continues`).
    A component that doesn't re-run keeps its previous node, whole subtree included,
    unless a dirty node is below it, in which case its children are reconciled again to reach it.
    `layouts` are the previous frame's, which `use_rects` reads, and `focused` is the focused node's key,
    which `use_focus` reads.
    With `check_purity`, the tree is then built again with every component re-run (see `check_is_pure`).
    """
    dirty_nodes, paths = (frozenset(), frozenset()) if previous is None else dirty_paths(previous, dirty, layouts)
    reconciliation = Reconciliation(
        layouts=layouts, focused=focused, dirty_nodes=dirty_nodes, paths=paths, check_purity=False
    )
    tree = ShadowTree(root=update_node(next, None if previous is None else previous.root, reconciliation))

    if check_purity:
        check_is_pure(next, tree, layouts, focused)

    return ShadowUpdate(
        tree=tree,
        ran=tuple(reconciliation.ran),
        unmounted=tuple(reconciliation.unmounted),
        mounted=frozenset(reconciliation.mounted),
    )


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
                element, hook_count = call_component(next_component, previous_hooks, reconciliation)
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
            element, _ = call_component(next_component, hook_state, reconciliation)
            reconciliation.ran.append(hook_state)
            reconciliation.mounted.append(hook_state.key)

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


def check_is_pure(next: Component | AnyElement, tree: ShadowTree, layouts: Layouts, focused: NodeKey | None) -> None:
    """
    Builds `tree` again from `next`, re-running every component against a `ShadowNode.detached` copy of it,
    and raises `ImpureComponent` naming the component that owns the first node whose element isn't `equivalent`.
    A node is compared only once all its ancestors matched, so the component named is where the difference starts.
    Re-running also checks each component's hook count (see `update_node`),
    and each `use_memo` that keeps its cached value (see `Hooks.use_memo`).
    """
    every_key = frozenset(tree.parents)
    reconciliation = Reconciliation(
        layouts=layouts, focused=focused, dirty_nodes=every_key, paths=every_key, check_purity=True
    )
    rerun = update_node(next, tree.root.detached(), reconciliation)

    pairs: list[tuple[ShadowNode, ShadowNode, Component | None]] = [(tree.root, rerun, tree.root.component)]
    while pairs:
        kept, again, owner = pairs.pop()
        owner = kept.component if kept.component is not None else owner
        if not equivalent(kept.element, again.element):
            name = "The root element" if owner is None else owner.func.__qualname__
            raise ImpureComponent(
                f"{name} returned a different element when every component was run again "
                "with the same arguments and hooks, so its output depends on something else, "
                "such as a module-level value or the time. "
                "A component must depend only on its arguments and its hooks."
            )
        pairs.extend((k, a, owner) for k, a in reversed(tuple(zip(kept.children, again.children, strict=True))))


def call_component(component: Component, hooks: Hooks, reconciliation: Reconciliation) -> tuple[AnyElement, int]:
    """
    Calls a component function with `hooks` as the current hook state,
    and the previous frame's layouts and the focused key from `reconciliation`,
    restoring the outer hook context even if it raises.
    With `check_purity`, each `use_memo` that keeps its cached value also checks it (see `Hooks.use_memo`).
    Returns the element and how many hooks it called.
    """
    reset_current_hook_idx = current_hook_idx.set(0)
    reset_current_hook_state = current_hook_state.set(hooks)
    reset_current_layouts = current_layouts.set(reconciliation.layouts)
    reset_current_focused = current_focused.set(reconciliation.focused)
    reset_current_purity_checked = current_purity_checked.set(component if reconciliation.check_purity else None)
    # use_rects isn't positional, so a run that stops calling it must stop the node re-running when its layout moves.
    hooks.rects = None
    # use_focus raises when it's called twice in one run, which it tells by this being set.
    hooks.focus = None
    try:
        element = component.func(*component.args, **component.kwargs)
        return element, current_hook_idx.get()
    finally:
        current_hook_idx.reset(reset_current_hook_idx)
        current_hook_state.reset(reset_current_hook_state)
        current_layouts.reset(reset_current_layouts)
        current_focused.reset(reset_current_focused)
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
