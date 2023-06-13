from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Extra, Field


class FrozenForbidExtras(BaseModel):
    class Config:
        frozen = True
        extras = Extra.forbid


class Edge(FrozenForbidExtras):
    top: int = 0
    bottom: int = 0
    left: int = 0
    right: int = 0

    def height(self) -> int:
        return self.top + self.bottom

    def width(self) -> int:
        return self.left + self.right


# https://www.compart.com/en/unicode/block/U+2500
class BorderKind(Enum):
    Star = "******"
    Light = "│─┌┐└┘"
    LightRounded = "│─╭╮╰╯"
    Heavy = "┃━┏┓┗┛"


class Border(FrozenForbidExtras):
    kind: BorderKind = Field(default=BorderKind.Light)


class Cells(FrozenForbidExtras):
    cells: int


class Span(FrozenForbidExtras):
    width: Cells | Literal["fill"] = "fill"
    height: Cells | Literal["fill"] | Literal["fit"] = "fit"


class Style(FrozenForbidExtras):
    span: Span = Field(default=Span())
    margin: Edge = Field(default=Edge())
    border: Border | None = Field(default=None)
    padding: Edge = Field(default=Edge())

    def box_height(self) -> int:
        return self.margin.height() + self.padding.height() + 2 if self.border else 0


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...]
    style: Style = Field(default=Style())


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())


AnyElement = Div | Text

Div.update_forward_refs()
