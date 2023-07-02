from __future__ import annotations

from functools import wraps
from typing import Callable, Literal

from pydantic import Field

from reprisal.events import KeyPressed
from reprisal.styles import Style
from reprisal.types import FrozenForbidExtras


def component(func: Callable[..., Component | Element]) -> Callable[[object, ...], Component]:
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
