"""
Gradients: colors that change across a box, as CSS's `linear-gradient`, `radial-gradient` and `conic-gradient` do,
and the pure functions that paint draws them with.

A gradient's geometry is CSS Images 4's, computed in visual units, where a row is `aspect` columns tall,
over a box that spans the centers of its first and last cells, so its corner cells take the end colors.
Paint draws a gradient in two parts that change for different reasons:
its `Ramp`, the colors along it, which depends only on its stops and how they're interpolated,
and a `field`, the ramp entry each cell of a box takes, which depends only on its geometry and the box's size.
"""

from __future__ import annotations

import colorsys
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from functools import lru_cache
from itertools import pairwise
from math import atan2
from math import cbrt
from math import cos
from math import degrees
from math import hypot
from math import inf
from math import isnan
from math import log
from math import nan
from math import pi
from math import radians
from math import sin
from math import sqrt
from typing import Literal
from typing import assert_never

import waxy

from counterweight.geometry import Region
from counterweight.styles._styles import Color

type Interpolation = Literal[
    "srgb",
    "srgb-linear",
    "oklab",
    "oklch",
    "lab",
    "lch",
    "hsl",
    "hwb",
    "xyz",
    "xyz-d50",
    "xyz-d65",
]
"""
The color space a gradient's colors are mixed in, as CSS's `in <color-space>` names it.
`"oklch"`, `"lch"`, `"hsl"` and `"hwb"` are polar, so their hue takes a `HueMethod`.
"""

type HueMethod = Literal["shorter", "longer", "increasing", "decreasing"]
"""Which way around the hue circle a polar color space mixes two hues, as CSS's `<hue-interpolation-method>`."""

type Box = Literal["margin", "border", "padding", "content"]
"""Which of an element's boxes a gradient maps over."""

type Coordinate = float | waxy.Length
"""A point along one axis of a box: a fraction of the way across it, or a number of cells from its first cell."""

type SideOrCorner = Literal[
    "top",
    "right",
    "bottom",
    "left",
    "top left",
    "top right",
    "bottom left",
    "bottom right",
    "left top",
    "right top",
    "left bottom",
    "right bottom",
]
"""Where a linear gradient points, as CSS's `to <side-or-corner>`."""

type Extent = Literal["closest-side", "closest-corner", "farthest-side", "farthest-corner"]
"""How large a radial gradient's ending shape is, by the side or corner of the box it reaches."""

type Shape = Literal["circle", "ellipse"]

POLAR_SPACES = frozenset({"oklch", "lch", "hsl", "hwb"})

SEGMENT_ENTRIES = 4096
"""
How many entries a ramp has between each pair of adjacent stops, spaced evenly in how much of the second color
each mixes in, so a hint's curve is no harder to follow than a straight blend.
It's the fewest that keep every lookup within a channel step of the exact color,
which the tests check in every color space.
"""


@dataclass(frozen=True, slots=True)
class Stop:
    """A color stop: `color` at `at`, a fraction of the gradient line, or wherever stop fixup puts it if `None`."""

    color: Color
    at: float | None = None


@dataclass(frozen=True, slots=True)
class Hint:
    """
    A transition hint, between two color stops: where along the gradient line their colors mix half and half,
    as a fraction of the gradient line.
    """

    at: float


type Stops = tuple[Stop | Hint, ...]


@dataclass(frozen=True, slots=True)
class ResolvedStops:
    """
    A gradient's stops after CSS's stop fixup: every color stop at a position no smaller than the one before it,
    and for each pair of adjacent stops, the exponent its hint raises the fraction between them to,
    or `None` without a hint (or with one halfway between them).
    """

    positions: tuple[float, ...]
    colors: tuple[Color, ...]
    exponents: tuple[float | None, ...]


