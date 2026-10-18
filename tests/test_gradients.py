from bisect import bisect_right
from math import inf
from math import nan

import pytest
import waxy
from hypothesis import example
from hypothesis import given
from hypothesis import strategies as st

from counterweight.geometry import Region
from counterweight.gradients import POLAR_SPACES
from counterweight.gradients import SEGMENT_ENTRIES
from counterweight.gradients import ConicGradient
from counterweight.gradients import Coordinate
from counterweight.gradients import Extent
from counterweight.gradients import Gradient
from counterweight.gradients import Hint
from counterweight.gradients import HueMethod
from counterweight.gradients import Interpolation
from counterweight.gradients import LinearGradient
from counterweight.gradients import Matrix
from counterweight.gradients import RadialGradient
from counterweight.gradients import ResolvedStops
from counterweight.gradients import SideOrCorner
from counterweight.gradients import Stop
from counterweight.gradients import Stops
from counterweight.gradients import _fixed_up_hues
from counterweight.gradients import _inverse
from counterweight.gradients import conic_gradient
from counterweight.gradients import field_indices
from counterweight.gradients import from_space
from counterweight.gradients import linear_gradient
from counterweight.gradients import radial_gradient
from counterweight.gradients import ramp
from counterweight.gradients import ramp_of
from counterweight.gradients import resolve_stops
from counterweight.gradients import to_space
from counterweight.styles.styles import Color

RED = Color(255, 0, 0)
GREEN = Color(0, 128, 0)
BLUE = Color(0, 0, 255)
WHITE = Color(255, 255, 255)
BLACK = Color(0, 0, 0)
GRAY = Color(128, 128, 128)

SPACES: tuple[Interpolation, ...] = (
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
)
HUE_METHODS: tuple[HueMethod, ...] = ("shorter", "longer", "increasing", "decreasing")
LAST = SEGMENT_ENTRIES - 1


def region(left: int, top: int, right: int, bottom: int) -> Region:
    return Region(left=left, top=top, right=right, bottom=bottom)


@pytest.mark.parametrize(
    ("stops", "positions"),
    [
        ((Stop(RED), Stop(BLUE)), (0, 1)),
        ((Stop(RED), Stop(GREEN), Stop(BLUE)), (0, 0.5, 1)),
        ((Stop(RED, 0.2), Stop(GREEN), Stop(WHITE), Stop(BLUE, 0.8)), (0.2, 0.4, 0.6, 0.8)),
        ((Stop(RED, 0.6), Stop(BLUE, 0.3)), (0.6, 0.6)),
        ((Stop(RED, 0.2), Stop(GREEN), Stop(WHITE), Stop(BLUE, 0.1), Stop(BLACK)), (0.2, 0.2, 0.2, 0.2, 1)),
        ((Stop(RED, -0.5), Stop(BLUE, 1.5)), (-0.5, 1.5)),
    ],
)
def test_stop_fixup_places_every_color_stop(stops: Stops, positions: tuple[float, ...]) -> None:
    assert resolve_stops(stops).positions == pytest.approx(positions)


def test_stop_fixup_keeps_the_colors_in_order_without_the_hints() -> None:
    assert resolve_stops((Stop(RED), Hint(0.3), Stop(GREEN), Stop(BLUE))).colors == (RED, GREEN, BLUE)


def test_spacing_positionless_stops_skips_hints() -> None:
    stops = (Stop(RED, 0), Hint(0.1), Stop(GREEN), Stop(BLUE, 0.9))
    assert resolve_stops(stops).positions == pytest.approx((0, 0.45, 0.9))


@pytest.mark.parametrize(
    ("hint", "exponent"),
    [
        (0.25, 0.5),
        (0.5, None),
        (0, 0),
        (-1, 0),
        (1, inf),
    ],
)
def test_a_hint_raises_the_fraction_between_its_stops_to_the_power_that_mixes_half_and_half_there(
    hint: float, exponent: float | None
) -> None:
    resolved = resolve_stops((Stop(RED, 0), Hint(hint), Stop(BLUE, 1)))
    assert resolved.exponents == (pytest.approx(exponent) if exponent is not None else None,)


def test_a_hint_measures_its_fraction_between_its_own_stops() -> None:
    resolved = resolve_stops((Stop(RED, 0.2), Hint(0.3), Stop(BLUE, 0.6), Stop(WHITE, 1)))
    assert resolved.exponents == (pytest.approx(0.5), None)


def test_a_hint_before_a_stop_it_is_past_mixes_none_of_the_second_color() -> None:
    resolved = resolve_stops((Stop(RED, 0), Hint(0.9), Stop(BLUE), Stop(WHITE, 1)))
    assert resolved.exponents == (inf, None)


def test_a_hint_between_stops_at_one_position_does_nothing() -> None:
    assert resolve_stops((Stop(RED, 0.5), Hint(0.5), Stop(BLUE, 0.5))).exponents == (None,)


@pytest.mark.parametrize("stops", [(), (Stop(RED),), (Stop(RED), Hint(0.5))])
def test_a_gradient_needs_two_color_stops(stops: Stops) -> None:
    with pytest.raises(ValueError, match="at least two color stops"):
        LinearGradient(stops=stops)


