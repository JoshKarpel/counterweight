"""What the render loop writes to the devlog over an app's life, as `counterweight devlog` shows it."""

from __future__ import annotations

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit, Screenshot, Suspend
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.output import Frame
from counterweight.styles.utilities import border, border_collapse, row, size
from tests.devlog import devlog_lines


def screenshot(frame: Frame) -> None:
    pass


def broken_screenshot(frame: Frame) -> None:
    raise ValueError("no screenshot")


def suspended() -> None:
    pass


def broken_suspension() -> None:
    raise ValueError("no suspension")


@component
def boxes() -> Div:
    return Div(style=row | border_collapse, children=(Div(style=border | size(5, 3)), Div(style=border | size(5, 3))))


FRAME = [
    "DEBUG    counterweight.app Updated shadow tree components_run=2",
    "DEBUG    counterweight.app Calculated layout",
    "DEBUG    counterweight.app Generated new paint",
    "DEBUG    counterweight.app Healed borders in new paint hint_cells=6 diff_cells=2",
    "DEBUG    counterweight.app Diffed new paint from current paint diff_runs=3 diff_cells=27",
    "DEBUG    counterweight.app Generated instructions from paint diff",
    "DEBUG    counterweight.app Reconciled effects",
    "DEBUG    counterweight.app Completed render cycle",
]


def handled(command: object) -> list[str]:
    return [
        f"DEBUG    counterweight.app Handled autopilot command command={command!r}",
        "DEBUG    counterweight.app Handled events num_events=1",
    ]


async def test_the_devlog_records_each_frame_control_and_handler_failure() -> None:
    autopilot: list[AnyControl] = [
        Screenshot(handler=screenshot),
        Screenshot(handler=broken_screenshot),
        Suspend(handler=suspended),
        Suspend(handler=broken_suspension),
        Quit(),
    ]

    with devlog_lines() as lines:
        await app(boxes(), headless=True, dimensions=(9, 3), autopilot=autopilot)

    assert lines == [
        "INFO     counterweight.app Application starting...",
        *FRAME,
        *handled(autopilot[0]),
        f"DEBUG    counterweight.app Took screenshot handler={screenshot!r}",
        *handled(autopilot[1]),
        "ERROR    counterweight.app Error in screenshot handler "
        f"error=\"ValueError('no screenshot')\" handler={broken_screenshot!r}",
        *handled(autopilot[2]),
        f"DEBUG    counterweight.app Suspending application handler={suspended!r}",
        f"DEBUG    counterweight.app Resuming application handler={suspended!r}",
        *FRAME,
        *handled(autopilot[3]),
        f"DEBUG    counterweight.app Suspending application handler={broken_suspension!r}",
        "ERROR    counterweight.app Error in suspend handler "
        f"handler={broken_suspension!r} error=\"ValueError('no suspension')\"",
        f"DEBUG    counterweight.app Resuming application handler={broken_suspension!r}",
        *FRAME,
        *handled(autopilot[4]),
        "INFO     counterweight.app Quitting application...",
        "DEBUG    counterweight.app Caught KeyboardInterrupt()",
        "INFO     counterweight.app Application stopping...",
        "INFO     counterweight.app Application stopped",
    ]


async def test_the_devlog_counts_every_event_a_frame_handles() -> None:
    @component
    def counter() -> Text:
        count, set_count = use_state(0)
        return Text(content=str(count), on_input=lambda event, _: set_count(count + 1))

    with devlog_lines() as lines:
        await app(counter(), headless=True, dimensions=(3, 1), autopilot=[KeyPressed(key="a"), Quit()])

    assert "DEBUG    counterweight.app Handled events num_events=2" in lines
