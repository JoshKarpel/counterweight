"""
The pure half of animation: the easing functions that shape how an animation moves,
which are CSS's (`linear`, `cubic_bezier` and its named curves, `steps`),
and `between`, which picks one phase out of an animation's progress, as a keyframe does.
The hooks that read an animation's progress from the clock are `use_progress` and `use_loop`.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable
from datetime import timedelta
from itertools import pairwise
from math import floor
from math import inf
from typing import Literal
from typing import assert_never

type Easing = Callable[[float], float]
"""
How far along an animation has got, given how far through its time it is, both from 0 to 1,
as CSS's `<easing-function>` is. Any function of that shape is one.
"""

FRAME_INTERVAL = timedelta(milliseconds=50)
"""How often an animation hook reads the clock while it's moving, unless it's given an `interval`: 20 frames a second."""

type StepPosition = Literal["jump-start", "jump-end", "jump-none", "jump-both"]
"""Where `steps` puts its jumps, as CSS's `<step-position>` does."""


def linear(progress: float) -> float:
    """Moves at a steady rate: CSS's `linear` keyword."""
    return progress


def piecewise_linear(*stops: float | tuple[float, float] | tuple[float, float, float]) -> Easing:
    """
    Moves in straight lines between `stops`, as CSS's `linear()` function does.

    Each stop is an output alone, an `(output, input)` pair, or an `(output, start, end)` triple,
    which holds the output from the input `start` to `end`, as `linear(0, 0.25 75%, 1)` is
    `piecewise_linear(0, (0.25, 0.75), 1)`.
    As in CSS, the first stop's input defaults to 0 and the last's to 1,
    an input less than an earlier stop's is raised to it,
    and stops without inputs are spread evenly between the stops on either side that have them.

    Raises:
        ValueError: If there are fewer than two stops.
    """
    if len(stops) < 2:
        raise ValueError(f"piecewise_linear needs at least two stops, but got {len(stops)}")

    outputs: list[float] = []
    given: list[float | None] = []
    for stop in stops:
        match stop:
            case float() | int():
                outputs.append(stop)
                given.append(None)
            case (output, at):
                outputs.append(output)
                given.append(at)
            case (output, start, end):
                outputs.extend((output, output))
                given.extend((start, end))
            case _ as unreachable:
                assert_never(unreachable)

    if given[0] is None:
        given[0] = 0
    if given[-1] is None:
        given[-1] = 1

    known: dict[int, float] = {}
    highest = -inf
    for index, given_input in enumerate(given):
        if given_input is not None:
            highest = known[index] = max(highest, given_input)

    inputs: list[float] = []
    for before, after in pairwise(known):
        start, end = known[before], known[after]
        inputs.extend(start + (end - start) * offset / (after - before) for offset in range(after - before))
    inputs.append(highest)

    def ease(progress: float) -> float:
        a = min(max(bisect_right(inputs, progress) - 1, 0), len(inputs) - 2)
        a_input, b_input = inputs[a], inputs[a + 1]
        if a_input == b_input:
            return outputs[a + 1]
        return outputs[a] + (progress - a_input) / (b_input - a_input) * (outputs[a + 1] - outputs[a])

    return ease


