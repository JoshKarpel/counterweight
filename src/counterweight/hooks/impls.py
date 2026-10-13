from __future__ import annotations

from asyncio import Task
from collections.abc import Iterator
from copy import copy
from dataclasses import dataclass, field, replace
from datetime import timedelta
from itertools import count
from typing import TYPE_CHECKING, NewType, assert_never
from weakref import ref

from counterweight._context_vars import current_event_queue, current_hook_idx, current_purity_checked
from counterweight.clock import Instant, tick_index, until_next_tick
from counterweight.equivalence import equivalent
from counterweight.events import StateSet
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup, Tick

if TYPE_CHECKING:
    from counterweight.hooks.hooks import Rects

# Identifies one mounted node across frames, for as long as its hooks carry over.
NodeKey = NewType("NodeKey", int)

_node_keys = count()


def _next_node_key() -> NodeKey:
    """A key no other `Hooks` in the process has, so keys from different apps and tests never collide."""
    return NodeKey(next(_node_keys))


@dataclass(slots=True)
class MountStatus:
    """
    Whether a component instance is still in the tree.
    One is shared by a `Hooks` and the slots that act on their own after render (like a setter),
    so unmounting the instance is a single write that every slot sees.
    """

    is_mounted: bool = True


@dataclass(slots=True, weakref_slot=True)
class UseState:
    value: object
    mount_status: MountStatus
    node_key: NodeKey
    setter: Setter[object] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Built once so every render hands out the same setter, which keeps it safe to put in an effect's deps.
        # It holds the state weakly: a bound method would form a cycle, so unmounted state would wait for the cyclic GC.
        state = ref(self)

        def setter(value: object) -> None:
            if (live_state := state()) is not None:
                live_state.set(value)

        self.setter = setter

    def set(self, value: object) -> None:
        if not self.mount_status.is_mounted:
            return

        if callable(value):
            value = value(self.value)

        if self.value != value:  # avoid unnecessary updates
            self.value = value
            current_event_queue.get().put_nowait(StateSet(key=self.node_key))


@dataclass(slots=True)
class UseRef:
    ref: Ref[object]


@dataclass(slots=True)
class UseEffect:
    setup: Setup
    deps: Deps
    new_deps: Deps
    task: Task[None] | None = None


@dataclass(slots=True)
class UseMemo:
    value: object
    deps: tuple[object, ...]


@dataclass(slots=True)
class UseClock:
    """
    The readings `use_clock` has taken for one node.
    A node keeps its `current` reading until a frame's instant falls in a later tick,
    so re-running it again within a tick, as `check_purity` does, returns the same `Tick`.
    """

    interval: timedelta
    mounted: Instant
    current: Instant

    def is_due(self, instant: Instant) -> bool:
        """Whether `instant` falls in a different tick from the current reading, so the node takes a new one."""
        return tick_index(instant.wall, self.interval) != tick_index(self.current.wall, self.interval)

    def until_due(self, instant: Instant) -> timedelta:
        """How long after `instant` the node is due a new reading."""
        return timedelta() if self.is_due(instant) else until_next_tick(instant.wall, self.interval)

    @property
    def tick(self) -> Tick:
        return Tick(
            now=self.current.wall,
            since_start=self.current.monotonic,
            since_mount=self.current.monotonic - self.mounted.monotonic,
        )


type AnyHook = UseState | UseRef | UseEffect | UseMemo | UseClock


def detached_hook(hook: AnyHook) -> AnyHook:
    """A copy of `hook` for `Hooks.detached`, or `hook` itself for a `use_state` hook, which a render only reads."""
    match hook:
        case UseState():
            return hook
        case UseRef(ref=ref):
            return UseRef(ref=Ref(current=ref.current))
        case UseEffect() | UseMemo() | UseClock():
            return copy(hook)
        case _ as unreachable:
            assert_never(unreachable)


class InconsistentHookExecution(Exception):
    pass


class StaleMemo(Exception):
    """
    Raised when `check_purity` is on and a `use_memo` whose deps didn't change
    computes something different from the value it cached,
    so the computation depends on something missing from its deps and the cached value is stale.
    """


