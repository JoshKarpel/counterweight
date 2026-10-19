"""
Hooks: use_controls

A test log that scrolls its first failure into view from an effect.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ScrollIntoView
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

LOG = (
    *(f"ok   tests/test_{name}.py" for name in ("app", "clock", "elements", "events", "focus", "geometry", "hooks")),
    "FAIL tests/test_layout.py::test_wraps",
    "     expected 3 lines, got 4",
    *(f"ok   tests/test_{name}.py" for name in ("output", "paint", "routing", "shadow", "styles")),
)

# --8<-- [start:example]


@component
def results_log(lines: tuple[str, ...] = LOG) -> Div:
    first_failure, _ = use_state(ElementHandle)
    send_control = use_controls()
    failure_index = next((i for i, line in enumerate(lines) if line.startswith("FAIL")), None)

    async def show_first_failure() -> None:
        if failure_index is not None:
            send_control(ScrollIntoView(first_failure, block="center"))

    use_effect(show_first_failure, deps=(failure_index,))

    return Div(
        style=col | border | border_lightrounded | pad_x(1) | size(42, 7) | overflow_y_scroll,
        on_input=scroll_on_wheel(),
        children=tuple(
            Text(
                content=line,
                style=text_color("red" if line.startswith("FAIL") else "slate", 400),
                handle=first_failure if i == failure_index else None,
            )
            for i, line in enumerate(lines)
        ),
    )


# --8<-- [end:example]


ROOTS = (results_log,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("use-controls-first-error", results_log(LOG), (42, 7))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(results_log()))
