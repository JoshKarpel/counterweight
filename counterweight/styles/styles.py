from __future__ import annotations

from enum import Enum
from functools import cached_property, lru_cache
from typing import TYPE_CHECKING, Literal, NamedTuple, TypeVar

from cachetools import LRUCache
from pydantic import Field, NonNegativeInt, PositiveInt

from counterweight._utils import merge
from counterweight.types import FrozenForbidExtras

if TYPE_CHECKING:
    pass

S = TypeVar("S", bound="StyleFragment")


STYLE_MERGE_CACHE: LRUCache[tuple[int, int], StyleFragment] = LRUCache(maxsize=2**16)


def merge_style_fragments(left: S, right: S) -> S:
    return type(left).model_validate(
        merge(
            left.mergeable_dump(),
            right.mergeable_dump(),
        )
    )


class StyleFragment(FrozenForbidExtras):
    def __or__(self: S, other: S | None) -> S:
        if other is None:
            return self

        key = (
            self._cached_hash,
            other._cached_hash,
        )
        try:
            return STYLE_MERGE_CACHE[key]  # type: ignore[return-value]
        except KeyError:
            merged = merge_style_fragments(self, other)
            STYLE_MERGE_CACHE[key] = merged
            return merged

    def mergeable_dump(self) -> dict[str, object]:
        d = super().model_dump(exclude_unset=True)

        # Always include the "type" field if present,
        # even if it was not set (important for style merging).
        if "type" in self.__dict__:
            d["type"] = self.__dict__["type"]

        return d

    @cached_property
    def _cached_hash(self) -> int:
        """This is safe because all style fragments are immutable."""
        return hash(self)


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

    @property
    def hex(self) -> str:
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"

    def blend(self, other: Color, alpha: float) -> Color:
        return Color(
            red=int(self.red * (1 - alpha) + other.red * alpha),
            green=int(self.green * (1 - alpha) + other.green * alpha),
            blue=int(self.blue * (1 - alpha) + other.blue * alpha),
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


class CellStyle(StyleFragment):
    foreground: Color = Field(default=Color.from_name("white"))
    background: Color = Field(default=Color.from_name("black"))
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False


class BorderParts(NamedTuple):
    left: str
    right: str
    top: str
    bottom: str
    left_top: str
    right_top: str
    left_bottom: str
    right_bottom: str


# https://www.compart.com/en/unicode/block/U+2500
class BorderKind(Enum):
    Light = BorderParts(
        left="│",
        right="│",
        top="─",
        bottom="─",
        left_top="┌",
        right_top="┐",
        left_bottom="└",
        right_bottom="┘",
    )
    LightRounded = BorderParts(
        left="│",
        right="│",
        top="─",
        bottom="─",
        left_top="╭",
        right_top="╮",
        left_bottom="╰",
        right_bottom="╯",
    )
    LightAngled = BorderParts(
        left="▏",
        right="▕",
        top="▔",
        bottom="▁",
        left_top="/",
        right_top="╲",
        left_bottom="╲",
        right_bottom="/",
    )
    Heavy = BorderParts(
        left="┃",
        right="┃",
        top="━",
        bottom="━",
        left_top="┏",
        right_top="┓",
        left_bottom="┗",
        right_bottom="┛",
    )
    Double = BorderParts(
        left="║",
        right="║",
        top="═",
        bottom="═",
        left_top="╔",
        right_top="╗",
        left_bottom="╚",
        right_bottom="╝",
    )
    Thick = BorderParts(
        left="▌",
        right="▐",
        top="▀",
        bottom="▄",
        left_top="▛",
        right_top="▜",
        left_bottom="▙",
        right_bottom="▟",
    )
    McGugan = BorderParts(  # https://www.willmcgugan.com/blog/tech/post/ceo-just-wants-to-draw-boxes/
        left="▕",
        right="▏",
        top="▁",
        bottom="▔",
        left_top=" ",
        right_top=" ",
        left_bottom=" ",
        right_bottom=" ",
    )
    LightShade = BorderParts(
        left="░",
        right="░",
        top="░",
        bottom="░",
        left_top="░",
        right_top="░",
        left_bottom="░",
        right_bottom="░",
    )
    MediumShade = BorderParts(
        left="▒",
        right="▒",
        top="▒",
        bottom="▒",
        left_top="▒",
        right_top="▒",
        left_bottom="▒",
        right_bottom="▒",
    )
    HeavyShade = BorderParts(
        left="▓",
        right="▓",
        top="▓",
        bottom="▓",
        left_top="▓",
        right_top="▓",
        left_bottom="▓",
        right_bottom="▓",
    )
    Star = BorderParts(
        left="*",
        right="*",
        top="*",
        bottom="*",
        left_top="*",
        right_top="*",
        left_bottom="*",
        right_bottom="*",
    )


class JoinedBorderParts(NamedTuple):
    vertical: str
    horizontal: str
    left_top: str
    right_top: str
    left_bottom: str
    right_bottom: str
    vertical_right: str
    vertical_left: str
    horizontal_top: str
    horizontal_bottom: str
    horizontal_vertical: str

    def select(self, top: bool, bottom: bool, left: bool, right: bool) -> str | None:
        # This could be a lookup table... not sure if that would be better
        match top, bottom, left, right:
            case True, True, True, True:
                return self.horizontal_vertical
            case True, True, True, False:
                return self.vertical_left
            case True, True, False, True:
                return self.vertical_right
            case True, False, True, True:
                return self.horizontal_top
            case False, True, True, True:
                return self.horizontal_bottom
            case True, True, False, False:
                return self.vertical
            case False, False, True, True:
                return self.horizontal
            case True, False, True, False:
                return self.right_bottom
            case True, False, False, True:
                return self.left_bottom
            case False, True, True, False:
                return self.right_top
            case False, True, False, True:
                return self.left_top
            case _:
                return None

    @property
    def connects_right(self) -> frozenset[str]:
        return frozenset(
            {
                self.horizontal,
                self.left_top,
                self.left_bottom,
                self.horizontal_top,
                self.horizontal_bottom,
                self.vertical_right,
                self.horizontal_vertical,
            }
        )

    @property
    def connects_left(self) -> frozenset[str]:
        return frozenset(
            {
                self.horizontal,
                self.right_top,
                self.right_top,
                self.horizontal_top,
                self.horizontal_bottom,
                self.vertical_left,
                self.horizontal_vertical,
            }
        )

    @property
    def connects_top(self) -> frozenset[str]:
        return frozenset(
            {
                self.vertical,
                self.left_bottom,
                self.right_bottom,
                self.vertical_right,
                self.vertical_left,
                self.horizontal_top,
                self.horizontal_vertical,
            }
        )

    @property
    def connects_bottom(self) -> frozenset[str]:
        return frozenset(
            {
                self.vertical,
                self.left_top,
                self.right_top,
                self.vertical_right,
                self.vertical_left,
                self.horizontal_bottom,
                self.horizontal_vertical,
            }
        )


class JoinedBorderKind(Enum):
    Light = JoinedBorderParts(
        vertical="│",
        horizontal="─",
        left_top="┌",
        right_top="┐",
        left_bottom="└",
        right_bottom="┘",
        vertical_right="├",
        vertical_left="┤",
        horizontal_top="┴",
        horizontal_bottom="┬",
        horizontal_vertical="┼",
    )
    LightRounded = JoinedBorderParts(
        vertical="│",
        horizontal="─",
        left_top="╭",
        right_top="╮",
        left_bottom="╰",
        right_bottom="╯",
        vertical_right="├",
        vertical_left="┤",
        horizontal_top="┴",
        horizontal_bottom="┬",
        horizontal_vertical="┼",
    )
    Heavy = JoinedBorderParts(
        vertical="┃",
        horizontal="━",
        left_top="┏",
        right_top="┓",
        left_bottom="┗",
        right_bottom="┛",
        vertical_right="┣",
        vertical_left="┫",
        horizontal_top="┻",
        horizontal_bottom="┳",
        horizontal_vertical="╋",
    )
    Double = JoinedBorderParts(
        vertical="║",
        horizontal="═",
        left_top="╔",
        right_top="╗",
        left_bottom="╚",
        right_bottom="╝",
        vertical_right="╠",
        vertical_left="╣",
        horizontal_top="╩",
        horizontal_bottom="╦",
        horizontal_vertical="╬",
    )


class BorderEdge(Enum):
    Top = "top"
    Bottom = "bottom"
    Left = "left"
    Right = "right"


class Border(StyleFragment):
    kind: BorderKind = Field(default=BorderKind.Light)
    style: CellStyle = Field(default_factory=CellStyle)
    edges: frozenset[BorderEdge] = frozenset({BorderEdge.Top, BorderEdge.Bottom, BorderEdge.Left, BorderEdge.Right})
    contract: int = Field(default=0)


class Margin(StyleFragment):
    top: int = Field(default=0)
    bottom: int = Field(default=0)
    left: int = Field(default=0)
    right: int = Field(default=0)
    color: Color = Field(default=Color.from_name("black"))


class Padding(StyleFragment):
    top: int = Field(default=0)
    bottom: int = Field(default=0)
    left: int = Field(default=0)
    right: int = Field(default=0)
    color: Color = Field(default=Color.from_name("black"))


class Span(StyleFragment):
    width: int | Literal["auto"] = Field(default="auto")
    height: int | Literal["auto"] = Field(default="auto")


class Typography(StyleFragment):
    style: CellStyle = Field(default=CellStyle())
    justify: Literal["left", "center", "right"] = "left"
    wrap: Literal["none", "paragraphs"] = "none"


class Flex(StyleFragment):
    type: Literal["flex"] = "flex"
    direction: Literal["row", "column"] = "row"
    position: Literal["relative"] = "relative"
    weight: PositiveInt | None = 1
    align_self: Literal["none", "start", "center", "end", "stretch"] = "none"
    justify_children: Literal[
        "start",
        "center",
        "end",
        "space-between",
        "space-around",
        "space-evenly",
    ] = "start"
    align_children: Literal[
        "start",
        "center",
        "end",
        "stretch",
    ] = "start"
    gap_children: NonNegativeInt = 0


class Style(StyleFragment):
    layout: Flex = Field(default=Flex())
    hidden: bool = False
    span: Span = Field(default=Span())
    margin: Margin = Field(default=Margin())
    border: Border | None = Field(default=None)
    padding: Padding = Field(default=Padding())
    typography: Typography = Field(default=Typography())