def resolve_stops(stops: Stops) -> ResolvedStops:
    """
    Fix up `stops` as [CSS Images 4](https://drafts.csswg.org/css-images-4/#color-stop-fixup) does.
    Raises `ValueError` for fewer than two color stops, or a hint that isn't between two color stops.
    """
    if sum(isinstance(stop, Stop) for stop in stops) < 2:
        raise ValueError(f"A gradient needs at least two color stops, not {stops!r}")
    for index, stop in enumerate(stops):
        if isinstance(stop, Hint) and not (
            0 < index < len(stops) - 1 and isinstance(stops[index - 1], Stop) and isinstance(stops[index + 1], Stop)
        ):
            raise ValueError(f"A hint goes between two color stops, but {stop!r} is at index {index} of {stops!r}")

    specified: list[float | None] = [stop.at for stop in stops]
    if specified[0] is None:
        specified[0] = 0
    if specified[-1] is None:
        specified[-1] = 1

    largest = -inf
    for index, position in enumerate(specified):
        if position is not None:
            largest = max(largest, position)
            specified[index] = largest

    # Each color stop with its position, and the position of the hint before it, if there is one.
    placed: list[tuple[Color, float | None, float | None]] = []
    hint: float | None = None
    for stop, position in zip(stops, specified, strict=True):
        if isinstance(stop, Hint):
            hint = position
        else:
            placed.append((stop.color, position, hint))
            hint = None

    positions: list[float] = []
    run_start = 0
    for index, (_, position, _) in enumerate(placed):
        if position is None:
            continue
        if positions:
            start = positions[-1]
            missing = index - run_start
            positions.extend(start + (position - start) * step / missing for step in range(1, missing))
        positions.append(position)
        run_start = index
    colors = [color for color, _, _ in placed]
    hints = [hint for _, _, hint in placed[1:]]

    return ResolvedStops(
        positions=tuple(positions),
        colors=tuple(colors),
        exponents=tuple(
            _hint_exponent(hint, start, end)
            for hint, start, end in zip(hints, positions[:-1], positions[1:], strict=True)
        ),
    )


def _hint_exponent(hint: float | None, start: float, end: float) -> float | None:
    """
    The exponent a hint at `hint` raises the fraction between stops at `start` and `end` to,
    `log(0.5) / log(H)` for the hint's fraction `H` of the way between them,
    or `None` for no hint, a hint halfway between them, or stops at the same position, which no fraction is between.
    """
    if hint is None or end == start:
        return None
    fraction = (hint - start) / (end - start)
    if fraction == 0.5:
        return None
    if fraction <= 0:
        return 0
    if fraction >= 1:
        return inf
    return log(0.5) / log(fraction)


def _validate_interpolation(interpolation: Interpolation, hue: HueMethod) -> None:
    if hue != "shorter" and interpolation not in POLAR_SPACES:
        raise ValueError(f"A hue method only applies in a polar color space, not {interpolation!r}")


@dataclass(frozen=True, slots=True, kw_only=True)
class LinearGradient:
    """
    Colors that change along a line through the middle of the box, as CSS's
    [`linear-gradient`](https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/linear-gradient) does.

    `direction` is an angle in degrees, where 0 points up and angles turn clockwise, so 90 points right,
    or the side or corner the gradient points to, where a corner points the way that puts the line the gradient
    is halfway along through the other two corners, so the corner takes the last color whatever the box's shape.
    The stops' positions are fractions of the gradient line, which is as long as the box is across in its direction.

    Building one fixes up its stops, and raises `ValueError` for fewer than two color stops,
    a hint that isn't between two of them, or a hue method in a color space that isn't polar.
    """

    stops: Stops
    direction: float | SideOrCorner = "bottom"
    repeating: bool = False
    interpolation: Interpolation = "oklab"
    hue: HueMethod = "shorter"
    box: Box | None = None
    resolved: ResolvedStops = dataclass_field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        _validate_interpolation(self.interpolation, self.hue)
        object.__setattr__(self, "resolved", resolve_stops(self.stops))