@dataclass(slots=True)
class Hooks:
    data: list[AnyHook] = field(default_factory=list)
    mount_status: MountStatus = field(default_factory=MountStatus)
    key: NodeKey = field(default_factory=_next_node_key)
    rects: Rects | None = None
    """What `use_rects` last returned to this node, so the node re-renders once its layout moves."""
    clocks: list[UseClock] = field(default_factory=list)
    """The node's `use_clock` hooks, also in `data`, so the node re-renders once one of them is due."""

    @property
    def effects(self) -> Iterator[UseEffect]:
        return (hook for hook in self.data if isinstance(hook, UseEffect))

    def detached(self) -> Hooks:
        """
        A copy to call the node's component against without changing anything the node keeps.
        Every hook a render can write to is copied:
        `use_effect` records its arguments on its hook, `use_memo` recomputes into its hook when its deps changed,
        `use_clock` takes a new reading into its hook when one is due,
        and a component can assign `current` on a ref.
        A ref's copy holds the same `current` object, so mutating that object in place still reaches the node's ref.
        `use_state` hooks are shared, so the setters handlers capture are the node's own.
        The mount status is copied too, so unmounting the copy leaves the node mounted.
        """
        data = [detached_hook(hook) for hook in self.data]
        return replace(
            self,
            data=data,
            clocks=[hook for hook in data if isinstance(hook, UseClock)],
            mount_status=MountStatus(is_mounted=self.mount_status.is_mounted),
        )

    def use_state[T](self, initial_value: Getter[T] | T) -> tuple[T, Setter[T]]:
        try:
            hook = self.data[current_hook_idx.get()]
            if not isinstance(hook, UseState):
                raise InconsistentHookExecution(
                    f"Expected a {UseState.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseState(
                value=initial_value() if callable(initial_value) else initial_value,
                mount_status=self.mount_status,
                node_key=self.key,
            )
            self.data.append(hook)

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook.value, hook.setter  # type: ignore[return-value]

    def use_ref[T](self, initial_value: Getter[T] | T) -> Ref[T]:
        try:
            hook = self.data[current_hook_idx.get()]
            if not isinstance(hook, UseRef):
                raise InconsistentHookExecution(
                    f"Expected a {UseRef.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseRef(ref=Ref[object](current=initial_value() if callable(initial_value) else initial_value))
            self.data.append(hook)

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook.ref  # type: ignore[return-value]

    def use_effect(self, setup: Setup, deps: Deps) -> None:
        try:
            hook = self.data[current_hook_idx.get()]
            if not isinstance(hook, UseEffect):
                raise InconsistentHookExecution(
                    f"Expected a {UseEffect.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseEffect(
                setup=setup,
                deps=(object(),),  # these deps will never equal anything else
                new_deps=deps,
            )
            self.data.append(hook)
        else:
            # We must capture the new setup function to update its closure,
            # but the decision about whether to actually rerun it will be made based on its deps.
            hook.setup = setup
            hook.new_deps = deps

        current_hook_idx.set(current_hook_idx.get() + 1)

        return None

    def use_memo[T](self, compute: Getter[T], deps: tuple[object, ...]) -> T:
        index = current_hook_idx.get()
        try:
            hook = self.data[index]
            if not isinstance(hook, UseMemo):
                raise InconsistentHookExecution(
                    f"Expected a {UseMemo.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseMemo(value=compute(), deps=deps)
            self.data.append(hook)
        else:
            if hook.deps != deps:
                hook.value = compute()
                hook.deps = deps
            elif (checked := current_purity_checked.get()) is not None and not equivalent(compute(), hook.value):
                raise StaleMemo(
                    f"The use_memo hook at index {index} in {checked.func.__qualname__} computed a different value "
                    "with the same deps, so its computation depends on something missing from its deps, "
                    "and the value it cached is stale."
                )

        current_hook_idx.set(index + 1)

        return hook.value  # type: ignore[return-value]

    def use_clock(self, interval: timedelta, instant: Instant) -> Tick:
        try:
            hook = self.data[current_hook_idx.get()]
            if not isinstance(hook, UseClock):
                raise InconsistentHookExecution(
                    f"Expected a {UseClock.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseClock(interval=interval, mounted=instant, current=instant)
            self.data.append(hook)
            self.clocks.append(hook)
        else:
            hook.interval = interval
            if hook.is_due(instant):
                hook.current = instant

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook.tick
