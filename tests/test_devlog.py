"""What the render loop writes to the devlog over an app's life, as `counterweight devlog` shows it."""

from __future__ import annotations

from counterweight import app
from counterweight._output import Frame
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.programs import TerminalStreams
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_collapse
from counterweight.styles.utilities import row
from counterweight.styles.utilities import size
from tests.devlog import devlog_lines


def screenshot(frame: Frame) -> None:
    pass


def broken_screenshot(frame: Frame) -> None:
    raise ValueError("no screenshot")


def suspended(terminal: TerminalStreams) -> None:
    pass


def broken_suspension(terminal: TerminalStreams) -> None:
    raise ValueError("no suspension")


@component
def boxes() -> Div:
    return Div(style=row | border_collapse, children=(Div(style=border | size(5, 3)), Div(style=border | size(5, 3))))


FRAME = [
    "DEBUG    counterweight._app Updated shadow tree components_run=2",
    "DEBUG    counterweight._app Calculated layout",
    "DEBUG    counterweight._app Generated new paint",
    "DEBUG    counterweight._app Healed borders in new paint hint_cells=6 diff_cells=2",
    "DEBUG    counterweight._app Diffed new paint from current paint diff_runs=3 diff_cells=27",
    "DEBUG    counterweight._app Generated instructions from paint diff",
    "DEBUG    counterweight._app Reconciled effects",
    "DEBUG    counterweight._app Completed render cycle",
]


def handled(command: object) -> list[str]:
    return [
        f"DEBUG    counterweight._app Handled autopilot command command={command!r}",
        "DEBUG    counterweight._app Handled events num_events=1",
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
        "INFO     counterweight._app Application starting...",
        *FRAME,
        *handled(autopilot[0]),
        f"DEBUG    counterweight._app Took screenshot handler={screenshot!r}",
        *handled(autopilot[1]),
        "ERROR    counterweight._app Error in screenshot handler "
        f"error=\"ValueError('no screenshot')\" handler={broken_screenshot!r}",
        *handled(autopilot[2]),
        f"DEBUG    counterweight._app Suspending application handler={suspended!r}",
        f"DEBUG    counterweight._app Resuming application handler={suspended!r}",
        *FRAME,
        *handled(autopilot[3]),
        f"DEBUG    counterweight._app Suspending application handler={broken_suspension!r}",
        "ERROR    counterweight._app Error in suspend handler "
        f"handler={broken_suspension!r} error=\"ValueError('no suspension')\"",
        f"DEBUG    counterweight._app Resuming application handler={broken_suspension!r}",
        *FRAME,
        *handled(autopilot[4]),
        "INFO     counterweight._app Quitting application...",
        "DEBUG    counterweight._app Caught KeyboardInterrupt()",
        "INFO     counterweight._app Application stopping...",
        "INFO     counterweight._app Application stopped",
    ]


async def test_the_devlog_counts_every_event_a_frame_handles() -> None:
    @component
    def counter() -> Text:
        count, set_count = use_state(0)
        return Text(content=str(count), on_input=lambda event, _: set_count(count + 1))

    with devlog_lines() as lines:
        await app(counter(), headless=True, dimensions=(3, 1), autopilot=[KeyPressed(key="a"), Quit()])

    assert "DEBUG    counterweight._app Handled events num_events=2" in lines


async def test_the_devlog_records_the_components_a_frame_runs_again_to_settle_focus() -> None:
    @component
    def label() -> Text:
        focus = use_focus(auto_focus=True)
        return Text(content="on" if focus.is_focused else "off")

    @component
    def mounts_on_key() -> Div:
        is_mounted, set_mounted = use_state(False)
        return Div(on_input=lambda event, _: set_mounted(True), children=(label(),) if is_mounted else ())

    with devlog_lines() as lines:
        await app(mounts_on_key(), headless=True, dimensions=(3, 1), autopilot=[KeyPressed(key="t"), Quit()])

    frame = lines[lines.index("DEBUG    counterweight._app Handled events num_events=2") + 1 :][:4]
    assert frame == [
        "DEBUG    counterweight._app Updated shadow tree components_run=2",
        "DEBUG    counterweight._app Calculated layout",
        "DEBUG    counterweight._app Settled focus components_run=1",
        "DEBUG    counterweight._app Generated new paint",
    ]
