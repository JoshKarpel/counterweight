from __future__ import annotations

from enum import Enum
from typing import Literal, NamedTuple, TypeVar

from pydantic import Field

from reprisal._utils import merge
from reprisal.types import FrozenForbidExtras

S = TypeVar("S", bound="StylePart")


class StylePart(FrozenForbidExtras):
    def __or__(self: S, other: S) -> S:
        return type(self).parse_obj(
            merge(
                self.dict(exclude_unset=True),
                other.dict(exclude_unset=True),
            )
        )


class Color(NamedTuple):
    red: int
    green: int
    blue: int

    @classmethod
    def from_name(cls, name: str) -> Color:
        return COLORS_BY_NAME[name]


COLORS_BY_NAME = {
    "white": Color(255, 255, 255),
    "black": Color(0, 0, 0),
    "red": Color(255, 0, 0),
    "green": Color(0, 255, 0),
    "blue": Color(0, 0, 255),
}


class CellStyle(StylePart):
    foreground: Color = Field(default=Color.from_name("white"))
    background: Color = Field(default=Color.from_name("black"))
    bold: bool = False
    dim: bool = False
    italic: bool = False


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
    style: CellStyle = Field(default_factory=CellStyle)


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
    padding: Padding = Field(default=Padding(top=0, bottom=0, left=0, right=0))
