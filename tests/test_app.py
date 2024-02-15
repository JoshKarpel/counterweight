from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot, Suspend
from counterweight.elements import Div
from counterweight.events import KeyPressed, MouseDownRaw, MouseMovedRaw, MouseUpRaw, TerminalResized
from counterweight.geometry import Position


async def test_headless_autopilot_events_with_empty_app() -> None:
    @component
    def root() -> Div:
        return Div()

    await app(
        root,
        headless=True,
        autopilot=(
            KeyPressed(key="f"),
            MouseMovedRaw(position=Position(0, 0), button=None),
            MouseDownRaw(position=Position(0, 0), button=1),
            MouseUpRaw(position=Position(0, 0), button=1),
            TerminalResized(),
            Screenshot(handler=lambda _: None),
            Suspend(handler=lambda: None),
            Quit(),
        ),
    )
