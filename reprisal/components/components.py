from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from itertools import zip_longest
from typing import Literal, TypeVar

from pydantic import Field

from reprisal.events import KeyPressed
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


AnyHook = UseState

current_hook_idx = ContextVar("current_hook_idx")
current_shadow_node = ContextVar("current_shadow_node")
current_hook_state = ContextVar("current_hook_state")


class Hooks(ForbidExtras):
    hooks: list[AnyHook] = Field(default_factory=list)

    def use_state(self, initial_value: T | Callable[[], T]) -> tuple[T, Callable[[T], None]]:
        try:
            hook = self.hooks[current_hook_idx.get()]
        except IndexError:
            hook = UseState(value=initial_value() if callable(initial_value) else initial_value)
            self.hooks.append(hook)

        def set_state(value: T) -> None:
            hook.value = value

        current_hook_idx.set(current_hook_idx.get() + 1)

        return hook.value, set_state


def use_state(initial_value: T | Callable[[], T]) -> tuple[T, Callable[[T], None]]:
    return current_hook_state.get().use_state(initial_value)


class ShadowNode(ForbidExtras):
    component: Component
    element: Element
    children: list[ShadowNode | Element] = Field(default_factory=list)
    hooks: Hooks


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