@dataclass(frozen=True, slots=True, kw_only=True)
class RadialGradient:
    """
    Colors that change outward from a point, as CSS's
    [`radial-gradient`](https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/radial-gradient) does.

    The stops' positions are fractions of the way from the center, `at`, to the ending shape,
    a `shape` whose `size` is the side or corner of the box it reaches, or its radius:
    one `Length` for a circle, in columns, and two for an ellipse, in columns and rows,
    either of which can also be a fraction of the box's width or height.

    Building one fixes up its stops, and raises `ValueError` for fewer than two color stops,
    a hint that isn't between two of them, a hue method in a color space that isn't polar,
    a `size` that doesn't match its `shape`, or a negative radius.
    """

    stops: Stops
    shape: Shape = "ellipse"
    size: Extent | waxy.Length | tuple[Coordinate, Coordinate] = "farthest-corner"
    at: tuple[Coordinate, Coordinate] = (0.5, 0.5)
    repeating: bool = False
    interpolation: Interpolation = "oklab"
    hue: HueMethod = "shorter"
    box: Box | None = None
    resolved: ResolvedStops = dataclass_field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        _validate_interpolation(self.interpolation, self.hue)
        match self.size:
            case waxy.Length() if self.shape == "ellipse":
                raise ValueError(f"An ellipse's size is two radii or an extent, not {self.size!r}")
            case tuple() if self.shape == "circle":
                raise ValueError(f"A circle's size is one radius or an extent, not {self.size!r}")
            case _:
                pass
        match self.size:
            case waxy.Length() as radius:
                radii: tuple[Coordinate, ...] = (radius,)
            case tuple() as radii:
                pass
            case _:
                radii = ()
        if any(_coordinate_value(radius) < 0 for radius in radii):
            raise ValueError(f"A radius can't be negative, as in {self.size!r}")
        object.__setattr__(self, "resolved", resolve_stops(self.stops))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConicGradient:
    """
    Colors that change around a point, as CSS's
    [`conic-gradient`](https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/conic-gradient) does.

    The stops' positions are fractions of a turn clockwise from `start`, an angle in degrees where 0 points up,
    around the center, `at`.

    Building one fixes up its stops, and raises `ValueError` for fewer than two color stops,
    a hint that isn't between two of them, or a hue method in a color space that isn't polar.
    """

    stops: Stops
    start: float = 0
    at: tuple[Coordinate, Coordinate] = (0.5, 0.5)
    repeating: bool = False
    interpolation: Interpolation = "oklab"
    hue: HueMethod = "shorter"
    box: Box | None = None
    resolved: ResolvedStops = dataclass_field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        _validate_interpolation(self.interpolation, self.hue)
        object.__setattr__(self, "resolved", resolve_stops(self.stops))


type Gradient = LinearGradient | RadialGradient | ConicGradient
"""A color that changes across the box it maps over, which any color slot of a style can hold."""

type StopLike = Color | tuple[Color, float] | tuple[Color, float, float] | Hint
"""
A stop as the gradient functions take it, as CSS spells one:
a bare color, a color at a position, a color from one position to another (two stops), or a hint.
"""


def _stops(stops: tuple[StopLike, ...]) -> Stops:
    built: list[Stop | Hint] = []
    for stop in stops:
        match stop:
            case Hint():
                built.append(stop)
            case Color():
                built.append(Stop(stop))
            case (Color() as color, float() | int() as at):
                built.append(Stop(color, at))
            case (Color() as color, float() | int() as start, float() | int() as end):
                built.extend((Stop(color, start), Stop(color, end)))
            case _ as unreachable:
                assert_never(unreachable)
    return tuple(built)


def linear_gradient(
    *stops: StopLike,
    to: SideOrCorner | None = None,
    angle: float | None = None,
    repeating: bool = False,
    interpolation: Interpolation = "oklab",
    hue: HueMethod = "shorter",
    box: Box | None = None,
) -> LinearGradient:
    """
    A [`LinearGradient`][counterweight.gradients.LinearGradient] through `stops`,
    pointing `to` a side or corner, or at an `angle` in degrees, or down if neither is given.
    Giving both raises `ValueError`.
    """
    if to is not None and angle is not None:
        raise ValueError(f"A linear gradient points to a side or corner or at an angle, not both {to!r} and {angle!r}")
    return LinearGradient(
        stops=_stops(stops),
        direction=angle if angle is not None else to if to is not None else "bottom",
        repeating=repeating,
        interpolation=interpolation,
        hue=hue,
        box=box,
    )


def radial_gradient(
    *stops: StopLike,
    shape: Shape | None = None,
    size: Extent | waxy.Length | tuple[Coordinate, Coordinate] = "farthest-corner",
    at: tuple[Coordinate, Coordinate] = (0.5, 0.5),
    repeating: bool = False,
    interpolation: Interpolation = "oklab",
    hue: HueMethod = "shorter",
    box: Box | None = None,
) -> RadialGradient:
    """
    A [`RadialGradient`][counterweight.gradients.RadialGradient] through `stops`, centered `at` a point.
    Without a `shape`, it's a circle if `size` is one radius, and an ellipse otherwise, as in CSS.
    """
    return RadialGradient(
        stops=_stops(stops),
        shape=shape if shape is not None else "circle" if isinstance(size, waxy.Length) else "ellipse",
        size=size,
        at=at,
        repeating=repeating,
        interpolation=interpolation,
        hue=hue,
        box=box,
    )


