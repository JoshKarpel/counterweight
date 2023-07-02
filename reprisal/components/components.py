from __future__ import annotations

from asyncio import Task
from collections.abc import Callable, Generator
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from itertools import zip_longest
from typing import Coroutine, Generic, Literal, TypeVar

from pydantic import Field

from reprisal.context_vars import current_event_queue
from reprisal.events import KeyPressed, StateSet
from reprisal.styles import Style
from reprisal.types import ForbidExtras, FrozenForbidExtras


def component(func: Callable[[object, ...], Component | Element]) -> Callable[[object, ...], Component]:
    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> Component:
        return Component(func=func, args=args, kwargs=kwargs)

    return wrapper


class Component(FrozenForbidExtras):
    func: Callable[[object, ...], Component]
    args: tuple[object, ...]
    kwargs: dict[str, object]


class Element(FrozenForbidExtras):
    children: tuple[Component | Element, ...] = Field(default_factory=tuple)
    on_key: Callable[[KeyPressed], None] | None = None
    style: Style = Field(default=Style())


class Div(Element):
    type: Literal["div"] = "div"


class Text(Element):
    type: Literal["text"] = "text"
    text: str


T = TypeVar("T")


class UseState(ForbidExtras):
    type: Literal["state"] = "state"
    value: object


class UseRef(ForbidExtras):
    type: Literal["ref"] = "ref"
    value: object


class UseEffect(ForbidExtras):
    type: Literal["effect"] = "effect"
    setup: Setup
    deps: Deps
    new_deps: Deps
    task: Task | None = None

    class Config:
        arbitrary_types_allowed = True


@dataclass(slots=True)
class Ref(Generic[T]):
    current: T


Getter = Callable[[], T]
Setter = Callable[[T], None]
Setup = Callable[[], Coroutine[None, None, None]]
Deps = tuple[object, ...] | None

current_hook_idx = ContextVar("current_hook_idx")
current_hook_state = ContextVar("current_hook_state")


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


def use_state(initial_value: T | Getter[T]) -> tuple[T, Setter[T]]:
    return current_hook_state.get().use_state(initial_value)


def use_ref(initial_value: T) -> Ref[T]:
    return current_hook_state.get().use_ref(initial_value)


def use_effect(setup: Setup, deps: Deps = ()) -> None:
    return current_hook_state.get().use_effect(setup, deps)


class ShadowNode(ForbidExtras):
    component: Component
    element: Element
    children: list[ShadowNode | Element] = Field(default_factory=list)
    hooks: Hooks

    def walk(self) -> Generator[ShadowNode]:
        yield self
        for child in self.children:
            if isinstance(child, ShadowNode):
                yield from child.walk()


def render_shadow_node_from_previous(component: Component, previous: ShadowNode | None) -> ShadowNode:
    if previous is None or component.func != previous.component.func:
        reset_current_hook_idx = current_hook_idx.set(0)

        hook_state = Hooks()
        reset_current_hook_state = current_hook_state.set(hook_state)

        element = component.func(*component.args, **component.kwargs)

        children = []
        for child in element.children:
            if isinstance(child, Component):
                children.append(render_shadow_node_from_previous(child, None))
            else:
                children.append(child)

        new = ShadowNode(
            component=component,
            element=element,
            children=children,
            hooks=hook_state,
        )
    else:
        reset_current_hook_idx = current_hook_idx.set(0)

        reset_current_hook_state = current_hook_state.set(previous.hooks)

        element = component.func(*component.args, **component.kwargs)

        children = []
        for new_child, previous_child in zip_longest(element.children, previous.children):
            if isinstance(new_child, Component):
                if isinstance(previous_child, ShadowNode):
                    children.append(render_shadow_node_from_previous(new_child, previous_child))
                else:
                    children.append(render_shadow_node_from_previous(new_child, None))
            else:
                children.append(new_child)

        new = ShadowNode(
            component=component,
            element=element,
            children=children,
            hooks=previous.hooks,  # the hooks are mutable and carry through renders
        )

    current_hook_idx.reset(reset_current_hook_idx)
    current_hook_state.reset(reset_current_hook_state)

    return new


def build_concrete_element_tree(root: ShadowNode) -> Element:
    return root.element.copy(
        update={"children": [child.element if isinstance(child, ShadowNode) else child for child in root.children]}
    )


Component.update_forward_refs()
Element.update_forward_refs()
Div.update_forward_refs()
Text.update_forward_refs()
UseState.update_forward_refs()
UseEffect.update_forward_refs()
