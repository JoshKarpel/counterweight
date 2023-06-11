from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Extra, Field


class FrozenForbidExtras(BaseModel):
    class Config:
        frozen = True
        extras = Extra.forbid


class Edge(FrozenForbidExtras):
    top: int
    bottom: int
    left: int
    right: int


class BorderKind(Enum):
    Star = "******"
    Light = "│─┌┐└┘"
    Heavy = "┃━┏┓┗┛"


class Border(FrozenForbidExtras):
    kind: BorderKind = Field(default=BorderKind.Light)


class Style(FrozenForbidExtras):
    margin: Edge | None = Field(default=None)
    border: Border | None = Field(default=None)
    padding: Edge | None = Field(default=None)


class Div(FrozenForbidExtras):
    children: tuple[AnyElement, ...]
    style: Style = Field(default=Style())


class Text(FrozenForbidExtras):
    text: str
    style: Style = Field(default=Style())


AnyElement = Div | Text

Div.update_forward_refs()
