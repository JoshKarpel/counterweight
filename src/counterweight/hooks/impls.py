from __future__ import annotations

from asyncio import Task
from collections.abc import Iterator
from dataclasses import dataclass, field

from counterweight._context_vars import current_event_queue, current_hook_idx
from counterweight.events import StateSet
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup
from counterweight.layout import INITIAL_RESOLVED_LAYOUT, ResolvedLayout


@dataclass(slots=True)
class MountStatus:
    """
    Whether a component instance is still in the tree.
    One is shared by a `Hooks` and the slots that act on their own after render (like a setter),
    so unmounting the instance is a single write that every slot sees.
    """

    is_mounted: bool = True


@dataclass(slots=True)
class UseState:
    value: object
    mount_status: MountStatus
    setter: Setter[object] = field(init=False)

    def __post_init__(self) -> None:
        # Bound once so every render hands out the same setter, which keeps it safe to put in an effect's deps.
        self.setter = self.set

    def set(self, value: object) -> None:
        if not self.mount_status.is_mounted:
            return

        if callable(value):
            value = value(self.value)

        if self.value != value:  # avoid unnecessary updates
            self.value = value
            current_event_queue.get().put_nowait(StateSet())


@dataclass(slots=True)
class UseRef:
    ref: Ref[object]


@dataclass(slots=True)
class UseEffect:
    setup: Setup
    deps: Deps
    new_deps: Deps
    task: Task[None] | None = None


class InconsistentHookExecution(Exception):
    pass


@dataclass(slots=True)
class Hooks:
    data: list[UseState | UseRef | UseEffect] = field(default_factory=list)
    dims: ResolvedLayout = field(default=INITIAL_RESOLVED_LAYOUT)
    mount_status: MountStatus = field(default_factory=MountStatus)

    @property
    def effects(self) -> Iterator[UseEffect]:
        return (hook for hook in self.data if isinstance(hook, UseEffect))

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

        hook.setup = setup  # we must capture the new setup function to update its closure
        hook.new_deps = deps  # ... but the decision about whether to actually rerun it will be made based on its deps

        current_hook_idx.set(current_hook_idx.get() + 1)

        return None
