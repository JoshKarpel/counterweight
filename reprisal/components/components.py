from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import Field

from reprisal.events import KeyPressed
from reprisal.styles import Style
from reprisal.types import FrozenForbidExtras


def component(func: Callable[[object, ...], object]) -> Component:
    return Component(func=func)


class Component(FrozenForbidExtras):
    func: Callable[[object, ...], AnyElement]

    def __call__(self, *args, **kwargs):
        return RenderCall(component=self, args=args, kwargs=tuple(kwargs.items()))


class RenderCall(FrozenForbidExtras):
    component: Component
    args: tuple[object, ...]
    kwargs: tuple[tuple[str, object], ...]


class Div(FrozenForbidExtras):
    type: Literal["div"] = "div"
    children: tuple[AnyElement | RenderCall, ...] = Field(default=...)
    style: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], None] | None = None


class Text(FrozenForbidExtras):
    type: Literal["text"] = "text"
    text: str
    style: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], None] | None = None
    children: list[AnyElement] = Field(default_factory=list)  # TODO: max_items=0 doesn't work here?


AnyElement = Div | Text

Component.update_forward_refs()
Div.update_forward_refs()
Text.update_forward_refs()


class ShadowNode(FrozenForbidExtras):
    render_call: RenderCall
    value: AnyElement
    children: list[ShadowNode | AnyElement]


def build_shadow_tree(root: RenderCall) -> ShadowNode:
    # TODO: hooks
    value = root.component.func(*root.args, **dict(root.kwargs))

    children = []
    for child in value.children:
        if isinstance(child, RenderCall):
            children.append(build_shadow_tree(child))
        else:
            children.append(child)

    return ShadowNode(render_call=root, value=value, children=children)


def build_value_tree(root: ShadowNode) -> AnyElement:
    return root.value.copy(
        update={"children": [child.value if isinstance(child, ShadowNode) else child for child in root.children]}
    )