def conic_gradient(
    *stops: StopLike,
    start: float = 0,
    at: tuple[Coordinate, Coordinate] = (0.5, 0.5),
    repeating: bool = False,
    interpolation: Interpolation = "oklab",
    hue: HueMethod = "shorter",
    box: Box | None = None,
) -> ConicGradient:
    """A [`ConicGradient`][counterweight.gradients.ConicGradient] through `stops`, around a point `at`."""
    return ConicGradient(
        stops=_stops(stops),
        start=start,
        at=at,
        repeating=repeating,
        interpolation=interpolation,
        hue=hue,
        box=box,
    )


# Color spaces.
# Each is a triple of floats; a polar space's hue is in degrees, and NaN where it's powerless,
# as in an achromatic color, which CSS Color 4 interpolates as missing: it takes the other color's hue.

type Triple = tuple[float, float, float]
type Matrix = tuple[Triple, Triple, Triple]

_SRGB_TO_XYZ_D65: Matrix = (
    (0.41239079926595934, 0.357584339383878, 0.1804807884018343),
    (0.21263900587151027, 0.715168678767756, 0.07219231536073371),
    (0.01933081871559182, 0.11919477979462598, 0.9505321522496607),
)
_D65_TO_D50: Matrix = (
    (1.0479298208405488, 0.022946793341019088, -0.05019222954313557),
    (0.029627815688159344, 0.990434484573249, -0.01707382502938514),
    (-0.009243058152591178, 0.015055144896577895, 0.7518742899580008),
)
_LINEAR_TO_LMS: Matrix = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
_LMS_TO_OKLAB: Matrix = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)
# Its Y is 1, so Y needs no scaling into or out of Lab.
_D50_WHITE: Triple = (0.3457 / 0.3585, 1.0, (1.0 - 0.3457 - 0.3585) / 0.3585)
_LAB_EPSILON = 216 / 24389
_LAB_KAPPA = 24389 / 27

ACHROMATIC_CHROMA = {"oklch": 1e-6, "lch": 1e-4}
"""How small a chroma is achromatic, which a gray's conversion leaves a rounding error above zero."""


def _apply(matrix: Matrix, vector: Triple) -> Triple:
    x, y, z = vector
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z,
    )


def _inverse(m: Matrix) -> Matrix:
    (a, b, c), (d, e, f), (g, h, i) = m
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return (
        ((e * i - f * h) / determinant, (c * h - b * i) / determinant, (b * f - c * e) / determinant),
        ((f * g - d * i) / determinant, (a * i - c * g) / determinant, (c * d - a * f) / determinant),
        ((d * h - e * g) / determinant, (b * g - a * h) / determinant, (a * e - b * d) / determinant),
    )


_XYZ_D65_TO_SRGB = _inverse(_SRGB_TO_XYZ_D65)
_D50_TO_D65 = _inverse(_D65_TO_D50)
_LMS_TO_LINEAR = _inverse(_LINEAR_TO_LMS)
_OKLAB_TO_LMS = _inverse(_LMS_TO_OKLAB)


def _to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _from_linear(channel: float) -> float:
    """The gamma-encoded sRGB channel of a linear one, which may be outside the gamut, and is clipped later."""
    if channel <= 0.0031308:
        return channel * 12.92
    return 1.055 * channel ** (1 / 2.4) - 0.055


def _to_polar(lightness: float, a: float, b: float, achromatic: float) -> Triple:
    chroma = hypot(a, b)
    return lightness, chroma, nan if chroma < achromatic else degrees(atan2(b, a)) % 360


def _from_polar(lightness: float, chroma: float, hue: float) -> Triple:
    hue = 0 if isnan(hue) else radians(hue)
    return lightness, chroma * cos(hue), chroma * sin(hue)


def _lab_f(value: float) -> float:
    return cbrt(value) if value > _LAB_EPSILON else (_LAB_KAPPA * value + 16) / 116


def _lab_f_inverse(value: float) -> float:
    return value**3 if value**3 > _LAB_EPSILON else (116 * value - 16) / _LAB_KAPPA


