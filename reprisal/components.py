from __future__ import annotations

from collections.abc import Iterator, Sequence
from functools import wraps
from typing import Callable, Literal, ParamSpec, Union

from pydantic import Field

from reprisal.cell_paint import CellPaint
from reprisal.control import Control
from reprisal.events import KeyPressed, MouseDown, MouseUp
from reprisal.styles import Style
from reprisal.styles.styles import CellStyle
from reprisal.types import FrozenForbidExtras

P = ParamSpec("P")

Key = str | int | None


def component(func: Callable[P, AnyElement]) -> Callable[P, Component]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Component:
        return Component(func=func, args=args, kwargs=kwargs)

    return wrapper


class Component(FrozenForbidExtras):
    func: Callable[..., AnyElement]
    args: tuple[object, ...]
    kwargs: dict[str, object]
    key: Key = None

    def with_key(self, key: Key) -> Component:
        return self.model_copy(update={"key": key})


class Div(FrozenForbidExtras):
    type: Literal["div"] = "div"
    style: Style = Field(default=Style())
    children: Sequence[Component | AnyElement] = Field(default_factory=list)
    on_hover: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], Control | None] | None = None
    on_mouse_down: Callable[[MouseDown], Control | None] | None = None
    on_mouse_up: Callable[[MouseUp], Control | None] | None = None


class Chunk(FrozenForbidExtras):
    content: str
    style: CellStyle = Field(default_factory=CellStyle)

    @property
    def cells(self) -> list[CellPaint]:
        return [CellPaint(char=char, style=self.style) for char in self.content]

    @classmethod
    def space(cls) -> Chunk:
        return Chunk(content=" ")

    @classmethod
    def newline(cls) -> Chunk:
        return Chunk(content="\n")


class Text(FrozenForbidExtras):
    type: Literal["text"] = "text"
    content: str | list[Chunk]
    style: Style = Field(default=Style())
    on_hover: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], Control | None] | None = None
    on_mouse_down: Callable[[MouseDown], Control | None] | None = None
    on_mouse_up: Callable[[MouseUp], Control | None] | None = None

    @property
    def children(self) -> Sequence[Component | AnyElement]:
        return ()

    @property
    def chunks(self) -> Iterator[Chunk]:
        if isinstance(self.content, str):
            yield Chunk(content=self.content)
        else:
            yield from self.content

    @property
    def cells(self) -> Iterator[CellPaint]:
        for chunk in self.chunks:
            yield from chunk.cells

    @property
    def unstyled_text(self) -> str:
        return "".join(chunk.content for chunk in self.chunks)


AnyElement = Union[
    Div,
    Text,
]

Component.model_rebuild()
Div.model_rebuild()
Text.model_rebuild()
