from __future__ import annotations

from typing import TypeVar, overload

from counterweight._context_vars import current_hook_state
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup

T = TypeVar("T")


@overload
def use_state(initial_value: Getter[T]) -> tuple[T, Setter[T]]:
    ...


@overload
def use_state(initial_value: T) -> tuple[T, Setter[T]]:
    ...


def use_state(initial_value: Getter[T] | T) -> tuple[T, Setter[T]]:
    return current_hook_state.get().use_state(initial_value)


def use_ref(initial_value: T) -> Ref[T]:
    return current_hook_state.get().use_ref(initial_value)


def use_effect(setup: Setup, deps: Deps | None = None) -> None:
    return current_hook_state.get().use_effect(setup, deps)