def to_space(color: Color, space: Interpolation) -> Triple:
    """`color`'s coordinates in `space`, with a polar space's hue NaN where it's powerless."""
    srgb = (color.red / 255, color.green / 255, color.blue / 255)
    match space:
        case "srgb":
            return srgb
        case "hsl":
            hue, lightness, saturation = colorsys.rgb_to_hls(*srgb)
            return nan if saturation == 0 else hue * 360, saturation, lightness
        case "hwb":
            hue, saturation, value = colorsys.rgb_to_hsv(*srgb)
            return nan if saturation == 0 else hue * 360, (1 - saturation) * value, 1 - value
        case _:
            pass
    linear = (_to_linear(srgb[0]), _to_linear(srgb[1]), _to_linear(srgb[2]))
    match space:
        case "srgb-linear":
            return linear
        case "oklab" | "oklch":
            l, m, s = _apply(_LINEAR_TO_LMS, linear)
            lab = _apply(_LMS_TO_OKLAB, (cbrt(l), cbrt(m), cbrt(s)))
            return lab if space == "oklab" else _to_polar(*lab, achromatic=ACHROMATIC_CHROMA["oklch"])
        case "xyz" | "xyz-d65":
            return _apply(_SRGB_TO_XYZ_D65, linear)
        case _:
            pass
    x, y, z = _apply(_D65_TO_D50, _apply(_SRGB_TO_XYZ_D65, linear))
    if space == "xyz-d50":
        return x, y, z
    fx, fy, fz = _lab_f(x / _D50_WHITE[0]), _lab_f(y), _lab_f(z / _D50_WHITE[2])
    lab = (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))
    return lab if space == "lab" else _to_polar(*lab, achromatic=ACHROMATIC_CHROMA["lch"])


def from_space(coordinates: Triple, space: Interpolation) -> Color:
    """The sRGB color at `coordinates` in `space`, with each channel clipped to the sRGB gamut and rounded."""
    match space:
        case "srgb":
            return _clipped(coordinates)
        case "hsl":
            hue, saturation, lightness = coordinates
            # colorsys wraps a hue past a turn around, and ignores it where saturation is 0, as for a missing one.
            return _clipped(colorsys.hls_to_rgb(0 if isnan(hue) else hue / 360, lightness, saturation))
        case "hwb":
            hue, whiteness, blackness = coordinates
            if whiteness + blackness >= 1:
                gray = whiteness / (whiteness + blackness)
                return _clipped((gray, gray, gray))
            value = 1 - blackness
            return _clipped(colorsys.hsv_to_rgb(0 if isnan(hue) else hue / 360, 1 - whiteness / value, value))
        case "srgb-linear":
            linear = coordinates
        case "oklab" | "oklch":
            lab = coordinates if space == "oklab" else _from_polar(*coordinates)
            l, m, s = _apply(_OKLAB_TO_LMS, lab)
            linear = _apply(_LMS_TO_LINEAR, (l**3, m**3, s**3))
        case "xyz" | "xyz-d65":
            linear = _apply(_XYZ_D65_TO_SRGB, coordinates)
        case "xyz-d50" | "lab" | "lch":
            if space == "xyz-d50":
                xyz_d50 = coordinates
            else:
                lightness, a, b = coordinates if space == "lab" else _from_polar(*coordinates)
                fy = (lightness + 16) / 116
                xyz_d50 = (
                    _lab_f_inverse(fy + a / 500) * _D50_WHITE[0],
                    fy**3 if lightness > _LAB_KAPPA * _LAB_EPSILON else lightness / _LAB_KAPPA,
                    _lab_f_inverse(fy - b / 200) * _D50_WHITE[2],
                )
            linear = _apply(_XYZ_D65_TO_SRGB, _apply(_D50_TO_D65, xyz_d50))
        case _ as unreachable:
            assert_never(unreachable)
    return _clipped((_from_linear(linear[0]), _from_linear(linear[1]), _from_linear(linear[2])))


def _clipped(srgb: tuple[float, float, float]) -> Color:
    return Color(*(int(min(max(channel, 0.0), 1.0) * 255 + 0.5) for channel in srgb))


def _hue_index(space: Interpolation) -> int | None:
    """Which coordinate of `space` is its hue, or `None` if it isn't polar."""
    match space:
        case "oklch" | "lch":
            return 2
        case "hsl" | "hwb":
            return 0
        case _:
            return None


def _fixed_up_hues(first: float, second: float, method: HueMethod) -> tuple[float, float]:
    """
    Two hues adjusted as [CSS Color 4](https://drafts.csswg.org/css-color-4/#hue-interpolation) adjusts them
    so that mixing them linearly goes around the hue circle the way `method` says,
    with a missing hue taking the other's.
    """
    if isnan(first) and isnan(second):
        return 0, 0
    if isnan(first):
        return second, second
    if isnan(second):
        return first, first
    difference = second - first
    match method:
        case "shorter":
            if difference > 180:
                first += 360
            elif difference < -180:
                second += 360
        case "longer":
            if 0 < difference < 180:
                first += 360
            elif -180 < difference <= 0:
                second += 360
        case "increasing":
            if second < first:
                second += 360
        case "decreasing":
            if first < second:
                first += 360
        case _ as unreachable:
            assert_never(unreachable)
    return first, second


