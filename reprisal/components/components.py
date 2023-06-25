from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from itertools import zip_longest
from typing import Literal, TypeVar

from pydantic import Field

from reprisal.events import KeyPressed
from reprisal.styles import Style
from reprisal.types import ForbidExtras, FrozenForbidExtras


def component(func: Callable[[object, ...], object]) -> Component:
    return Component(func=func)


class Component(FrozenForbidExtras):
    func: Callable[[object, ...], Element]

    def __call__(self, *args, **kwargs) -> Composite:
        return Composite(component=self, args=args, kwargs=kwargs)


class Composite(FrozenForbidExtras):
    component: Component
    args: tuple[object, ...]
    kwargs: dict[str, object]


class Element(FrozenForbidExtras):
    children: tuple[Element | Composite, ...] = Field(default_factory=tuple)
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


class ShadowNode(ForbidExtras):
    render_call: Composite
    value: Element | None = None
    children: list[ShadowNode | Element] = Field(default_factory=list)
    hooks: list[AnyHook] = Field(default_factory=list)
    hook_idx: int = 0
    dirty: bool = False

    def use_state(self, initial_value: T | Callable[[], T]) -> tuple[T, Callable[[T], None]]:
        try:
            hook = self.hooks[self.hook_idx]
        except IndexError:
            hook = UseState(value=initial_value() if callable(initial_value) else initial_value)
            self.hooks.append(hook)

        self.hook_idx += 1

        def set_state(value: T) -> None:
            hook.value = value
            self.dirty = True

        return hook.value, set_state


current_shadow_node = ContextVar("current_shadow_node")


def use_state(initial_value: T | Callable[[], T]) -> tuple[T, Callable[[T], None]]:
    return current_shadow_node.get().use_state(initial_value)


def build_initial_shadow_tree(root: Composite) -> ShadowNode:
    sn = ShadowNode(render_call=root)

    reset_token = current_shadow_node.set(sn)

    sn.value = root.component.func(*root.args, **dict(root.kwargs))

    current_shadow_node.reset(reset_token)
    sn.hook_idx = 0

    for child in sn.value.children:
        if isinstance(child, Composite):
            sn.children.append(build_initial_shadow_tree(child))
        else:
            sn.children.append(child)

    return sn


def reconcile_shadow_tree(root: ShadowNode) -> ShadowNode:
    if root.dirty:
        print(f"dirty {root=}")

        reset_token = current_shadow_node.set(root)

        root.value = root.render_call.component.func(*root.render_call.args, **dict(root.render_call.kwargs))

        current_shadow_node.reset(reset_token)
        root.hook_idx = 0

        root.dirty = False

    new = []
    for prev_child, new_child in zip_longest(root.children, root.value.children):
        if isinstance(new_child, Composite):
            if not isinstance(prev_child, ShadowNode):
                new.append(build_initial_shadow_tree(new_child))
            else:
                if prev_child.render_call == new_child and not prev_child.dirty:
                    # cache hit
                    new.append(prev_child)

                else:
                    # cache miss
                    new.append(reconcile_shadow_tree(prev_child.copy(update={"render_call": new_child})))
        else:
            new.append(new_child)

    root.children = new

    return root


def build_concrete_element_tree(root: ShadowNode) -> Element:
    return root.value.copy(
        update={"children": [child.value if isinstance(child, ShadowNode) else child for child in root.children]}
    )


Component.update_forward_refs()
Element.update_forward_refs()
Div.update_forward_refs()
Text.update_forward_refs()
UseState.update_forward_refs()
