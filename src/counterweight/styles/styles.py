from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Literal, NamedTuple

import waxy

from counterweight._utils import flyweight

TextJustify = Literal["left", "center", "right"]
TextWrap = Literal["none", "stable", "pretty", "balance"]
ClipTo = Literal["padding", "border", "screen"]
OverflowAnchor = Literal["auto", "none"]


UNSET = sentinel("UNSET")


def or_default[T](value: T | UNSET, default: T) -> T:
    """`value`, or `default` if `value` is `UNSET`."""
    return default if value is UNSET else value


# Keep this a functools.lru_cache: it hashes the key once per lookup, in C, where a Python-level cache
# such as cachetools' LRUCache hashes and compares the key again on every hit, which dominates a cached merge.
@lru_cache(maxsize=2**16)
def merge_style_fragments[S: StyleFragment](left: S, right: S) -> S:
    """
    Merge two fragments field by field: `right`'s value wins wherever it isn't `UNSET`,
    and nested fragments (and `waxy.Style` layouts) merge recursively.
    """
    kwargs: dict[str, object] = {}
    for f in dataclasses.fields(left):  # type: ignore[arg-type]
        if not f.init:
            continue
        left_value = getattr(left, f.name)
        right_value = getattr(right, f.name)
        if right_value is UNSET:
            kwargs[f.name] = left_value
        elif isinstance(right_value, StyleFragment | waxy.Style):
            kwargs[f.name] = left_value | right_value
        else:
            kwargs[f.name] = right_value
    return type(left)(**kwargs)


class StyleFragment:
    __slots__ = ()

    def __or__[S: StyleFragment](self: S, other: S | None) -> S:
        if other is None:
            return self
        return merge_style_fragments(self, other)


class Color(NamedTuple):
    red: int
    green: int
    blue: int

    @classmethod
    def from_name(cls, name: str) -> Color:
        return COLORS_BY_NAME[name]

    @classmethod
    @lru_cache(maxsize=2**14)
    def from_hex(cls, hex: str) -> Color:
        """
        A color from `#rrggbb` or the CSS shorthand `#rgb`, with or without the `#`.
        Any other number of digits, like `#rrggbbaa`'s alpha, raises `ValueError`.
        """
        hex = hex.lstrip("#")
        if len(hex) == 3:
            hex = "".join(digit * 2 for digit in hex)
        if len(hex) != 6:
            raise ValueError(f"A hex color has 3 or 6 digits, not {hex!r}")
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

_WHITE = COLORS_BY_NAME["white"]
_BLACK = COLORS_BY_NAME["black"]


def is_osc_8_uri(uri: str) -> bool:
    """
    Whether `uri` can go in an OSC 8 hyperlink: non-empty, and only printable ASCII,
    since any other character could end the escape sequence early or start another one.
    """
    return bool(uri) and all(" " <= c <= "~" for c in uri)


@flyweight(maxsize=2**10)
@dataclass(frozen=True, slots=True, kw_only=True)
class CellStyle(StyleFragment):
    """
    How to draw a cell's character: its colors and attributes.

    Every field starts `UNSET`. Merging with `|` takes the right side's value wherever it is set,
    including when it is set to the default, so `CellStyle(bold=False)` turns bold off.
    Unset fields resolve to the defaults in
    [`CELL_STYLE_DEFAULTS`][counterweight.styles.CELL_STYLE_DEFAULTS].

    `link` makes the cell a hyperlink to that URI, which the terminal opens when it's clicked
    (an [OSC 8](https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda) hyperlink);
    `None` makes it not a link, overriding a `link` it would otherwise inherit.
    The URI must be printable ASCII, so percent-encode anything else,
    or `CellStyle` raises `ValueError`.
    """

    foreground: Color | UNSET = UNSET
    background: Color | UNSET = UNSET
    bold: bool | UNSET = UNSET
    dim: bool | UNSET = UNSET
    italic: bool | UNSET = UNSET
    underline: bool | UNSET = UNSET
    strikethrough: bool | UNSET = UNSET
    link: str | UNSET | None = UNSET
    _hash: int = field(init=False, repr=False, compare=False, hash=False, default=0)

    def __post_init__(self) -> None:
        if isinstance(self.link, str) and not is_osc_8_uri(self.link):
            raise ValueError(f"A link must be a non-empty URI of printable ASCII characters, not {self.link!r}")
        object.__setattr__(
            self,
            "_hash",
            hash(
                (
                    self.foreground,
                    self.background,
                    self.bold,
                    self.dim,
                    self.italic,
                    self.underline,
                    self.strikethrough,
                    self.link,
                )
            ),
        )

    def __hash__(self) -> int:
        return self._hash