def _segment_ends(first: Triple, second: Triple, space: Interpolation, method: HueMethod) -> tuple[Triple, Triple]:
    """Two stops' coordinates, ready to mix linearly, with any hue between them fixed up."""
    index = _hue_index(space)
    if index is None:
        return first, second
    start, end = _fixed_up_hues(first[index], second[index], method)
    return _with(first, index, start), _with(second, index, end)


def _with(coordinates: Triple, index: int, value: float) -> Triple:
    values = list(coordinates)
    values[index] = value
    return values[0], values[1], values[2]


def _mix(first: Triple, second: Triple, weight: float) -> Triple:
    return (
        first[0] + (second[0] - first[0]) * weight,
        first[1] + (second[1] - first[1]) * weight,
        first[2] + (second[2] - first[2]) * weight,
    )


@dataclass(frozen=True, slots=True, eq=False)
class Ramp:
    """
    The colors along a gradient, by entry, and which entry each position along it takes.

    Each pair of adjacent stops has `SEGMENT_ENTRIES` entries, spaced evenly in how much of the second color
    each mixes in, after the hint between them; a final entry is the gradient's average color,
    which a repeating gradient takes where it repeats too finely to draw.
    An entry's color is computed when it's first asked for, so a ramp costs only the entries some cell takes.
    """

    stops: ResolvedStops
    repeating: bool
    interpolation: Interpolation
    segments: tuple[tuple[Triple, Triple], ...]
    colors: dict[int, Color] = dataclass_field(default_factory=dict)

    @property
    def average_index(self) -> int:
        return len(self.segments) * SEGMENT_ENTRIES

    def index(self, position: float) -> int:
        """
        The entry a point `position` along the gradient takes, which is past its end at `inf`.
        Where several stops share a position, the point takes the last one's color.
        """
        positions = self.stops.positions
        first = positions[0]
        if self.repeating:
            span = positions[-1] - first
            if span == 0 or position == inf:
                return self.average_index
            position = first + (position - first) % span
        if position < first:
            return 0
        if position >= positions[-1]:
            return self.average_index - 1
        segment = bisect_right(positions, position) - 1
        start = positions[segment]
        fraction = (position - start) / (positions[segment + 1] - start)
        if (exponent := self.stops.exponents[segment]) is not None:
            fraction **= exponent
        return segment * SEGMENT_ENTRIES + int(fraction * (SEGMENT_ENTRIES - 1) + 0.5)

    def indices(self, positions: list[float]) -> tuple[int, ...]:
        """The entry each of `positions` takes, as `index` gives it, faster for the common gradient of two stops."""
        stops = self.stops
        if len(stops.positions) != 2 or stops.exponents[0] is not None or self.repeating:
            return tuple(map(self.index, positions))
        first, last = stops.positions
        if first == last:
            return tuple([0 if position < first else SEGMENT_ENTRIES - 1 for position in positions])
        scale = (SEGMENT_ENTRIES - 1) / (last - first)
        top = SEGMENT_ENTRIES - 1
        return tuple(
            [
                0 if position <= first else top if position >= last else int((position - first) * scale + 0.5)
                for position in positions
            ]
        )

    def color(self, index: int) -> Color:
        """The color of entry `index`."""
        try:
            return self.colors[index]
        except KeyError:
            pass
        if index == self.average_index:
            coordinates = self._average()
        else:
            segment, step = divmod(index, SEGMENT_ENTRIES)
            first, second = self.segments[segment]
            coordinates = _mix(first, second, step / (SEGMENT_ENTRIES - 1))
        color = self.colors[index] = from_space(coordinates, self.interpolation)
        return color

    def _average(self) -> Triple:
        """
        The average of the gradient's colors along it, in its color space,
        or, if its stops are all at one position, of the gradient with the same colors spaced evenly,
        as [CSS Images 4](https://drafts.csswg.org/css-images-4/#repeating-gradients) takes for both.
        """
        positions = self.stops.positions
        span = positions[-1] - positions[0]
        total = [0.0, 0.0, 0.0]
        for (first, second), start, end, exponent in zip(
            self.segments, positions[:-1], positions[1:], self.stops.exponents, strict=True
        ):
            weight = (end - start) / span if span else 1 / len(self.segments)
            # The mean of fraction ** exponent from 0 to 1.
            mean = 0.5 if exponent is None or not span else 1 / (exponent + 1)
            for channel, value in enumerate(_mix(first, second, mean)):
                total[channel] += weight * value
        return total[0], total[1], total[2]