@pytest.mark.parametrize(
    "stops",
    [
        (Hint(0.1), Stop(RED), Stop(BLUE)),
        (Stop(RED), Stop(BLUE), Hint(0.9)),
        (Stop(RED), Hint(0.3), Hint(0.6), Stop(BLUE)),
    ],
)
def test_a_hint_goes_between_two_color_stops(stops: Stops) -> None:
    with pytest.raises(ValueError, match="between two color stops"):
        LinearGradient(stops=stops)


@pytest.mark.parametrize("interpolation", sorted(set(SPACES) - POLAR_SPACES))
def test_a_hue_method_needs_a_polar_space(interpolation: Interpolation) -> None:
    with pytest.raises(ValueError, match="polar color space"):
        ConicGradient(stops=(Stop(RED), Stop(BLUE)), interpolation=interpolation, hue="longer")


@pytest.mark.parametrize("interpolation", sorted(POLAR_SPACES))
def test_a_polar_space_takes_a_hue_method(interpolation: Interpolation) -> None:
    assert RadialGradient(stops=(Stop(RED), Stop(BLUE)), interpolation=interpolation, hue="longer").hue == "longer"


def test_an_ellipse_has_two_radii() -> None:
    with pytest.raises(ValueError, match="An ellipse's size"):
        RadialGradient(stops=(Stop(RED), Stop(BLUE)), shape="ellipse", size=waxy.Length(3))


def test_a_circle_has_one_radius() -> None:
    with pytest.raises(ValueError, match="A circle's size"):
        RadialGradient(stops=(Stop(RED), Stop(BLUE)), shape="circle", size=(waxy.Length(3), waxy.Length(2)))


@pytest.mark.parametrize(
    ("shape", "size"),
    [
        ("circle", waxy.Length(-1)),
        ("ellipse", (waxy.Length(2), -0.5)),
    ],
)
def test_a_radius_is_not_negative(shape: str, size: waxy.Length | tuple[Coordinate, Coordinate]) -> None:
    with pytest.raises(ValueError, match="can't be negative"):
        RadialGradient(stops=(Stop(RED), Stop(BLUE)), shape="circle" if shape == "circle" else "ellipse", size=size)


def test_the_gradient_functions_take_stops_as_css_spells_them() -> None:
    gradient = linear_gradient(RED, (GREEN, 0.3), Hint(0.4), (BLUE, 0.5, 0.7), WHITE)
    assert gradient.stops == (
        Stop(RED),
        Stop(GREEN, 0.3),
        Hint(0.4),
        Stop(BLUE, 0.5),
        Stop(BLUE, 0.7),
        Stop(WHITE),
    )


@pytest.mark.parametrize(
    ("to", "angle", "direction"),
    [
        (None, None, "bottom"),
        ("top right", None, "top right"),
        (None, 45, 45),
    ],
)
def test_a_linear_gradient_points_to_a_side_or_corner_or_at_an_angle(
    to: SideOrCorner | None, angle: float | None, direction: float | SideOrCorner
) -> None:
    assert linear_gradient(RED, BLUE, to=to, angle=angle).direction == direction


def test_a_linear_gradient_points_one_way() -> None:
    with pytest.raises(ValueError, match="not both"):
        linear_gradient(RED, BLUE, to="right", angle=90)


def test_the_gradient_functions_pass_their_options_on() -> None:
    assert linear_gradient(RED, BLUE, repeating=True, interpolation="oklch", hue="longer", box="padding") == (
        LinearGradient(
            stops=(Stop(RED), Stop(BLUE)), repeating=True, interpolation="oklch", hue="longer", box="padding"
        )
    )
    assert conic_gradient(RED, BLUE, start=90, at=(0.25, waxy.Length(2)), repeating=True, box="content") == (
        ConicGradient(stops=(Stop(RED), Stop(BLUE)), start=90, at=(0.25, waxy.Length(2)), repeating=True, box="content")
    )
    assert radial_gradient(RED, BLUE, size="closest-side", at=(0, 1), repeating=True, interpolation="srgb") == (
        RadialGradient(
            stops=(Stop(RED), Stop(BLUE)), size="closest-side", at=(0, 1), repeating=True, interpolation="srgb"
        )
    )


@pytest.mark.parametrize(
    ("size", "shape"),
    [
        (waxy.Length(3), "circle"),
        ((waxy.Length(3), waxy.Length(2)), "ellipse"),
        ("closest-side", "ellipse"),
    ],
)
def test_a_radial_gradient_is_a_circle_if_its_size_is_one_radius(
    size: Extent | waxy.Length | tuple[Coordinate, Coordinate], shape: str
) -> None:
    assert radial_gradient(RED, BLUE, size=size).shape == shape


def test_a_radial_gradient_takes_the_shape_it_is_given() -> None:
    assert radial_gradient(RED, BLUE, shape="circle").shape == "circle"


