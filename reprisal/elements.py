from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Extra, Field


class FrozenForbidExtras(BaseModel):
    class Config:
        frozen = True
        extras = Extra.forbid


# https://www.compart.com/en/unicode/block/U+2500
class BorderKind(Enum):
    Star = "******"
    Light = "│─┌┐└┘"
    LightRounded = "│─╭╮╰╯"
    Heavy = "┃━┏┓┗┛"


class Border(FrozenForbidExtras):
    kind: BorderKind = Field(default=BorderKind.Light)


class Margin(FrozenForbidExtras):
    top: int = Field(default=0)
    bottom: int = Field(default=0)
    left: int | Literal["auto"] = Field(default=0)
    right: int | Literal["auto"] = Field(default="auto")


class Padding(FrozenForbidExtras):
    top: int = Field(default=0)
    bottom: int = Field(default=0)
    left: int = Field(default=0)
    right: int = Field(default=0)


class Span(FrozenForbidExtras):
    width: int | Literal["auto"] = Field(default="auto")
    height: int | Literal["auto"] = Field(default="auto")


class Style(FrozenForbidExtras):
    display: Literal["block"] = Field(default="block")
    span: Span = Field(default=Span())
    margin: Margin = Field(default=Margin(top=0, bottom=0, left=0, right="auto"))
    border: Border | None = Field(default=None)
    padding: Padding = Field(default=Padding(top=0, bottom=0, left=0, right=0))


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...]
    style: Style = Field(default=Style())


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())


AnyElement = Div | Text

Div.update_forward_refs()
