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
    "aliceblue": Color.from_hex("#F0F8FF"),
    "antiquewhite": Color.from_hex("#FAEBD7"),
    "aqua": Color.from_hex("#00FFFF"),
    "aquamarine": Color.from_hex("#7FFFD4"),
    "azure": Color.from_hex("#F0FFFF"),
    "beige": Color.from_hex("#F5F5DC"),
    "bisque": Color.from_hex("#FFE4C4"),
    "black": Color.from_hex("#000000"),
    "blanchedalmond": Color.from_hex("#FFEBCD"),
    "blue": Color.from_hex("#0000FF"),
    "blueviolet": Color.from_hex("#8A2BE2"),
    "brown": Color.from_hex("#A52A2A"),
    "burlywood": Color.from_hex("#DEB887"),
    "cadetblue": Color.from_hex("#5F9EA0"),
    "chartreuse": Color.from_hex("#7FFF00"),
    "chocolate": Color.from_hex("#D2691E"),
    "coral": Color.from_hex("#FF7F50"),
    "cornflowerblue": Color.from_hex("#6495ED"),
    "cornsilk": Color.from_hex("#FFF8DC"),
    "crimson": Color.from_hex("#DC143C"),
    "cyan": Color.from_hex("#00FFFF"),
    "darkblue": Color.from_hex("#00008B"),
    "darkcyan": Color.from_hex("#008B8B"),
    "darkgoldenrod": Color.from_hex("#B8860B"),
    "darkgray": Color.from_hex("#A9A9A9"),
    "darkgreen": Color.from_hex("#006400"),
    "darkkhaki": Color.from_hex("#BDB76B"),
    "darkmagenta": Color.from_hex("#8B008B"),
    "darkolivegreen": Color.from_hex("#556B2F"),
    "darkorange": Color.from_hex("#FF8C00"),
    "darkorchid": Color.from_hex("#9932CC"),
    "darkred": Color.from_hex("#8B0000"),
    "darksalmon": Color.from_hex("#E9967A"),
    "darkseagreen": Color.from_hex("#8FBC8F"),
    "darkslateblue": Color.from_hex("#483D8B"),
    "darkslategray": Color.from_hex("#2F4F4F"),
    "darkturquoise": Color.from_hex("#00CED1"),
    "darkviolet": Color.from_hex("#9400D3"),
    "deeppink": Color.from_hex("#FF1493"),
    "deepskyblue": Color.from_hex("#00BFFF"),
    "dimgray": Color.from_hex("#696969"),
    "dodgerblue": Color.from_hex("#1E90FF"),
    "firebrick": Color.from_hex("#B22222"),
    "floralwhite": Color.from_hex("#FFFAF0"),
    "forestgreen": Color.from_hex("#228B22"),
    "fuchsia": Color.from_hex("#FF00FF"),
    "gainsboro": Color.from_hex("#DCDCDC"),
    "ghostwhite": Color.from_hex("#F8F8FF"),
    "gold": Color.from_hex("#FFD700"),
    "goldenrod": Color.from_hex("#DAA520"),
    "gray": Color.from_hex("#808080"),
    "green": Color.from_hex("#008000"),
    "greenyellow": Color.from_hex("#ADFF2F"),
    "honeydew": Color.from_hex("#F0FFF0"),
    "hotpink": Color.from_hex("#FF69B4"),
    "indianred": Color.from_hex("#CD5C5C"),
    "indigo": Color.from_hex("#4B0082"),
    "ivory": Color.from_hex("#FFFFF0"),
    "khaki": Color.from_hex("#F0E68C"),
    "lavender": Color.from_hex("#E6E6FA"),
    "lavenderblush": Color.from_hex("#FFF0F5"),
    "lawngreen": Color.from_hex("#7CFC00"),
    "lemonchiffon": Color.from_hex("#FFFACD"),
    "lightblue": Color.from_hex("#ADD8E6"),
    "lightcoral": Color.from_hex("#F08080"),
    "lightcyan": Color.from_hex("#E0FFFF"),
    "lightgoldenrodyellow": Color.from_hex("#FAFAD2"),
    "lightgreen": Color.from_hex("#90EE90"),
    "lightgray": Color.from_hex("#D3D3D3"),
    "lightpink": Color.from_hex("#FFB6C1"),
    "lightsalmon": Color.from_hex("#FFA07A"),
    "lightseagreen": Color.from_hex("#20B2AA"),
    "lightskyblue": Color.from_hex("#87CEFA"),
    "lightslategray": Color.from_hex("#778899"),
    "lightsteelblue": Color.from_hex("#B0C4DE"),
    "lightyellow": Color.from_hex("#FFFFE0"),
    "lime": Color.from_hex("#00FF00"),
    "limegreen": Color.from_hex("#32CD32"),
    "linen": Color.from_hex("#FAF0E6"),
    "magenta": Color.from_hex("#FF00FF"),
    "maroon": Color.from_hex("#800000"),
    "mediumaquamarine": Color.from_hex("#66CDAA"),
    "mediumblue": Color.from_hex("#0000CD"),
    "mediumorchid": Color.from_hex("#BA55D3"),
    "mediumpurple": Color.from_hex("#9370DB"),
    "mediumseagreen": Color.from_hex("#3CB371"),
    "mediumslateblue": Color.from_hex("#7B68EE"),
    "mediumspringgreen": Color.from_hex("#00FA9A"),
    "mediumturquoise": Color.from_hex("#48D1CC"),
    "mediumvioletred": Color.from_hex("#C71585"),
    "midnightblue": Color.from_hex("#191970"),
    "mintcream": Color.from_hex("#F5FFFA"),
    "mistyrose": Color.from_hex("#FFE4E1"),
    "moccasin": Color.from_hex("#FFE4B5"),
    "navajowhite": Color.from_hex("#FFDEAD"),
    "navy": Color.from_hex("#000080"),
    "oldlace": Color.from_hex("#FDF5E6"),
    "olive": Color.from_hex("#808000"),
    "olivedrab": Color.from_hex("#6B8E23"),
    "orange": Color.from_hex("#FFA500"),
    "orangered": Color.from_hex("#FF4500"),
    "orchid": Color.from_hex("#DA70D6"),
    "palegoldenrod": Color.from_hex("#EEE8AA"),
    "palegreen": Color.from_hex("#98FB98"),
    "paleturquoise": Color.from_hex("#AFEEEE"),
    "palevioletred": Color.from_hex("#DB7093"),
    "papayawhip": Color.from_hex("#FFEFD5"),
    "peachpuff": Color.from_hex("#FFDAB9"),
    "peru": Color.from_hex("#CD853F"),
    "pink": Color.from_hex("#FFC0CB"),
    "plum": Color.from_hex("#DDA0DD"),
    "powderblue": Color.from_hex("#B0E0E6"),
    "purple": Color.from_hex("#800080"),
    "red": Color.from_hex("#FF0000"),
    "rosybrown": Color.from_hex("#BC8F8F"),
    "royalblue": Color.from_hex("#4169E1"),
    "saddlebrown": Color.from_hex("#8B4513"),
    "salmon": Color.from_hex("#FA8072"),
    "sandybrown": Color.from_hex("#FAA460"),
    "seagreen": Color.from_hex("#2E8B57"),
    "seashell": Color.from_hex("#FFF5EE"),
    "sienna": Color.from_hex("#A0522D"),
    "silver": Color.from_hex("#C0C0C0"),
    "skyblue": Color.from_hex("#87CEEB"),
    "slateblue": Color.from_hex("#6A5ACD"),
    "slategray": Color.from_hex("#708090"),
    "snow": Color.from_hex("#FFFAFA"),
    "springgreen": Color.from_hex("#00FF7F"),
    "steelblue": Color.from_hex("#4682B4"),
    "tan": Color.from_hex("#D2B48C"),
    "teal": Color.from_hex("#008080"),
    "thistle": Color.from_hex("#D8BFD8"),
    "tomato": Color.from_hex("#FF6347"),
    "turquoise": Color.from_hex("#40E0D0"),
    "violet": Color.from_hex("#EE82EE"),
    "wheat": Color.from_hex("#F5DEB3"),
    "white": Color.from_hex("#FFFFFF"),
    "whitesmoke": Color.from_hex("#F5F5F5"),
    "yellow": Color.from_hex("#FFFF00"),
    "yellowgreen": Color.from_hex("#9ACD32"),
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