def test_gradients_with_the_same_fields_are_equal_and_hash_equal() -> None:
    first = linear_gradient(RED, BLUE, angle=30)
    second = linear_gradient(RED, BLUE, angle=30)
    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.parametrize(
    ("space", "color", "expected"),
    [
        ("oklab", RED, (0.62796, 0.22486, 0.12585)),
        ("oklch", RED, (0.62796, 0.25768, 29.2339)),
        ("lab", RED, (54.2905, 80.8049, 69.891)),
        ("lch", RED, (54.2905, 106.8372, 40.8577)),
        ("xyz-d65", RED, (0.41239, 0.21264, 0.01933)),
        ("xyz-d50", RED, (0.43607, 0.22249, 0.01392)),
        ("hsl", BLUE, (240, 1, 0.5)),
        ("hwb", BLUE, (240, 0, 0)),
        ("srgb-linear", GRAY, (0.21586, 0.21586, 0.21586)),
        ("lab", WHITE, (100, 0, 0)),
    ],
)
def test_converting_to_a_color_space_gives_css_colors_coordinates(
    space: Interpolation, color: Color, expected: tuple[float, float, float]
) -> None:
    assert to_space(color, space) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("space", sorted(POLAR_SPACES))
@pytest.mark.parametrize("color", [BLACK, GRAY, WHITE])
def test_an_achromatic_colors_hue_is_missing(space: Interpolation, color: Color) -> None:
    hue = to_space(color, space)[0 if space in ("hsl", "hwb") else 2]
    assert hue != hue


@pytest.mark.parametrize("space", SPACES)
@given(color=st.builds(Color, *(st.integers(0, 255) for _ in range(3))))
def test_converting_to_a_color_space_and_back_is_the_same_color(space: Interpolation, color: Color) -> None:
    assert from_space(to_space(color, space), space) == color


@pytest.mark.parametrize("space", SPACES)
def test_converting_back_clips_to_the_srgb_gamut(space: Interpolation) -> None:
    beyond = {
        "srgb": (1.5, -0.5, 0.5),
        "srgb-linear": (1.5, -0.5, 0.5),
        "oklab": (0.7, 0.4, 0.4),
        "oklch": (0.7, 0.5, 30),
        "lab": (60, 150, 100),
        "lch": (60, 180, 30),
        "hsl": (0, 1, 0.5),
        "hwb": (0, 0, 0),
        "xyz": (0.6, 0.2, -0.1),
        "xyz-d50": (0.6, 0.2, -0.1),
        "xyz-d65": (0.6, 0.2, -0.1),
    }[space]
    assert all(0 <= channel <= 255 for channel in from_space(beyond, space))


@pytest.mark.parametrize(
    ("coordinates", "expected"),
    [
        ((0, 0.6, 0.6), Color(128, 128, 128)),
        ((120, 0.2, 0.2), Color(51, 204, 51)),
    ],
)
def test_hwb_with_whiteness_and_blackness_adding_to_one_or_more_is_gray(
    coordinates: tuple[float, float, float], expected: Color
) -> None:
    assert from_space(coordinates, "hwb") == expected


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("shorter", (Color(255, 0, 0), Color(255, 0, 255))),
        ("longer", (Color(255, 0, 0), Color(0, 255, 0))),
        ("increasing", (Color(255, 0, 0), Color(0, 255, 0))),
        ("decreasing", (Color(255, 0, 0), Color(255, 0, 255))),
    ],
)
def test_a_hue_method_chooses_the_way_around_the_hue_circle(method: HueMethod, expected: tuple[Color, Color]) -> None:
    # From red (0 degrees) to blue (240 degrees), halfway is magenta (300) the short way and green (120) the long way.
    gradient_ramp = ramp(linear_gradient(RED, BLUE, interpolation="hsl", hue=method))
    assert (gradient_ramp.color(0), gradient_ramp.color(gradient_ramp.index(0.5))) == expected


@pytest.mark.parametrize(
    ("first", "second", "method", "expected"),
    [
        # From blue (240 degrees) to red (0, or 360), halfway is magenta (300) the short way.
        (BLUE, RED, "shorter", Color(255, 0, 255)),
        # From red (0 degrees) to green (120 degrees), halfway is blue (240) the long way.
        (RED, Color(0, 255, 0), "longer", Color(0, 0, 255)),
    ],
)
def test_a_hue_method_wraps_whichever_hue_it_has_to(
    first: Color, second: Color, method: HueMethod, expected: Color
) -> None:
    gradient_ramp = ramp(linear_gradient(first, second, interpolation="hsl", hue=method))
    assert gradient_ramp.color(gradient_ramp.index(0.5)) == expected


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("shorter", Color(0, 255, 255)),
        ("longer", Color(255, 0, 0)),
        ("increasing", Color(255, 0, 0)),
        ("decreasing", Color(0, 255, 255)),
    ],
)
def test_a_hue_method_chooses_the_way_around_from_a_larger_hue(method: HueMethod, expected: Color) -> None:
    # From blue (240 degrees) to green (120 degrees), halfway is cyan (180) the short way and red (0) the long way.
    gradient_ramp = ramp(linear_gradient(BLUE, Color(0, 255, 0), interpolation="hsl", hue=method))
    assert gradient_ramp.color(gradient_ramp.index(0.5)) == expected


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (WHITE, BLUE),
        (BLUE, WHITE),
    ],
)
def test_an_achromatic_stop_takes_the_other_stops_hue(first: Color, second: Color) -> None:
    # Halfway from white to blue is hsl(240 50% 75%), not the red its own hue of 0 would give.
    gradient_ramp = ramp(linear_gradient(first, second, interpolation="hsl"))
    assert gradient_ramp.color(gradient_ramp.index(0.5)) == Color(159, 159, 223)


