from __future__ import annotations

from asyncio import Task
from typing import Literal, TypeVar

from pydantic import Field

from reprisal._context_vars import current_event_queue, current_hook_idx
from reprisal.events import StateSet
from reprisal.hooks.types import Deps, Getter, Ref, Setter, Setup
from reprisal.types import ForbidExtras


class UseState(ForbidExtras):
    type: Literal["state"] = "state"
    value: object


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
    data: list[UseState | Ref | UseEffect] = Field(default_factory=list)

    def use_state(self, initial_value: T | Getter[T]) -> tuple[T, Setter[T]]:
        try:
            hook = self.data[current_hook_idx.get()]
        except IndexError:
            hook = UseState(value=initial_value() if callable(initial_value) else initial_value)
            self.data.append(hook)

        def set_state(value: T) -> None:
            hook.value = value
            current_event_queue.get().put_nowait(StateSet())

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook.value, set_state

    def use_ref(self, initial_value: T) -> Ref[T]:
        try:
            hook = self.data[current_hook_idx.get()]
        except IndexError:
            hook = Ref(current=initial_value)
            self.data.append(hook)

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook

    def use_effect(self, setup: Setup, deps: Deps) -> None:
        try:
            hook = self.data[current_hook_idx.get()]
            hook.new_deps = deps
        except IndexError:
            hook = UseEffect(
                setup=setup,
                deps=(object(),),  # these deps will never equal anything else
                new_deps=deps,
            )
            self.data.append(hook)

        current_hook_idx.set(current_hook_idx.get() + 1)

        return None
