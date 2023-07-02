from __future__ import annotations

from enum import Enum
from functools import lru_cache
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

    @classmethod
    @lru_cache(maxsize=2**10)
    def from_hex(cls, hex: str) -> Color:
        hex = hex.lstrip("#")
        return cls(
            int(hex[0:2], 16),
            int(hex[2:4], 16),
            int(hex[4:6], 16),
        )


COLORS_BY_NAME = {
    name: Color.from_hex(hex)
    for name, hex in {
        "aliceblue": "#F0F8FF",
        "antiquewhite": "#FAEBD7",
        "aqua": "#00FFFF",
        "aquamarine": "#7FFFD4",
        "azure": "#F0FFFF",
        "beige": "#F5F5DC",
        "bisque": "#FFE4C4",
        "black": "#000000",
        "blanchedalmond": "#FFEBCD",
        "blue": "#0000FF",
        "blueviolet": "#8A2BE2",
        "brown": "#A52A2A",
        "burlywood": "#DEB887",
        "cadetblue": "#5F9EA0",
        "chartreuse": "#7FFF00",
        "chocolate": "#D2691E",
        "coral": "#FF7F50",
        "cornflowerblue": "#6495ED",
        "cornsilk": "#FFF8DC",
        "crimson": "#DC143C",
        "cyan": "#00FFFF",
        "darkblue": "#00008B",
        "darkcyan": "#008B8B",
        "darkgoldenrod": "#B8860B",
        "darkgray": "#A9A9A9",
        "darkgreen": "#006400",
        "darkkhaki": "#BDB76B",
        "darkmagenta": "#8B008B",
        "darkolivegreen": "#556B2F",
        "darkorange": "#FF8C00",
        "darkorchid": "#9932CC",
        "darkred": "#8B0000",
        "darksalmon": "#E9967A",
        "darkseagreen": "#8FBC8F",
        "darkslateblue": "#483D8B",
        "darkslategray": "#2F4F4F",
        "darkturquoise": "#00CED1",
        "darkviolet": "#9400D3",
        "deeppink": "#FF1493",
        "deepskyblue": "#00BFFF",
        "dimgray": "#696969",
        "dodgerblue": "#1E90FF",
        "firebrick": "#B22222",
        "floralwhite": "#FFFAF0",
        "forestgreen": "#228B22",
        "fuchsia": "#FF00FF",
        "gainsboro": "#DCDCDC",
        "ghostwhite": "#F8F8FF",
        "gold": "#FFD700",
        "goldenrod": "#DAA520",
        "gray": "#808080",
        "green": "#008000",
        "greenyellow": "#ADFF2F",
        "honeydew": "#F0FFF0",
        "hotpink": "#FF69B4",
        "indianred": "#CD5C5C",
        "indigo": "#4B0082",
        "ivory": "#FFFFF0",
        "khaki": "#F0E68C",
        "lavender": "#E6E6FA",
        "lavenderblush": "#FFF0F5",
        "lawngreen": "#7CFC00",
        "lemonchiffon": "#FFFACD",
        "lightblue": "#ADD8E6",
        "lightcoral": "#F08080",
        "lightcyan": "#E0FFFF",
        "lightgoldenrodyellow": "#FAFAD2",
        "lightgreen": "#90EE90",
        "lightgray": "#D3D3D3",
        "lightpink": "#FFB6C1",
        "lightsalmon": "#FFA07A",
        "lightseagreen": "#20B2AA",
        "lightskyblue": "#87CEFA",
        "lightslategray": "#778899",
        "lightsteelblue": "#B0C4DE",
        "lightyellow": "#FFFFE0",
        "lime": "#00FF00",
        "limegreen": "#32CD32",
        "linen": "#FAF0E6",
        "magenta": "#FF00FF",
        "maroon": "#800000",
        "mediumaquamarine": "#66CDAA",
        "mediumblue": "#0000CD",
        "mediumorchid": "#BA55D3",
        "mediumpurple": "#9370DB",
        "mediumseagreen": "#3CB371",
        "mediumslateblue": "#7B68EE",
        "mediumspringgreen": "#00FA9A",
        "mediumturquoise": "#48D1CC",
        "mediumvioletred": "#C71585",
        "midnightblue": "#191970",
        "mintcream": "#F5FFFA",
        "mistyrose": "#FFE4E1",
        "moccasin": "#FFE4B5",
        "navajowhite": "#FFDEAD",
        "navy": "#000080",
        "oldlace": "#FDF5E6",
        "olive": "#808000",
        "olivedrab": "#6B8E23",
        "orange": "#FFA500",
        "orangered": "#FF4500",
        "orchid": "#DA70D6",
        "palegoldenrod": "#EEE8AA",
        "palegreen": "#98FB98",
        "paleturquoise": "#AFEEEE",
        "palevioletred": "#DB7093",
        "papayawhip": "#FFEFD5",
        "peachpuff": "#FFDAB9",
        "peru": "#CD853F",
        "pink": "#FFC0CB",
        "plum": "#DDA0DD",
        "powderblue": "#B0E0E6",
        "purple": "#800080",
        "red": "#FF0000",
        "rosybrown": "#BC8F8F",
        "royalblue": "#4169E1",
        "saddlebrown": "#8B4513",
        "salmon": "#FA8072",
        "sandybrown": "#FAA460",
        "seagreen": "#2E8B57",
        "seashell": "#FFF5EE",
        "sienna": "#A0522D",
        "silver": "#C0C0C0",
        "skyblue": "#87CEEB",
        "slateblue": "#6A5ACD",
        "slategray": "#708090",
        "snow": "#FFFAFA",
        "springgreen": "#00FF7F",
        "steelblue": "#4682B4",
        "tan": "#D2B48C",
        "teal": "#008080",
        "thistle": "#D8BFD8",
        "tomato": "#FF6347",
        "turquoise": "#40E0D0",
        "violet": "#EE82EE",
        "wheat": "#F5DEB3",
        "white": "#FFFFFF",
        "whitesmoke": "#F5F5F5",
        "yellow": "#FFFF00",
        "yellowgreen": "#9ACD32",
    }.items()
}


class CellStyle(StylePart):
    foreground: Color = Field(default=Color.from_name("white"))
    background: Color = Field(default=Color.from_name("black"))
    bold: bool = False
    dim: bool = False
    italic: bool = False


# https://www.compart.com/en/unicode/block/U+2500
class BorderKind(Enum):
    Light = "││──┌┐└┘"
    LightRounded = "││──╭╮╰╯"
    Heavy = "┃┃━━┏┓┗┛"
    Double = "║║══╔╗╚╝"
    Thick = "▌▐▀▄▛▜▙▟"
    LightShade = "░░░░░░░░"
    MediumShade = "▒▒▒▒▒▒▒▒"
    HeavyShade = "▓▓▓▓▓▓▓▓"
    Star = "********"


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
