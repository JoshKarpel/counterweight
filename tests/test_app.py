import io
from collections.abc import Callable

import pytest

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import Quit, Screenshot, Suspend, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseDown, MouseMoved, MouseUp, TerminalResized
from counterweight.geometry import Position
from counterweight.styles.styles import Style
from counterweight.styles.utilities import border_light, col, full, text_wrap_stable


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
            Screenshot.to_stream(),
            Suspend(handler=lambda: None),
            ToggleBorderHealing(),
            Quit(),
        ),
    )


async def render_text(root: Callable[[], Component], dimensions: tuple[int, int]) -> list[str]:
    capture = io.StringIO()
    await app(root, headless=True, dimensions=dimensions, autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()])
    return capture.getvalue().rstrip("\n").split("\n")


@pytest.mark.parametrize("root_style", [col, col | full])
async def test_root_fills_screen_whatever_its_content_width(root_style: Style) -> None:
    @component
    def root() -> Div:
        return Div(style=root_style | border_light, children=[Text(content="wider than the screen")])

    assert await render_text(root, (10, 3)) == [
        "┌────────┐",
        "│wider th│",
        "└────────┘",
    ]


async def test_wrapping_text_in_root_wraps_at_screen_width() -> None:
    @component
    def root() -> Div:
        return Div(style=col, children=[Text(content="aaa bbb ccc", style=text_wrap_stable)])

    assert await render_text(root, (7, 3)) == [
        "aaa bbb",
        "ccc    ",
        "       ",
    ]