def test_two_achromatic_stops_mix_as_grays() -> None:
    gradient_ramp = ramp(linear_gradient(BLACK, WHITE, interpolation="oklch"))
    middle = gradient_ramp.color(gradient_ramp.index(0.5))
    assert middle.red == middle.green == middle.blue


def exact_color(stops: ResolvedStops, space: Interpolation, hue: HueMethod, position: float) -> Color:
    """The color CSS Images 4 gives `position` along a gradient, computed without a ramp."""
    gradient_ramp = ramp_of(stops, False, space, hue)
    positions = stops.positions
    if position < positions[0]:
        return stops.colors[0]
    if position >= positions[-1]:
        return stops.colors[-1]
    segment = bisect_right(positions, position) - 1
    start, end = positions[segment], positions[segment + 1]
    fraction = (position - start) / (end - start)
    if (exponent := stops.exponents[segment]) is not None:
        fraction **= exponent
    first, second = gradient_ramp.segments[segment]
    mixed = (
        first[0] + (second[0] - first[0]) * fraction,
        first[1] + (second[1] - first[1]) * fraction,
        first[2] + (second[2] - first[2]) * fraction,
    )
    return from_space(mixed, space)


colors = st.builds(Color, *(st.integers(0, 255) for _ in range(3)))


@st.composite
def gradient_stops(draw: st.DrawFn) -> Stops:
    count = draw(st.integers(2, 4))
    positions = sorted(draw(st.lists(st.floats(0, 1), min_size=count, max_size=count)))
    stops: list[Stop | Hint] = []
    for index, position in enumerate(positions):
        if index and draw(st.booleans()):
            stops.append(Hint(draw(st.floats(positions[index - 1], position))))
        stops.append(Stop(draw(colors), position))
    return tuple(stops)


@example(stops=(Stop(BLACK, 0), Hint(0.1), Stop(WHITE, 1)), space="srgb", hue="shorter", position=0.001)
@given(
    stops=gradient_stops(),
    space=st.sampled_from(SPACES),
    hue=st.sampled_from(HUE_METHODS),
    position=st.floats(-0.5, 1.5),
)
def test_a_ramp_lookup_is_within_a_channel_step_of_the_exact_color(
    stops: Stops, space: Interpolation, hue: HueMethod, position: float
) -> None:
    hue = hue if space in POLAR_SPACES else "shorter"
    resolved = resolve_stops(stops)
    gradient_ramp = ramp_of(resolved, False, space, hue)
    looked_up = gradient_ramp.color(gradient_ramp.index(position))
    exact = exact_color(resolved, space, hue, position)
    assert all(abs(a - b) <= 1 for a, b in zip(looked_up, exact, strict=True)), (looked_up, exact)


@given(stops=gradient_stops(), positions=st.lists(st.floats(-0.5, 1.5) | st.just(inf), max_size=8))
def test_looking_up_a_row_of_positions_is_looking_up_each(stops: Stops, positions: list[float]) -> None:
    gradient_ramp = ramp(LinearGradient(stops=stops))
    assert gradient_ramp.indices(positions) == tuple(map(gradient_ramp.index, positions))


@pytest.mark.parametrize("position", [-1, 0, 0.5, 1, 2])
def test_stops_at_one_position_split_the_gradient_there(position: float) -> None:
    gradient_ramp = ramp(linear_gradient((RED, 0.5), (BLUE, 0.5)))
    expected = RED if position < 0.5 else BLUE
    assert gradient_ramp.color(gradient_ramp.indices([position])[0]) == expected


def test_a_hard_stop_takes_the_later_color_at_its_position() -> None:
    gradient_ramp = ramp(linear_gradient(RED, (GREEN, 0.5), (BLUE, 0.5), WHITE))
    assert gradient_ramp.color(gradient_ramp.index(0.5)) == BLUE


@pytest.mark.parametrize(("position", "expected"), [(-0.1, RED), (1.2, BLUE)])
def test_past_the_ends_the_end_colors_extend(position: float, expected: Color) -> None:
    gradient_ramp = ramp(linear_gradient(RED, GREEN, BLUE))
    assert gradient_ramp.color(gradient_ramp.index(position)) == expected


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (0.25, 0.75),
        (1.25, 0.75),
        (-0.75, 0.75),
        (0.5, 0.5),
    ],
)
def test_a_repeating_gradient_repeats_its_stops_every_span(position: float, expected: float) -> None:
    gradient_ramp = ramp(linear_gradient((RED, 0.5), (BLUE, 1), repeating=True))
    plain = ramp(linear_gradient((RED, 0.5), (BLUE, 1)))
    assert gradient_ramp.color(gradient_ramp.index(position)) == plain.color(plain.index(expected))


@pytest.mark.parametrize("position", [0, 0.5, inf])
def test_a_repeating_gradient_whose_stops_span_nothing_is_the_average_of_its_colors_spaced_evenly(
    position: float,
) -> None:
    gradient_ramp = ramp(linear_gradient((RED, 0.5), (BLUE, 0.5), repeating=True, interpolation="srgb"))
    assert gradient_ramp.color(gradient_ramp.indices([position])[0]) == Color(128, 0, 128)


