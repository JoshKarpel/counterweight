from bisect import bisect_left

import pytest

from counterweight.animation import Easing
from counterweight.animation import StepPosition
from counterweight.animation import between
from counterweight.animation import cubic_bezier
from counterweight.animation import ease
from counterweight.animation import ease_in
from counterweight.animation import ease_in_out
from counterweight.animation import ease_out
from counterweight.animation import linear
from counterweight.animation import piecewise_linear
from counterweight.animation import step_end
from counterweight.animation import step_start
from counterweight.animation import steps

SAMPLES = 200_001


def sampled_bezier(x1: float, y1: float, x2: float, y2: float, x: float) -> float:
    """The curve's `y` at `x`, interpolated between dense samples of the curve, which solving for `t` doesn't touch."""
    points = []
    for i in range(SAMPLES):
        t = i / (SAMPLES - 1)
        u = 1 - t
        points.append((3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3, 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3))
    xs = [px for px, _ in points]
    right = bisect_left(xs, x)
    (xa, ya), (xb, yb) = points[right - 1], points[right]
    return ya + (yb - ya) * (x - xa) / (xb - xa)


def test_linear_moves_at_a_steady_rate() -> None:
    assert [linear(x) for x in (0.0, 0.3, 1.0)] == [0.0, 0.3, 1.0]


@pytest.mark.parametrize(
    ("curve", "points"),
    [
        pytest.param(ease, (0.25, 0.1, 0.25, 1), id="ease"),
        pytest.param(ease_in, (0.42, 0, 1, 1), id="ease-in"),
        pytest.param(ease_out, (0, 0, 0.58, 1), id="ease-out"),
        pytest.param(ease_in_out, (0.42, 0, 0.58, 1), id="ease-in-out"),
        pytest.param(cubic_bezier(0.3, 1.6, 0.7, -0.4), (0.3, 1.6, 0.7, -0.4), id="overshooting"),
    ],
)
@pytest.mark.parametrize("x", [0.1, 0.37, 0.5, 0.83])
def test_a_cubic_bezier_follows_its_curve(curve: Easing, points: tuple[float, float, float, float], x: float) -> None:
    assert curve(x) == pytest.approx(sampled_bezier(*points, x), abs=1e-5)


@pytest.mark.parametrize(
    "x",
    [
        pytest.param(0.5 + 5e-5, id="flat-at-the-first-guess"),
        pytest.param(0.501, id="newton-overshoots"),
    ],
)
def test_a_cubic_bezier_with_a_flat_point_is_solved_by_bisection(x: float) -> None:
    assert cubic_bezier(1, 0.2, 0, 0.8)(x) == pytest.approx(sampled_bezier(1, 0.2, 0, 0.8, x), abs=1e-5)


@pytest.mark.parametrize("curve", [ease, ease_in, ease_out, ease_in_out], ids=["ease", "in", "out", "in-out"])
def test_a_cubic_bezier_is_exactly_at_its_ends(curve: Easing) -> None:
    assert (curve(0.0), curve(1.0)) == (0.0, 1.0)


@pytest.mark.parametrize("points", [(-0.1, 0, 1, 1), (0, 0, 1.1, 1)], ids=["x1", "x2"])
def test_a_cubic_bezier_that_goes_back_in_time_raises(points: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="x1 and x2 must be from 0 to 1"):
        cubic_bezier(*points)


@pytest.mark.parametrize(
    ("curve", "x", "expected"),
    [
        pytest.param(piecewise_linear(0, 0.25, 1), 0.25, 0.125, id="spread-evenly"),
        pytest.param(piecewise_linear(0, (0.25, 0.75), 1), 0.75, 0.25, id="at-an-input"),
        pytest.param(piecewise_linear(0, (0.25, 0.75), 1), 0.375, 0.125, id="before-an-input"),
        pytest.param(piecewise_linear(0, (0.5, 0.25, 0.75), 1), 0.6, 0.5, id="held-between-two-inputs"),
        pytest.param(piecewise_linear(0, (0.5, 0.25, 0.75), 1), 0.125, 0.25, id="leading-up-to-a-hold"),
        pytest.param(piecewise_linear(0, 0.2, 0.4, (1, 0.9)), 0.3, 0.2, id="spread-up-to-a-given-input"),
        pytest.param(piecewise_linear(0, (0.5, 0.6), (0.75, 0.4), 1), 0.6, 0.75, id="raised-to-an-earlier-input"),
        pytest.param(piecewise_linear(0, (0.5, 0.6), (0.75, 0.4), 1), 0.3, 0.25, id="before-a-jump"),
        pytest.param(piecewise_linear(0, 1), 1.0, 1.0, id="at-the-end"),
        pytest.param(piecewise_linear((0, 0.2), 1), 0.6, 0.5, id="from-a-given-first-input"),
        pytest.param(piecewise_linear(0, (0.5, 1), (1, 1)), 1.0, 1.0, id="jumping-at-the-end"),
    ],
)
def test_piecewise_linear_moves_in_straight_lines_between_its_stops(curve: Easing, x: float, expected: float) -> None:
    assert curve(x) == pytest.approx(expected)


def test_piecewise_linear_with_one_stop_raises() -> None:
    with pytest.raises(ValueError, match="at least two stops"):
        piecewise_linear(0.5)


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        pytest.param("jump-end", [0, 0, 0.25, 0.75, 1], id="jump-end"),
        pytest.param("jump-start", [0.25, 0.25, 0.5, 1, 1], id="jump-start"),
        pytest.param("jump-none", [0, 0, 1 / 3, 1, 1], id="jump-none"),
        pytest.param("jump-both", [0.2, 0.2, 0.4, 0.8, 1], id="jump-both"),
    ],
)
def test_steps_jump_where_their_position_says(position: StepPosition, expected: list[float]) -> None:
    curve = steps(4, position)

    assert [curve(x) for x in (0, 0.24, 0.25, 0.99, 1)] == pytest.approx(expected)


def test_step_start_jumps_to_the_end_at_once() -> None:
    assert (step_start(0), step_start(0.5)) == (1, 1)


def test_step_end_holds_the_start_until_the_end() -> None:
    assert (step_end(0.99), step_end(1)) == (0, 1)


@pytest.mark.parametrize(
    ("count", "position"),
    [pytest.param(0, "jump-end", id="no-steps"), pytest.param(1, "jump-none", id="one-step-without-jumps")],
)
def test_steps_that_never_move_raise(count: int, position: StepPosition) -> None:
    with pytest.raises(ValueError, match="never moves"):
        steps(count, position)


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        pytest.param(0.1, 0.0, id="before"),
        pytest.param(0.5, 0.5, id="during"),
        pytest.param(0.9, 1.0, id="after"),
    ],
)
def test_between_is_how_far_progress_is_through_a_phase(progress: float, expected: float) -> None:
    assert between(progress, 0.25, 0.75) == pytest.approx(expected)


def test_between_a_phase_that_ends_before_it_starts_raises() -> None:
    with pytest.raises(ValueError, match="stop must be after its start"):
        between(0.5, 0.75, 0.75)
