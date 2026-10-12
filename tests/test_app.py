import io
from asyncio import wait_for

import pytest

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import Quit, Screenshot, Suspend, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseDown, MouseMoved, MouseUp, TerminalResized
from counterweight.geometry import Position
from counterweight.hooks import use_effect, use_state
from counterweight.styles.styles import Style
from counterweight.styles.utilities import border, col, full, text_wrap_stable


async def test_headless_autopilot_events_with_empty_app() -> None:
    @component
    def root() -> Div:
        return Div()

    await app(
        root(),
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
        check_purity=True,
    )


async def render_text(root: Component, dimensions: tuple[int, int]) -> list[str]:
    capture = io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()],
        check_purity=True,
    )
    return capture.getvalue().rstrip("\n").split("\n")


@pytest.mark.parametrize("root_style", [col, col | full])
async def test_root_fills_screen_whatever_its_content_width(root_style: Style) -> None:
    @component
    def root() -> Div:
        return Div(style=root_style | border, children=[Text(content="wider than the screen")])

    assert await render_text(root(), (10, 3)) == [
        "┌────────┐",
        "│wider th│",
        "└────────┘",
    ]


async def test_wrapping_text_in_root_wraps_at_screen_width() -> None:
    @component
    def root() -> Div:
        return Div(style=col, children=[Text(content="aaa bbb ccc", style=text_wrap_stable)])

    assert await render_text(root(), (7, 3)) == [
        "aaa bbb",
        "ccc    ",
        "       ",
    ]


class Boom(Exception):
    pass


@component
def raises_in_render() -> Text:
    is_pressed, set_is_pressed = use_state(False)
    if is_pressed:
        raise Boom()

    def on_key(_: KeyPressed) -> None:
        set_is_pressed(True)

    return Text(content="", on_key=on_key)


@component
def raises_in_handler() -> Text:
    def on_key(_: KeyPressed) -> None:
        raise Boom()

    return Text(content="", on_key=on_key)


@component
def raises_in_effect() -> Text:
    async def setup() -> None:
        raise Boom()

    use_effect(setup, deps=())
    return Text(content="")


@pytest.mark.parametrize(
    "root", [raises_in_render(), raises_in_handler(), raises_in_effect()], ids=lambda r: r.func.__name__
)
async def test_app_raises_a_lone_error_itself_rather_than_in_an_exception_group(root: Component) -> None:
    # No Quit: it would end the app before the effect's task runs. The error ends it instead.
    with pytest.raises(Boom) as raised:
        await wait_for(
            app(root, headless=True, dimensions=(10, 2), autopilot=[KeyPressed(key="x")], check_purity=True),
            timeout=5,
        )

    assert not isinstance(raised.value.__context__, BaseExceptionGroup)


@component
def raises_in_two_effects() -> Text:
    async def setup() -> None:
        raise Boom()

    use_effect(setup, deps=())
    use_effect(setup, deps=())
    return Text(content="")


async def test_app_raises_simultaneous_errors_in_an_exception_group() -> None:
    with pytest.RaisesGroup(Boom, Boom):
        await wait_for(app(raises_in_two_effects(), headless=True, dimensions=(10, 2), check_purity=True), timeout=5)