def test_infinitely_far_along_a_repeating_gradient_is_its_average_color() -> None:
    gradient_ramp = ramp(linear_gradient(BLACK, (WHITE, 0.25), WHITE, repeating=True, interpolation="srgb"))
    # A quarter of the line averages to half white, and the other three quarters are white.
    assert gradient_ramp.color(gradient_ramp.index(inf)) == Color(223, 223, 223)


def test_a_hint_weights_the_average_color_by_its_curve() -> None:
    gradient_ramp = ramp(linear_gradient(BLACK, Hint(0.25), WHITE, repeating=True, interpolation="srgb"))
    # The fraction mixed in is P ** 0.5, which averages to 2/3.
    assert gradient_ramp.color(gradient_ramp.index(inf)) == Color(170, 170, 170)


def test_infinitely_far_along_a_gradient_that_doesnt_repeat_is_its_last_color() -> None:
    gradient_ramp = ramp(linear_gradient(RED, BLUE))
    assert gradient_ramp.color(gradient_ramp.index(inf)) == BLUE


def test_a_ramp_computes_each_entry_once() -> None:
    gradient_ramp = ramp(linear_gradient(Color(1, 2, 3), Color(4, 5, 6)))
    assert gradient_ramp.color(17) is gradient_ramp.color(17)


def colors_of(
    gradient: Gradient, width: int, height: int, aspect: float = 2, within: Region | None = None
) -> list[list[Color]]:
    gradient_ramp = ramp(gradient)
    rows = field_indices(gradient, width, height, aspect, within or region(0, 0, width, height))
    return [[gradient_ramp.color(index) for index in row] for row in rows]


def fractions(
    gradient: Gradient, width: int, height: int, aspect: float = 2, within: Region | None = None
) -> list[list[float]]:
    """Where each cell's entry is along a two-stop gradient from 0 to 1, rounded to two places."""
    rows = field_indices(gradient, width, height, aspect, within or region(0, 0, width, height))
    return [[round(index / LAST, 2) for index in row] for row in rows]


def test_a_vertical_gradient_spans_from_the_first_rows_center_to_the_last_rows() -> None:
    assert fractions(linear_gradient(BLACK, WHITE), 2, 3) == [[0, 0], [0.5, 0.5], [1, 1]]


def test_a_horizontal_gradient_spans_from_the_first_columns_center_to_the_last_columns() -> None:
    assert fractions(linear_gradient(BLACK, WHITE, to="right"), 5, 1) == [[0, 0.25, 0.5, 0.75, 1]]


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("top", [[1], [0.5], [0]]),
        ("left", [[1, 0.5, 0]]),
        (0, [[1], [0.5], [0]]),
        (90, [[0, 0.5, 1]]),
        (270, [[1, 0.5, 0]]),
    ],
)
def test_a_linear_gradient_points_where_its_direction_says(
    direction: float | SideOrCorner, expected: list[list[float]]
) -> None:
    gradient = LinearGradient(stops=(Stop(BLACK), Stop(WHITE)), direction=direction)
    width, height = len(expected[0]), len(expected)
    assert fractions(gradient, width, height) == expected


def test_an_angle_is_in_visual_units() -> None:
    # With rows two columns tall, a 3x3 box is 2 columns wide and 4 tall between its corner cells' centers,
    # so at 45 degrees, its line is 6 long, and a step right or a step down moves 1/3 along it.
    assert fractions(linear_gradient(BLACK, WHITE, angle=135), 3, 3) == [
        [0, 0.17, 0.33],
        [0.33, 0.5, 0.67],
        [0.67, 0.83, 1],
    ]


def test_an_angle_follows_the_aspect_ratio() -> None:
    assert fractions(linear_gradient(BLACK, WHITE, angle=135), 3, 3, aspect=1) == [
        [0, 0.25, 0.5],
        [0.25, 0.5, 0.75],
        [0.5, 0.75, 1],
    ]


@pytest.mark.parametrize(
    ("corner", "start", "end"),
    [
        ("top right", (0, -1), (-1, 0)),
        ("right top", (0, -1), (-1, 0)),
        ("bottom right", (0, 0), (-1, -1)),
        ("right bottom", (0, 0), (-1, -1)),
        ("bottom left", (-1, 0), (0, -1)),
        ("left bottom", (-1, 0), (0, -1)),
        ("top left", (-1, -1), (0, 0)),
        ("left top", (-1, -1), (0, 0)),
    ],
)
@given(width=st.integers(2, 30), height=st.integers(2, 30), aspect=st.floats(0.5, 3))
def test_a_corner_takes_the_last_color_and_the_opposite_corner_the_first(
    corner: SideOrCorner, start: tuple[int, int], end: tuple[int, int], width: int, height: int, aspect: float
) -> None:
    rows = fractions(linear_gradient(BLACK, WHITE, to=corner), width, height, aspect)
    assert (rows[start[1]][start[0]], rows[end[1]][end[0]]) == (0, 1)


def test_magic_corners_put_the_middle_line_through_the_other_two_corners() -> None:
    rows = fractions(linear_gradient(BLACK, WHITE, to="top right"), 5, 3)
    assert (rows[0][0], rows[2][4]) == (0.5, 0.5)


