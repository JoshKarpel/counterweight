from __future__ import annotations

from functools import wraps
from typing import Callable, Literal, ParamSpec, Union

from pydantic import Field

from reprisal.events import KeyPressed
from reprisal.styles import Style
from reprisal.types import FrozenForbidExtras

P = ParamSpec("P")


def component(func: Callable[P, Element]) -> Callable[P, Component]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Component:
        return Component(func=func, args=args, kwargs=kwargs)

    return wrapper


class Component(FrozenForbidExtras):
    func: Callable[..., Element]
    args: tuple[object, ...]
    kwargs: dict[str, object]


class Element(FrozenForbidExtras):
    children: list[Component | Element] = Field(default_factory=list)
    on_key: Callable[[KeyPressed], None] | None = None
    style: Style = Field(default=Style())


class Div(Element):
    type: Literal["div"] = "div"


class Paragraph(Element):
    type: Literal["text"] = "text"
    content: str


AnyElement = Union[
    Div,
    Paragraph,
]

Component.update_forward_refs()