NEWTON_ITERATIONS = 8
PRECISION = 1e-7


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Easing:
    """
    Moves along the cubic Bézier curve from `(0, 0)` to `(1, 1)` with control points `(x1, y1)` and `(x2, y2)`,
    as CSS's `cubic-bezier()` function does.
    A `y` outside 0 to 1 overshoots, so the animation goes past its end, or before its start, and comes back.

    Raises:
        ValueError: If `x1` or `x2` is outside 0 to 1, where the curve would go back in time.
    """
    if not (0 <= x1 <= 1 and 0 <= x2 <= 1):
        raise ValueError(f"cubic_bezier's x1 and x2 must be from 0 to 1, but got {x1!r} and {x2!r}")

    # The curve's coordinates as polynomials in its parameter `t`, from 0 to 1.
    cx = 3 * x1
    bx = 3 * (x2 - x1) - cx
    ax = 1 - cx - bx
    cy = 3 * y1
    by = 3 * (y2 - y1) - cy
    ay = 1 - cy - by

    def x_at(t: float) -> float:
        return ((ax * t + bx) * t + cx) * t

    def y_at(t: float) -> float:
        return ((ay * t + by) * t + cy) * t

    def t_for(x: float) -> float:
        """The parameter at which the curve reaches `x`: by Newton's method, or by bisection where that stalls."""
        t = x
        for _ in range(NEWTON_ITERATIONS):
            error = x_at(t) - x
            if abs(error) < PRECISION:
                return t
            slope = (3 * ax * t + 2 * bx) * t + cx
            if abs(slope) < PRECISION:
                break
            t -= error / slope
        low, high = 0.0, 1.0
        t = x
        while high - low > PRECISION:
            if x_at(t) < x:
                low = t
            else:
                high = t
            t = (low + high) / 2
        return t

    def ease(progress: float) -> float:
        # Exactly at the ends, so an animation that has finished is exactly where it ends.
        if progress <= 0 or progress >= 1:
            return progress
        return y_at(t_for(progress))

    return ease


ease = cubic_bezier(0.25, 0.1, 0.25, 1)
"""Starts quickly and slows gently to the end: CSS's `ease`, its default for transitions."""
ease_in = cubic_bezier(0.42, 0, 1, 1)
"""Starts slowly and speeds up to the end: CSS's `ease-in`."""
ease_out = cubic_bezier(0, 0, 0.58, 1)
"""Starts quickly and slows to the end: CSS's `ease-out`."""
ease_in_out = cubic_bezier(0.42, 0, 0.58, 1)
"""Starts slowly, speeds up, and slows to the end: CSS's `ease-in-out`."""


def steps(count: int, position: StepPosition = "jump-end") -> Easing:
    """
    Moves in `count` equal jumps rather than smoothly, as CSS's `steps()` function does,
    such as to step through the frames of a spinner.
    `position` says where the jumps are: `"jump-end"` holds each step until it ends (CSS's default),
    `"jump-start"` jumps at the start of each, `"jump-none"` at neither end, so it holds 0 and 1 for a step each,
    and `"jump-both"` at both.

    Raises:
        ValueError: If `count` isn't positive, or is less than 2 for `"jump-none"`, which would never move.
    """
    jumps = {"jump-start": count, "jump-end": count, "jump-none": count - 1, "jump-both": count + 1}[position]
    if count < 1 or jumps < 1:
        raise ValueError(f"steps({count!r}, {position!r}) never moves")
    is_jumping_at_start = position in ("jump-start", "jump-both")

    def ease(progress: float) -> float:
        step = floor(progress * count) + is_jumping_at_start
        return min(max(step, 0), jumps) / jumps

    return ease


step_start = steps(1, "jump-start")
"""Jumps to the end as soon as it starts: CSS's `step-start`."""
step_end = steps(1, "jump-end")
"""Holds the start until the end, then jumps: CSS's `step-end`."""


def between(progress: float, start: float, stop: float) -> float:
    """
    How far `progress` is through the part of an animation from `start` to `stop`: 0 before it, 1 after it,
    as a keyframe's offsets pick a phase out of a CSS animation,
    so one animation's progress can run several motions one after another, each with its own easing.

    Raises:
        ValueError: If `stop` isn't after `start`.
    """
    if stop <= start:
        raise ValueError(f"between's stop must be after its start, but got {start!r} to {stop!r}")
    return min(max((progress - start) / (stop - start), 0.0), 1.0)


__all__ = [
    "FRAME_INTERVAL",
    "Easing",
    "StepPosition",
    "between",
    "cubic_bezier",
    "ease",
    "ease_in",
    "ease_in_out",
    "ease_out",
    "linear",
    "piecewise_linear",
    "step_end",
    "step_start",
    "steps",
]
