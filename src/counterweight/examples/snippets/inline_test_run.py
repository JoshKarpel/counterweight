"""
Inline apps: A test run

A test run's live progress: a bar and the test running now below the prompt,
with each failure printed above it as it happens, and a summary left behind when the run finishes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from counterweight import Inline
from counterweight import app
from counterweight.components import component
from counterweight.controls import Print
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.hooks import use_clock
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_ref
from counterweight.styles.utilities import *

VIEWPORT = Inline()


@dataclass(frozen=True, slots=True)
class Outcome:
    test: str
    failure: str | None = None
    """What went wrong, or `None` if the test passed."""


OUTCOMES = (
    Outcome("test_layout.py::test_a_row_splits_its_width"),
    Outcome("test_layout.py::test_a_column_splits_its_height"),
    Outcome(
        "test_paint.py::test_a_border_heals_where_it_meets_another",
        failure="assert '┬' == '┐', the cell at (4, 0)",
    ),
    Outcome("test_paint.py::test_a_wide_grapheme_takes_two_cells"),
    Outcome("test_input.py::test_a_paste_arrives_whole"),
    Outcome("test_input.py::test_ctrl_c_quits"),
    Outcome(
        "test_scroll.py::test_a_log_sticks_to_its_end",
        failure="assert 12 == 14, the log's scroll offset after two more lines",
    ),
    Outcome("test_scroll.py::test_scroll_into_view_moves_the_least"),
)

TICK = timedelta(milliseconds=300)


# --8<-- [start:failure]


def failure_report(outcome: Outcome) -> Div:
    return Div(
        style=col | border_left | border_heavy | border_color("red", 500) | pad_left(1),
        children=(
            Text(content=f"FAILED {outcome.test}", style=text_color("red", 400) | text_bold | text_wrap_stable),
            Text(content=outcome.failure or "", style=text_color("slate", 300) | text_wrap_stable),
        ),
    )


# --8<-- [end:failure]

# --8<-- [start:test-run]


@component
def test_run() -> Div:
    # One test finishes each tick, as each takes a while to run.
    finished = min(use_clock(TICK).since_mount // TICK, len(OUTCOMES))
    reported_through = use_ref(0)
    send = use_controls()
    failures = sum(outcome.failure is not None for outcome in OUTCOMES[:finished])
    is_done = finished == len(OUTCOMES)

    async def report() -> None:
        for outcome in OUTCOMES[reported_through.current : finished]:
            if outcome.failure is not None:
                send(Print(failure_report(outcome)))
        reported_through.current = finished
        if is_done:
            send(Quit())

    use_effect(report, deps=(finished,))

    width = 30
    filled = width * finished // len(OUTCOMES)
    return Div(
        style=col,
        children=(
            Div(
                style=row | gap_width(1),
                children=(
                    Div(
                        style=row,
                        children=(
                            Text(content="█" * filled, style=text_color("emerald", 400) | text_wrap_none),
                            Text(content="░" * (width - filled), style=text_color("slate", 600) | text_wrap_none),
                        ),
                    ),
                    Text(content=f"{finished}/{len(OUTCOMES)}", style=text_wrap_none),
                ),
            ),
            Text(
                content=f"{finished - failures} passed, {failures} failed"
                + ("" if is_done else f" · running {OUTCOMES[finished].test}"),
                style=text_wrap_none | (text_color("red", 400) if failures else text_color("emerald", 400)),
            ),
        ),
    )


# --8<-- [end:test-run]


ROOTS = (test_run,)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

DIMENSIONS = (72, 8)

STILLS = [Still("inline-test-run", test_run(), (72, 4), steps=[AdvanceClock(by=TICK * 5)], viewport=VIEWPORT)]

DEMOS = [
    Demo(
        "inline-test-run",
        test_run(),
        DIMENSIONS,
        steps=[*[AdvanceClock(by=TICK)] * len(OUTCOMES)],
        viewport=VIEWPORT,
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(test_run(), viewport=VIEWPORT))
