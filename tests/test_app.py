from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot, Suspend, ToggleBorderHealing
from counterweight.elements import Div
from counterweight.events import KeyPressed, MouseDown, MouseMoved, MouseUp, TerminalResized
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
            MouseMoved(absolute=Position(0, 0), button=None),
            MouseDown(absolute=Position(0, 0), button=1),
            MouseMoved(absolute=Position(0, 1), button=1),
            MouseUp(absolute=Position(0, 2), button=1),
            TerminalResized(),
            Screenshot(handler=lambda _: None),
            Suspend(handler=lambda: None),
            ToggleBorderHealing(),
            Quit(),
        ),
    )
