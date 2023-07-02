from __future__ import annotations

from enum import Enum
from typing import Literal, TypeVar

from pydantic import Field
from pydantic.color import Color

from reprisal.styles.merge import merge
from reprisal.types import FrozenForbidExtras

S = TypeVar("S", bound="StylePart")


class StylePart(FrozenForbidExtras):
    def __or__(self: S, other: S) -> S:
        return type(self).parse_obj(merge(self.dict(exclude_unset=True), other.dict(exclude_unset=True)))


# https://www.compart.com/en/unicode/block/U+2500
class BorderKind(Enum):
    Star = "********"
    Light = "││──┌┐└┘"
    LightRounded = "││──╭╮╰╯"
    Heavy = "┃┃━━┏┓┗┛"
    Double = "║║══╔╗╚╝"
    Thick = "▌▐▀▄▛▜▙▟"
    LightShade = "░░░░░░░░"
    MediumShade = "▒▒▒▒▒▒▒▒"
    HeavyShade = "▓▓▓▓▓▓▓▓"


class Border(StylePart):
    kind: BorderKind = Field(default=BorderKind.Light)


class Margin(StylePart):
    top: int = Field(default=0)
    bottom: int = Field(default=0)
    left: int | Literal["auto"] = Field(default=0)
    right: int | Literal["auto"] = Field(default=0)


class Padding(StylePart):
    top: int = Field(default=0)
    bottom: int = Field(default=0)
    left: int = Field(default=0)
    right: int = Field(default=0)


class Span(StylePart):
    width: int | Literal["auto"] = Field(default="auto")
    height: int | Literal["auto"] = Field(default="auto")


class Style(StylePart):
    display: Literal["block"] = Field(default="block")
    span: Span = Field(default=Span())
    margin: Margin = Field(default=Margin(top=0, bottom=0, left=0, right="auto"))
    border: Border | None = Field(default=None)
    border_color: Color = Field(default=Color("white"))
    padding: Padding = Field(default=Padding(top=0, bottom=0, left=0, right=0))
