import io
from asyncio import wait_for

import pytest

from counterweight.app import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Bell
from counterweight.controls import Quit
from counterweight.controls import RestoreTitle
from counterweight.controls import Screenshot
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollTo
from counterweight.controls import SetTitle
from counterweight.controls import Suspend
from counterweight.controls import ToggleBorderHealing
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.events import TerminalResized
from counterweight.focus import ElementHandle
from counterweight.geometry import Position
from counterweight.hooks import use_effect
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.styles.styles import Style
from counterweight.styles.utilities import border
from counterweight.styles.utilities import col
from counterweight.styles.utilities import full
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import size
from counterweight.styles.utilities import text_wrap_stable


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
        return Div(style=root_style | border, children=(Text(content="wider than the screen"),))

    assert await render_text(root(), (10, 3)) == [
        "┌────────┐",
        "│wider tha",
        "└────────┘",
    ]


async def test_root_fills_screen_whatever_its_content_height() -> None:
    @component
    def root() -> Div:
        return Div(style=border, children=(Text(content="\n".join("taller")),))

    assert await render_text(root(), (6, 4)) == [
        "┌────┐",
        "│t   │",
        "│a   │",
        "└l───┘",
    ]


async def test_wrapping_text_in_root_wraps_at_screen_width() -> None:
    @component
    def root() -> Div:
        return Div(style=col, children=(Text(content="aaa bbb ccc", style=text_wrap_stable),))

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
        raise Boom

    def on_input(event: InputEvent, _: Receiver) -> None:
        set_is_pressed(True)

    return Text(content="", on_input=on_input)


@component
def raises_in_handler() -> Text:
    def on_input(event: InputEvent, _: Receiver) -> None:
        raise Boom

    return Text(content="", on_input=on_input)


@component
def raises_in_effect() -> Text:
    async def setup() -> None:
        raise Boom

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
        raise Boom

    use_effect(setup, deps=())
    use_effect(setup, deps=())
    return Text(content="")


async def test_app_raises_simultaneous_errors_in_an_exception_group() -> None:
    with pytest.RaisesGroup(Boom, Boom):
        await wait_for(app(raises_in_two_effects(), headless=True, dimensions=(10, 2), check_purity=True), timeout=5)


@pytest.mark.parametrize(
    "controls",
    [[Bell()], [SetTitle(title="hi")], [SetTitle(title="hi"), RestoreTitle()]],
    ids=["bell", "title", "restored-title"],
)
async def test_a_headless_app_writes_nothing_even_for_a_control_that_writes_to_the_terminal(
    controls: list[AnyControl],
) -> None:
    @component
    def root() -> Text:
        return Text(content="hi")

    output = io.StringIO()

    await app(root(), output_stream=output, headless=True, dimensions=(3, 1), autopilot=[*controls, Quit()])

    assert output.getvalue() == ""


HANDLE = ElementHandle()


def scroller(count: int) -> Div:
    """A container 1 row tall over `count` lines, scrolling vertically."""
    return Div(
        style=col | size(6, 1) | overflow_y_scroll,
        handle=HANDLE,
        children=tuple(Text(content=f"line {i}") for i in range(count)),
    )


async def test_scroll_controls_one_handler_returns_compose_in_order() -> None:
    @component
    def root() -> Div:
        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            return ScrollBy(HANDLE, y=2), ScrollBy(HANDLE, y=1)

        return Div(on_input=on_input, children=(scroller(5),))

    capture = io.StringIO()
    await app(
        root(),
        headless=True,
        dimensions=(6, 1),
        autopilot=[KeyPressed(key="j"), Screenshot.to_stream(capture, ansi=False), Quit()],
        check_purity=True,
    )

    assert capture.getvalue() == "line 3\n"


async def test_a_component_reading_another_elements_scroll_renders_again_once_after_it_scrolls() -> None:
    reports: list[int] = []

    @component
    def beside() -> Div:
        scroll = use_scroll(HANDLE)
        reports.append(scroll.offset.y)
        return Div(style=col, children=(Text(content=str(scroll.offset.y)), scroller(5)))

    await app(
        beside(),
        headless=True,
        dimensions=(6, 2),
        autopilot=[
            ScrollTo(HANDLE, y=3),
            Screenshot(handler=lambda _: None),
            Screenshot(handler=lambda _: None),
            Quit(),
        ],
    )

    # Once for the warmup, once on the first painted frame, and once after the scroll.
    assert reports == [0, 0, 3]