def test_a_linear_gradient_with_no_line_is_halfway_along_everywhere() -> None:
    assert fractions(linear_gradient(BLACK, WHITE), 3, 1, within=region(-1, -1, 4, 2)) == [[0.5] * 5] * 3


def test_a_field_outside_the_box_continues_the_gradient() -> None:
    gradient = linear_gradient(BLACK, WHITE, to="right", repeating=True)
    assert fractions(gradient, 3, 1, within=region(3, 0, 6, 1)) == [[0.5, 0, 0.5]]


def test_a_field_covers_only_its_region() -> None:
    assert fractions(linear_gradient(BLACK, WHITE, to="right"), 5, 2, within=region(1, 1, 3, 2)) == [[0.25, 0.5]]


def test_a_circle_is_in_visual_units() -> None:
    # A circle of radius 2 reaches 2 columns from its center, and 1 row.
    gradient = radial_gradient(BLACK, WHITE, size=waxy.Length(2), at=(waxy.Length(2), waxy.Length(1)))
    assert fractions(gradient, 5, 3) == [
        [1, 1, 1, 1, 1],
        [1, 0.5, 0, 0.5, 1],
        [1, 1, 1, 1, 1],
    ]


def test_an_ellipses_radii_are_columns_and_rows() -> None:
    gradient = radial_gradient(BLACK, WHITE, size=(waxy.Length(2), waxy.Length(2)), at=(0.5, 0.5))
    assert fractions(gradient, 5, 5)[2] == [1, 0.5, 0, 0.5, 1]
    assert [row[2] for row in fractions(gradient, 5, 5)] == [1, 0.5, 0, 0.5, 1]


def test_an_ellipses_radii_can_be_fractions_of_the_box() -> None:
    gradient = radial_gradient(BLACK, WHITE, size=(0.5, 0.5))
    assert [row[1] for row in fractions(gradient, 3, 5)] == [1, 0.5, 0, 0.5, 1]


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        # From a center 1 column and 1 row (2 visual units) into a 7x4 box (6 by 6 between corner cells).
        ("closest-side", 1),
        ("farthest-side", 5),
        ("closest-corner", 2.24),
        ("farthest-corner", 6.40),
    ],
)
def test_a_circle_sized_by_an_extent_reaches_that_side_or_corner(size: Extent, expected: float) -> None:
    gradient = radial_gradient(BLACK, WHITE, shape="circle", size=size, at=(waxy.Length(1), waxy.Length(1)))
    one_column_away = fractions(gradient, 7, 4)[1][2]
    assert one_column_away == round(1 / expected, 2)


@pytest.mark.parametrize(
    ("size", "radii"),
    [
        ("closest-side", (1, 2)),
        ("farthest-side", (5, 4)),
        # Through the closest corner, (1, 2) away, with closest-side's ratio of 2: radii of sqrt(2) and 2 sqrt(2).
        ("closest-corner", (1.41, 2.83)),
        # Through the farthest corner, (5, 4) away, with farthest-side's ratio of 0.8: sqrt(50) and 0.8 sqrt(50).
        ("farthest-corner", (7.07, 5.66)),
    ],
)
def test_an_ellipse_sized_by_an_extent_reaches_that_side_or_corner(size: Extent, radii: tuple[float, float]) -> None:
    gradient = radial_gradient(BLACK, WHITE, size=size, at=(waxy.Length(1), waxy.Length(1)))
    rows = fractions(gradient, 7, 4)
    assert (rows[1][2], rows[2][1]) == (round(1 / radii[0], 2), round(2 / radii[1], 2))


def test_a_corner_sized_ellipse_with_no_width_has_none() -> None:
    gradient = radial_gradient(BLACK, WHITE, size="closest-corner", at=(0, 0.5))
    assert colors_of(gradient, 3, 3, within=region(0, 0, 3, 3)) == [[BLACK, WHITE, WHITE]] * 3


def test_a_corner_sized_ellipse_with_no_height_has_none() -> None:
    gradient = radial_gradient(BLACK, WHITE, size="closest-corner", at=(0.5, 1))
    assert colors_of(gradient, 3, 3) == [[WHITE] * 3, [WHITE] * 3, [BLACK] * 3]


def test_a_circle_with_no_radius_is_its_first_color_at_its_center_and_its_last_everywhere_else() -> None:
    gradient = radial_gradient(BLACK, WHITE, size=waxy.Length(0), at=(0.5, 0.5))
    assert colors_of(gradient, 3, 3) == [[WHITE] * 3, [WHITE, BLACK, WHITE], [WHITE] * 3]


def test_an_ellipse_with_no_width_is_an_infinitely_tall_line() -> None:
    gradient = radial_gradient(BLACK, WHITE, size=(0, waxy.Length(0)))
    assert colors_of(gradient, 3, 2) == [[WHITE, BLACK, WHITE]] * 2


def test_a_radial_gradient_in_a_box_one_row_tall_is_a_line_across_it() -> None:
    gradient = radial_gradient(BLACK, WHITE, size="closest-side")
    assert colors_of(gradient, 3, 1, within=region(0, -1, 3, 2)) == [[WHITE] * 3, [BLACK] * 3, [WHITE] * 3]


