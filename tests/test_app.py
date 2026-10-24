import io
from asyncio import sleep
from asyncio import wait_for
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping

import pytest

from counterweight import DEFAULT_UNCLAIMED_KEYS
from counterweight import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Bell
from counterweight.controls import CopyToClipboard
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
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.events import TerminalResized
from counterweight.focus import ElementHandle
from counterweight.geometry import Position
from counterweight.hooks import use_effect
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles._styles import Style
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
            Suspend(handler=lambda terminal: None),
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
    [[Bell()], [SetTitle(title="hi")], [SetTitle(title="hi"), RestoreTitle()], [CopyToClipboard(text="hi")]],
    ids=["bell", "title", "restored-title", "copy"],
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


@component
def copies(handler: Callable[[str], Awaitable[None] | None] | None = None) -> Text:
    return Text(content="hi", on_input=lambda event, _: CopyToClipboard(text="copied", handler=handler))


async def test_a_copy_with_a_handler_gives_it_the_text_in_a_headless_app() -> None:
    copied: list[str] = []

    await app(copies(copied.append), headless=True, dimensions=(3, 1), autopilot=[KeyPressed(key="c"), Quit()])

    assert copied == ["copied"]


async def test_a_copy_awaits_a_handler_that_returns_an_awaitable() -> None:
    copied: list[str] = []

    async def copy(text: str) -> None:
        await sleep(0)
        copied.append(text)

    await app(copies(copy), headless=True, dimensions=(3, 1), autopilot=[KeyPressed(key="c"), Quit()])

    assert copied == ["copied"]


async def test_the_apps_clipboard_handler_takes_a_copy_without_a_handler_of_its_own() -> None:
    copied: list[str] = []

    await app(
        copies(),
        headless=True,
        dimensions=(3, 1),
        autopilot=[KeyPressed(key="c"), Quit()],
        clipboard_handler=copied.append,
    )

    assert copied == ["copied"]


async def test_a_copys_own_handler_takes_it_in_place_of_the_apps_clipboard_handler() -> None:
    own: list[str] = []
    apps: list[str] = []

    await app(
        copies(own.append),
        headless=True,
        dimensions=(3, 1),
        autopilot=[KeyPressed(key="c"), Quit()],
        clipboard_handler=apps.append,
    )

    assert (own, apps) == (["copied"], [])


async def test_an_app_keeps_running_after_a_copy_handler_raises() -> None:
    def broken(text: str) -> None:
        raise ValueError("no copy")

    copied: list[str] = []

    await app(
        copies(broken),
        headless=True,
        dimensions=(3, 1),
        autopilot=[KeyPressed(key="c"), CopyToClipboard(text="after", handler=copied.append), Quit()],
    )

    assert copied == ["after"]


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


CTRL_C = KeyPressed(key=Key.ControlC)


async def frames_after(
    events: list[KeyPressed | Pasted],
    response: InputResponse = None,
    unclaimed_keys: Mapping[str, AnyControl] = DEFAULT_UNCLAIMED_KEYS,
) -> int:
    """
    How many screenshots an app takes after `events` before it quits, one after each event,
    with a root whose handler responds to every event with `response`.
    """
    frames: list[object] = []
    autopilot: list[KeyPressed | Pasted | AnyControl] = []
    for event in events:
        autopilot += [event, Screenshot(handler=frames.append)]

    @component
    def root() -> Text:
        return Text(content="hi", on_input=lambda event, _: response)

    await app(root(), headless=True, dimensions=(3, 1), autopilot=[*autopilot, Quit()], unclaimed_keys=unclaimed_keys)
    return len(frames)


async def test_an_unclaimed_ctrl_c_quits() -> None:
    assert await frames_after([KeyPressed(key="a"), CTRL_C, KeyPressed(key="b")]) == 1


async def test_a_claimed_ctrl_c_does_not_take_its_default() -> None:
    assert await frames_after([CTRL_C, KeyPressed(key="b")], response=()) == 2


async def test_with_no_unclaimed_keys_ctrl_c_does_nothing() -> None:
    assert await frames_after([CTRL_C, KeyPressed(key="b")], unclaimed_keys={}) == 2


async def test_an_unclaimed_key_takes_the_control_it_is_given() -> None:
    assert await frames_after([KeyPressed(key="a"), KeyPressed(key="q")], unclaimed_keys={"q": Quit()}) == 1


async def test_a_paste_of_a_keys_text_does_not_take_its_default() -> None:
    assert await frames_after([Pasted(text="q"), KeyPressed(key="b")], unclaimed_keys={"q": Quit()}) == 2


def test_ctrl_z_suspends_the_app_to_the_shell_by_default() -> None:
    assert DEFAULT_UNCLAIMED_KEYS[Key.ControlZ] == Suspend.to_shell()