_DEFAULT_CELL_STYLE = CellStyle()


@flyweight(maxsize=2**10)
@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedCellStyle:
    """A [`CellStyle`][counterweight.styles.CellStyle] with every field filled in, as paint and output read it."""

    foreground: Color
    background: Color
    bold: bool
    dim: bool
    italic: bool
    underline: bool
    strikethrough: bool
    link: str | None
    _hash: int = field(init=False, repr=False, compare=False, hash=False, default=0)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_hash",
            hash(
                (
                    self.foreground,
                    self.background,
                    self.bold,
                    self.dim,
                    self.italic,
                    self.underline,
                    self.strikethrough,
                    self.link,
                )
            ),
        )

    def __hash__(self) -> int:
        return self._hash


CELL_STYLE_DEFAULTS = ResolvedCellStyle(
    foreground=_WHITE,
    background=_BLACK,
    bold=False,
    dim=False,
    italic=False,
    underline=False,
    strikethrough=False,
    link=None,
)


@lru_cache(maxsize=2**12)
def resolve_cell_style(style: CellStyle, defaults: ResolvedCellStyle = CELL_STYLE_DEFAULTS) -> ResolvedCellStyle:
    """
    Fill `style`'s unset fields from `defaults`.

    Resolving against a resolved base is the same as merging onto it first:
    `resolve_cell_style(b, resolve_cell_style(a))` equals `resolve_cell_style(a | b)`.
    """
    return ResolvedCellStyle(
        foreground=or_default(style.foreground, defaults.foreground),
        background=or_default(style.background, defaults.background),
        bold=or_default(style.bold, defaults.bold),
        dim=or_default(style.dim, defaults.dim),
        italic=or_default(style.italic, defaults.italic),
        underline=or_default(style.underline, defaults.underline),
        strikethrough=or_default(style.strikethrough, defaults.strikethrough),
        link=or_default(style.link, defaults.link),
    )


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

    def __repr__(self) -> str:
        return f"BorderKind.{self.name}"


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

    def __repr__(self) -> str:
        return f"JoinedBorderKind.{self.name}"


LAYOUT_BORDER_FIELDS = frozenset({"border_top", "border_bottom", "border_left", "border_right"})
BORDER_WIDTHS = (waxy.Length(0), waxy.Length(1))


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedStyle:
    """
    The fields of a [`Style`][counterweight.styles.Style] other than `layout`, every one filled in,
    as paint and the placement of scrolled boxes read them,
    except `z`, which stays `None` when unset, because an element that sets no `z` forms no stacking context.
    """

    z: int | None
    clip_to: ClipTo
    overflow_anchor: OverflowAnchor
    stick_to_end_x: bool
    stick_to_end_y: bool
    margin_color: Color
    padding_color: Color
    content_color: Color

    border_kind: BorderKind | None
    border_style: ResolvedCellStyle
    border_contract: int

    text_style: ResolvedCellStyle
    text_justify: TextJustify
    text_wrap: TextWrap