def test_a_repeating_radial_gradient_that_has_no_size_is_its_average_color() -> None:
    gradient = radial_gradient(BLACK, WHITE, size=waxy.Length(0), repeating=True, interpolation="srgb")
    assert colors_of(gradient, 2, 1) == [[Color(128, 128, 128)] * 2]


def test_a_radial_gradient_centered_outside_the_box_measures_its_sides_by_their_distance() -> None:
    # The center is a column left of the box, so the farthest side is its right edge, 3 columns away.
    gradient = radial_gradient(BLACK, WHITE, shape="circle", size="farthest-side", at=(waxy.Length(-1), 0.5))
    assert fractions(gradient, 3, 3)[1] == [0.33, 0.67, 1]


def test_a_conic_gradient_turns_clockwise_from_up() -> None:
    gradient = conic_gradient(BLACK, WHITE)
    rows = fractions(gradient, 3, 3)
    assert (rows[0][1], rows[1][2], rows[2][1], rows[1][0]) == (0, 0.25, 0.5, 0.75)


def test_a_conic_gradient_starts_at_its_start_angle() -> None:
    rows = fractions(conic_gradient(BLACK, WHITE, start=90), 3, 3)
    assert (rows[1][2], rows[2][1], rows[1][0], rows[0][1]) == (0, 0.25, 0.5, 0.75)


def test_a_conic_gradients_center_takes_its_start_angles_color() -> None:
    assert fractions(conic_gradient(BLACK, WHITE, start=90), 3, 3)[1][1] == 0.75


def test_a_conic_gradients_angles_are_in_visual_units() -> None:
    # One column right and one row down is 1 by 2 in visual units: about 153 degrees clockwise from up.
    assert fractions(conic_gradient(BLACK, WHITE), 3, 3)[2][2] == round(153.43 / 360, 2)


def test_a_conic_gradient_can_center_on_a_cell() -> None:
    rows = fractions(conic_gradient(BLACK, WHITE, at=(waxy.Length(0), waxy.Length(0))), 2, 2)
    assert (rows[0][1], rows[1][0]) == (0.25, 0.5)


def test_an_empty_box_spans_nothing() -> None:
    assert fractions(linear_gradient(BLACK, WHITE, to="right"), 0, 0, within=region(0, 0, 2, 1)) == [[0.5, 0.5]]


@pytest.mark.parametrize(
    "matrix",
    [
        ((2.0, 0.0, 1.0), (1.0, 3.0, 0.0), (0.0, 1.0, 4.0)),
        ((0.4, 0.5, 0.1), (0.2, 0.7, 0.1), (0.1, 0.3, 0.6)),
    ],
)
def test_a_matrix_times_its_inverse_is_the_identity(matrix: Matrix) -> None:
    inverse = _inverse(matrix)
    product = [[sum(matrix[i][k] * inverse[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    assert product == [pytest.approx([1.0 if i == j else 0.0 for j in range(3)], abs=1e-12) for i in range(3)]


@pytest.mark.parametrize(
    ("first", "second", "method", "expected"),
    [
        (10, 200, "shorter", (370, 200)),
        (200, 10, "shorter", (200, 370)),
        (10, 190, "shorter", (10, 190)),
        (10, 191, "shorter", (370, 191)),
        (191, 10, "shorter", (191, 370)),
        (190, 10, "shorter", (190, 10)),
        (10, 100, "longer", (370, 100)),
        (100, 10, "longer", (100, 370)),
        (10, 190, "longer", (10, 190)),
        (190, 10, "longer", (190, 10)),
        (10, 10, "longer", (10, 370)),
        (10, 10.5, "longer", (370, 10.5)),
        (191, 10, "longer", (191, 10)),
        (100, 10, "increasing", (100, 370)),
        (10, 10, "increasing", (10, 10)),
        (10, 100, "increasing", (10, 100)),
        (10, 100, "decreasing", (370, 100)),
        (10, 10, "decreasing", (10, 10)),
        (100, 10, "decreasing", (100, 10)),
        (nan, 40, "shorter", (40, 40)),
        (40, nan, "longer", (40, 40)),
        (nan, nan, "increasing", (0, 0)),
    ],
)
def test_hues_are_fixed_up_to_go_around_the_way_their_method_says(
    first: float, second: float, method: HueMethod, expected: tuple[float, float]
) -> None:
    assert _fixed_up_hues(first, second, method) == expected


@pytest.mark.parametrize("space", sorted(POLAR_SPACES))
@pytest.mark.parametrize(("method", "is_green"), [("shorter", False), ("longer", True)])
def test_every_polar_space_mixes_hues_the_way_its_method_says(
    space: Interpolation, method: HueMethod, is_green: bool
) -> None:
    # Red to blue the short way is through magenta, and the long way through green.
    gradient_ramp = ramp(linear_gradient(RED, BLUE, interpolation=space, hue=method))
    middle = gradient_ramp.color(gradient_ramp.index(0.5))
    assert (middle.green > max(middle.red, middle.blue)) is is_green


@pytest.mark.parametrize("make", [LinearGradient, RadialGradient, ConicGradient])
def test_every_gradient_checks_its_hue_method(make: type[Gradient]) -> None:
    with pytest.raises(ValueError, match="polar color space"):
        make(stops=(Stop(RED), Stop(BLUE)), hue="longer")


@pytest.mark.parametrize("make", [LinearGradient, RadialGradient, ConicGradient])
def test_every_gradient_takes_a_hue_method_in_a_polar_space(make: type[Gradient]) -> None:
    assert make(stops=(Stop(RED), Stop(BLUE)), interpolation="oklch", hue="longer").hue == "longer"


def test_the_radial_and_conic_functions_pass_every_option_on() -> None:
    options = {"repeating": True, "interpolation": "lch", "hue": "decreasing", "box": "margin"}
    assert radial_gradient(RED, BLUE, **options) == RadialGradient(stops=(Stop(RED), Stop(BLUE)), **options)  # type: ignore[arg-type]
    assert conic_gradient(RED, BLUE, **options) == ConicGradient(stops=(Stop(RED), Stop(BLUE)), **options)  # type: ignore[arg-type]


def test_the_conic_function_doesnt_repeat_by_default() -> None:
    assert conic_gradient(RED, BLUE).repeating is False


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (-1, 0),
        (0.25, 1024),
        (0.5, 2048),
        (0.75, 3071),
        (2, LAST),
    ],
)
def test_a_position_takes_the_nearest_entry_of_its_segment(position: float, expected: int) -> None:
    gradient_ramp = ramp(linear_gradient(RED, BLUE))
    assert (gradient_ramp.index(position), gradient_ramp.indices([position])) == (expected, (expected,))


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (0.1, 0),
        (0.2, 0),
        (0.45, 2048),
        (0.7, LAST),
        (0.9, LAST),
    ],
)
def test_a_two_stop_gradient_between_any_positions_takes_entries_across_its_stops(
    position: float, expected: int
) -> None:
    gradient_ramp = ramp(linear_gradient((RED, 0.2), (BLUE, 0.7)))
    assert (gradient_ramp.indices([position]), gradient_ramp.index(position)) == ((expected,), expected)