@lru_cache(maxsize=2**8)
def ramp_of(stops: ResolvedStops, repeating: bool, interpolation: Interpolation, hue: HueMethod) -> Ramp:
    """The ramp of a gradient with these `stops`, repeating or not, mixed in `interpolation` with `hue`."""
    coordinates = [to_space(color, interpolation) for color in stops.colors]
    return Ramp(
        stops=stops,
        repeating=repeating,
        interpolation=interpolation,
        segments=tuple(_segment_ends(first, second, interpolation, hue) for first, second in pairwise(coordinates)),
    )


def ramp(gradient: Gradient) -> Ramp:
    """The ramp of `gradient`'s colors."""
    return ramp_of(gradient.resolved, gradient.repeating, gradient.interpolation, gradient.hue)


# Geometry.
# Points are in visual units, where a row is `aspect` columns tall, measured from the center of the box's top left cell,
# and the gradient box spans from there to the center of its bottom right cell.

type Indices = tuple[tuple[int, ...], ...]


def field_indices(gradient: Gradient, width: int, height: int, aspect: float, region: Region) -> Indices:
    """
    The ramp entry each cell of `region` takes, row by row,
    for `gradient` mapped over a box of `width` by `height` cells,
    where `region` is relative to the box's top left cell, and can reach outside it,
    where the gradient's geometry continues.
    """
    positions = _positions(gradient, max(width - 1, 0), max(height - 1, 0) * aspect, aspect)
    indices = ramp(gradient).indices
    columns = range(region.left, region.right)
    return tuple(indices(positions(columns, y)) for y in range(region.top, region.bottom))


type RowPositions = Callable[[range, int], list[float]]


def _positions(gradient: Gradient, width: float, height: float, aspect: float) -> RowPositions:
    """
    For a box `width` by `height` visual units between its corner cells' centers,
    a function from columns and a row to the position along `gradient` of each of those cells.
    """
    match gradient:
        case LinearGradient(direction=direction):
            return _linear_positions(_angle(direction, width, height), width, height, aspect)
        case RadialGradient(shape=shape, size=size, at=at):
            center_x, center_y = _point(at, width, height, aspect)
            radius_x, radius_y = _radii(shape, size, center_x, center_y, width, height, aspect)
            return _radial_positions(shape, center_x, center_y, radius_x, radius_y, aspect)
        case ConicGradient(start=start, at=at):
            center_x, center_y = _point(at, width, height, aspect)
            return _conic_positions(center_x, center_y, start, aspect)
        case _ as unreachable:
            assert_never(unreachable)


def _angle(direction: float | SideOrCorner, width: float, height: float) -> float:
    """
    The angle in radians, clockwise from up, that a linear gradient points at,
    where a corner is the angle that puts the line through its middle through the other two corners.
    """
    match direction:
        case float() | int():
            return radians(direction)
        case "top":
            return 0
        case "right":
            return pi / 2
        case "bottom":
            return pi
        case "left":
            return 3 * pi / 2
        case "top right" | "right top":
            return atan2(height, width)
        case "bottom right" | "right bottom":
            return atan2(height, -width)
        case "bottom left" | "left bottom":
            return atan2(-height, -width)
        case "top left" | "left top":
            return atan2(-height, width)
        case _ as unreachable:
            assert_never(unreachable)


def _linear_positions(angle: float, width: float, height: float, aspect: float) -> RowPositions:
    """
    Positions along a gradient line through the middle of the box, pointing at `angle`,
    as long as the box is across in that direction, which is halfway along it everywhere if it has no length.
    """
    # Rounded so that axis-aligned directions have exact zeros, rather than a sine of 1e-16.
    along_x, along_y = round(sin(angle), 15), round(-cos(angle), 15)
    length = abs(width * along_x) + abs(height * along_y)
    if length == 0:
        return lambda columns, _: [0.5] * len(columns)
    step_x = along_x / length
    step_y = along_y * aspect / length
    origin = 0.5 - (width / 2 * along_x + height / 2 * along_y) / length

    def positions(columns: range, y: int) -> list[float]:
        start = origin + y * step_y
        return [start + x * step_x for x in columns]

    return positions


