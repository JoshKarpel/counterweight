from __future__ import annotations

from asyncio import Task
from collections.abc import Callable
from typing import Literal, TypeVar

from pydantic import Field

from counterweight._context_vars import current_event_queue, current_hook_idx
from counterweight.errors import InconsistentHookExecution
from counterweight.events import StateSet
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup
from counterweight.types import ForbidExtras


class UseState(ForbidExtras):
    type: Literal["state"] = "state"
    value: object


class UseRef(ForbidExtras):
    type: Literal["ref"] = "ref"
    ref: Ref[object]


class UseEffect(ForbidExtras):
    type: Literal["effect"] = "effect"
    setup: Setup
    deps: Deps
    new_deps: Deps
    task: Task[None] | None = None

    class Config:
        arbitrary_types_allowed = True


T = TypeVar("T")


class Hooks(ForbidExtras):
    data: list[UseState | UseRef | UseEffect] = Field(default_factory=list)

    def use_state(self, initial_value: Getter[T] | T) -> tuple[T, Setter[T]]:
        try:
            hook = self.data[current_hook_idx.get()]
            if not isinstance(hook, UseState):
                raise InconsistentHookExecution(
                    f"Expected a {UseState.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseState(value=initial_value() if callable(initial_value) else initial_value)
            self.data.append(hook)

        def set_state(value: T | Callable[[T], T]) -> None:
            if callable(value):
                value = value(hook.value)  # type: ignore[arg-type]
            hook.value = value
            current_event_queue.get().put_nowait(StateSet())

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook.value, set_state  # type: ignore[return-value]

    def use_ref(self, initial_value: T) -> Ref[T]:
        try:
            hook = self.data[current_hook_idx.get()]
            if not isinstance(hook, UseRef):
                raise InconsistentHookExecution(
                    f"Expected a {UseRef.__name__} hook, but got a {type(hook).__name__} hook instead."
                )
        except IndexError:
            hook = UseRef(ref=Ref[object](current=initial_value))
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