@pytest.mark.parametrize(("position", "expected"), [(0.3, 0), (0.5, LAST), (0.6, LAST)])
def test_two_stops_at_one_position_take_their_end_entries(position: float, expected: int) -> None:
    gradient_ramp = ramp(linear_gradient((RED, 0.5), (BLUE, 0.5)))
    assert gradient_ramp.indices([position]) == (expected,)


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (0.25, 0.25),
        (0.85, 0.35),
        (-0.15, 0.35),
        (0.6, 0.6),
    ],
)
def test_a_repeating_gradient_not_starting_at_zero_repeats_from_its_first_stop(
    position: float, expected: float
) -> None:
    stops = ((RED, 0.2), (GREEN, 0.4), (BLUE, 0.7))
    gradient_ramp = ramp(linear_gradient(*stops, repeating=True))
    plain = ramp(linear_gradient(*stops))
    assert gradient_ramp.index(position) == plain.index(expected)


def test_a_repeating_gradients_average_weights_each_segment_by_its_length() -> None:
    gradient_ramp = ramp(
        linear_gradient((BLACK, 0.2), (WHITE, 0.4), (WHITE, 0.6), repeating=True, interpolation="srgb")
    )
    # Half the span averages to half white, and the other half is white.
    assert gradient_ramp.color(gradient_ramp.index(inf)) == Color(191, 191, 191)


def test_a_repeating_gradient_with_stops_at_one_position_averages_its_segments_alike() -> None:
    gradient_ramp = ramp(
        linear_gradient((BLACK, 0.5), (BLACK, 0.5), (WHITE, 0.5), (WHITE, 0.5), repeating=True, interpolation="srgb")
    )
    # Spaced evenly, the segments are black, black to white, and white.
    assert gradient_ramp.color(gradient_ramp.index(0.5)) == Color(128, 128, 128)


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("top", [[1, 1], [0.5, 0.5], [0, 0]]),
        ("left", [[1, 0.5, 0], [1, 0.5, 0]]),
    ],
)
def test_a_side_points_the_same_way_in_a_box_of_any_shape(direction: SideOrCorner, expected: list[list[float]]) -> None:
    gradient = LinearGradient(stops=(Stop(BLACK), Stop(WHITE)), direction=direction)
    assert fractions(gradient, len(expected[0]), len(expected)) == expected


def test_an_ellipses_fractional_radii_are_fractions_of_each_axis() -> None:
    gradient = radial_gradient(BLACK, WHITE, size=(0.25, 0.5))
    assert fractions(gradient, 5, 5)[2] == [1, 1, 0, 1, 1]


@pytest.mark.parametrize(("size", "expected"), [("closest-side", 0.5), ("farthest-side", 0.25)])
def test_a_circle_sized_by_a_side_measures_the_sides_on_both_axes(size: Extent, expected: float) -> None:
    # From a center 3 columns and 1 row (2 visual units) into a 7x4 box (6 by 6):
    # the closest side is 2 away, above, and the farthest 4, below, where either side is 3 across.
    gradient = radial_gradient(BLACK, WHITE, shape="circle", size=size, at=(waxy.Length(3), waxy.Length(1)))
    assert fractions(gradient, 7, 4)[1][4] == expected


def test_a_conic_gradients_start_is_in_degrees() -> None:
    gradient = conic_gradient(BLACK, WHITE, start=90)
    assert field_indices(gradient, 3, 3, 2, region(1, 0, 2, 1)) == ((round(0.75 * LAST),),)