STYLE_DEFAULTS = ResolvedStyle(
    z=None,
    clip_to="padding",
    overflow_anchor="auto",
    stick_to_end_x=False,
    stick_to_end_y=False,
    margin_color=_BLACK,
    padding_color=_BLACK,
    content_color=_BLACK,
    border_kind=BorderKind.Light,
    border_style=CELL_STYLE_DEFAULTS,
    border_contract=0,
    text_style=CELL_STYLE_DEFAULTS,
    text_justify="left",
    text_wrap="none",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Style(StyleFragment):
    """
    How an element is laid out and drawn.

    Every field except `layout` starts `UNSET`, and the nested `border_style` and `text_style`
    start as empty `CellStyle`s. Merging with `|` takes the right side's value wherever it is set,
    including when it is set to the default, so `border | border_none` has no border.
    `layout` merges the same way, field by field.
    Unset fields resolve to the defaults in [`STYLE_DEFAULTS`][counterweight.styles.STYLE_DEFAULTS].

    A border side is drawn where its width in `layout` (`border_top`, ...) is 1,
    and `border_kind` chooses the characters it's drawn with.
    A `border_kind` of `None` removes the border, along with the space reserved for it.
    Each side is one cell, so a `Style` whose `layout` sets a border width other than
    `Length(0)` or `Length(1)` raises `ValueError`.

    `clip_to` chooses what clips the element.
    With `"padding"`, the default, or `"border"`, it's its parent's padding or border box,
    on each axis where the parent's overflow is `Hidden`, `Clip` or `Scroll`,
    and every clip above the parent clips the element too;
    `"border"` lets a title be drawn on its parent's border.
    With `"screen"`, the element is unclipped: no ancestor clips it, so a popup can reach past them,
    though its own overflow still clips its descendants.

    `overflow_anchor` and `stick_to_end_x` and `stick_to_end_y` choose how a scroll container's offset follows
    its content when the content changes.
    With `overflow_anchor` `"auto"`, the default, a scroll container keeps the content in view where it was,
    as CSS's [`overflow-anchor`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow-anchor) does;
    with `"none"`, a scroll container keeps its offset, and nothing inside an element that sets it is
    an anchor for the scroll container around it.
    A scroll container that sticks to its end on an axis and is scrolled to its end there
    stays scrolled to its end when its content grows.
    """

    layout: waxy.Style = field(default_factory=waxy.Style)

    z: int | UNSET = UNSET
    clip_to: ClipTo | UNSET = UNSET
    overflow_anchor: OverflowAnchor | UNSET = UNSET
    stick_to_end_x: bool | UNSET = UNSET
    stick_to_end_y: bool | UNSET = UNSET
    margin_color: Color | UNSET = UNSET
    padding_color: Color | UNSET = UNSET
    content_color: Color | UNSET = UNSET

    border_kind: BorderKind | UNSET | None = UNSET
    border_style: CellStyle = _DEFAULT_CELL_STYLE
    border_contract: int | UNSET = UNSET

    text_style: CellStyle = _DEFAULT_CELL_STYLE
    text_justify: TextJustify | UNSET = UNSET
    text_wrap: TextWrap | UNSET = UNSET

    _hash: int = field(init=False, repr=False, compare=False, hash=False, default=0)
    resolved: ResolvedStyle = field(init=False, repr=False, compare=False, hash=False)
    """
    This style's drawing fields, with the unset ones filled from `STYLE_DEFAULTS`,
    resolved once when the style is built, since paint reads them for every element on every frame.
    """

    def __post_init__(self) -> None:
        for name in sorted(self.layout.fields_set & LAYOUT_BORDER_FIELDS):
            width = getattr(self.layout, name)
            if width not in BORDER_WIDTHS:
                raise ValueError(
                    f"Style.layout sets {name} to {width!r}, "
                    f"but a border side is one cell, so its width must be Length(0) or Length(1)"
                )
        object.__setattr__(
            self,
            "_hash",
            hash(
                (
                    self.layout,
                    self.z,
                    self.clip_to,
                    self.overflow_anchor,
                    self.stick_to_end_x,
                    self.stick_to_end_y,
                    self.margin_color,
                    self.padding_color,
                    self.content_color,
                    self.border_kind,
                    self.border_style,
                    self.border_contract,
                    self.text_style,
                    self.text_justify,
                    self.text_wrap,
                )
            ),
        )
        object.__setattr__(self, "resolved", self._resolve())

    def __hash__(self) -> int:
        return self._hash

    def _resolve(self) -> ResolvedStyle:
        """Fill this style's unset drawing fields from `STYLE_DEFAULTS`."""
        defaults = STYLE_DEFAULTS
        return ResolvedStyle(
            z=or_default(self.z, defaults.z),
            clip_to=or_default(self.clip_to, defaults.clip_to),
            overflow_anchor=or_default(self.overflow_anchor, defaults.overflow_anchor),
            stick_to_end_x=or_default(self.stick_to_end_x, defaults.stick_to_end_x),
            stick_to_end_y=or_default(self.stick_to_end_y, defaults.stick_to_end_y),
            margin_color=or_default(self.margin_color, defaults.margin_color),
            padding_color=or_default(self.padding_color, defaults.padding_color),
            content_color=or_default(self.content_color, defaults.content_color),
            border_kind=or_default(self.border_kind, defaults.border_kind),
            border_style=resolve_cell_style(self.border_style, defaults.border_style),
            border_contract=or_default(self.border_contract, defaults.border_contract),
            text_style=resolve_cell_style(self.text_style, defaults.text_style),
            text_justify=or_default(self.text_justify, defaults.text_justify),
            text_wrap=or_default(self.text_wrap, defaults.text_wrap),
        )


_EMPTY_STYLE = Style()


def merge(*styles: Style | None) -> Style:
    """
    Merge styles left to right, the same as chaining them with `|`.

    Later styles win wherever they set a field, and `None`s are skipped wherever they appear,
    so a conditional style can be passed as `hover_style if hovered else None`.
    With no styles, or only `None`s, the result is an empty `Style()`.
    """
    merged = _EMPTY_STYLE
    for style in styles:
        merged = merged | style
    return merged
