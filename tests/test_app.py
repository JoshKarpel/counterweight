from counterweight.app import app
from counterweight.components import component
from counterweight.controls import PrintPaint, Quit, Screenshot, Suspend, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseDown, MouseMoved, MouseUp, TerminalResized
from counterweight.geometry import Position
from counterweight.hooks import use_rects
from counterweight.styles.utilities import full


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
            PrintPaint(),
            Suspend(handler=lambda: None),
            ToggleBorderHealing(),
            Quit(),
        ),
    )


async def test_use_rects_reflects_new_dimensions_after_resize() -> None:
    observed: list[tuple[float, float]] = []

    @component
    def root() -> Text:
        rects = use_rects()
        observed.append((rects.border.width, rects.border.height))
        return Text(content="", style=full)

    await app(
        root,
        headless=True,
        dimensions=(80, 24),
        autopilot=(
            TerminalResized(dimensions=(120, 40)),
            Quit(),
        ),
    )

    # After resize the warmup pass should populate use_rects() so that the
    # first painted render sees the new dimensions, not the old ones.
    assert (119.0, 39.0) in observed