def _coordinate_value(coordinate: Coordinate) -> float:
    return coordinate.value if isinstance(coordinate, waxy.Length) else coordinate


def _point(at: tuple[Coordinate, Coordinate], width: float, height: float, aspect: float) -> tuple[float, float]:
    """Where `at` is, in visual units: each coordinate a fraction of the box or a number of cells."""
    x, y = at
    return (
        x.value if isinstance(x, waxy.Length) else x * width,
        y.value * aspect if isinstance(y, waxy.Length) else y * height,
    )


def _radii(
    shape: Shape,
    size: Extent | waxy.Length | tuple[Coordinate, Coordinate],
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    aspect: float,
) -> tuple[float, float]:
    """The ending shape's radii in visual units, which are equal for a circle."""
    sides_x = (abs(center_x), abs(width - center_x))
    sides_y = (abs(center_y), abs(height - center_y))
    match size:
        case waxy.Length(value=radius):
            return radius, radius
        case (radius_x, radius_y):
            return (
                radius_x.value if isinstance(radius_x, waxy.Length) else radius_x * width,
                radius_y.value * aspect if isinstance(radius_y, waxy.Length) else radius_y * height,
            )
        case _ if shape == "circle":
            match size:
                case "closest-side":
                    radius = min(*sides_x, *sides_y)
                case "farthest-side":
                    radius = max(*sides_x, *sides_y)
                case "closest-corner":
                    radius = hypot(min(sides_x), min(sides_y))
                case "farthest-corner":
                    radius = hypot(max(sides_x), max(sides_y))
                case _ as unreachable:
                    assert_never(unreachable)
            return radius, radius
        case "closest-side":
            return min(sides_x), min(sides_y)
        case "farthest-side":
            return max(sides_x), max(sides_y)
        # The closest corner is the closest side on each axis away, and the farthest the farthest,
        # so the ellipse through it with the side ellipse's aspect ratio is that one scaled by the square root of 2.
        case "closest-corner":
            return min(sides_x) * sqrt(2), min(sides_y) * sqrt(2)
        case "farthest-corner":
            return max(sides_x) * sqrt(2), max(sides_y) * sqrt(2)
        case _ as unreachable:
            assert_never(unreachable)


def _radial_positions(
    shape: Shape, center_x: float, center_y: float, radius_x: float, radius_y: float, aspect: float
) -> RowPositions:
    """
    Positions outward from the center, which are 1 on the ending shape.
    An ending shape with no size is drawn as CSS Images 4 draws
    [degenerate radial gradients](https://drafts.csswg.org/css-images-4/#degenerate-radials):
    a circle as an infinitely small one, so everywhere but its center is infinitely far out,
    and an ellipse with no width (or with a width but no height) as an infinitely long, infinitely thin one,
    so everywhere off the line through its center is.
    """
    if shape == "circle" and radius_x == 0:
        return lambda columns, y: [0 if x == center_x and y * aspect == center_y else inf for x in columns]
    if radius_x == 0:
        return lambda columns, _: [0 if x == center_x else inf for x in columns]
    if radius_y == 0:
        return lambda columns, y: [0 if y * aspect == center_y else inf] * len(columns)
    scale_x = 1 / radius_x
    scale_y = aspect / radius_y

    def positions(columns: range, y: int) -> list[float]:
        across = y * scale_y - center_y / radius_y
        offset = center_x * scale_x
        return [hypot(x * scale_x - offset, across) for x in columns]

    return positions


def _conic_positions(center_x: float, center_y: float, start: float, aspect: float) -> RowPositions:
    """Fractions of a turn clockwise around the center, from `start` degrees clockwise from up."""
    turn = 1 / (2 * pi)
    offset = -start / 360

    def positions(columns: range, y: int) -> list[float]:
        # center_y - y, not -(y - center_y), which is -0.0 at the center, and atan2(0.0, -0.0) is a half turn.
        up = center_y - y * aspect
        return [(atan2(x - center_x, up) * turn + offset) % 1.0 for x in columns]

    return positions


__all__ = [
    "Box",
    "ConicGradient",
    "Coordinate",
    "Extent",
    "Gradient",
    "Hint",
    "HueMethod",
    "Interpolation",
    "LinearGradient",
    "RadialGradient",
    "Shape",
    "SideOrCorner",
    "Stop",
    "StopLike",
    "Stops",
    "conic_gradient",
    "linear_gradient",
    "radial_gradient",
]
