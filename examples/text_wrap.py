import asyncio
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseEvent, MouseUp
from counterweight.hooks import use_hovered, use_state
from counterweight.keys import Key
from counterweight.styles.styles import TextWrap
from counterweight.styles.utilities import *

WRAP_MODES: tuple[TextWrap, ...] = ("none", "stable", "balance", "pretty")

SAMPLE = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vainly men themselves amaze to win the palm, the oak, or the bays."
)


def _make_on_click(set_wrap_idx: Callable[[int], None], idx: int) -> Callable[[], None]:
    return lambda: set_wrap_idx(idx)


@component
def root() -> Div:
    input_text, set_input_text = use_state(SAMPLE)
    wrap_idx, set_wrap_idx = use_state(2)  # start on "balance"

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.ControlC:
                return Quit()
            case Key.BackTab:
                set_wrap_idx(lambda i: (i + 1) % len(WRAP_MODES))
            case Key.Backspace:
                set_input_text(lambda t: t[:-1])
            case char if len(char) == 1 and char.isprintable():
                set_input_text(lambda t: t + char)
        return None

    return Div(
        style=col | full | align_children_stretch,
        on_key=on_key,
        children=[
            Text(
                content="Text Wrap Demo",
                style=text_justify_center | text_color("amber", 400) | pad_y(1),
            ),
            Div(
                style=row | grow(1) | gap(1) | pad_x(1) | align_children_stretch,
                children=[
                    input_pane(input_text),
                    display_pane(input_text, WRAP_MODES[wrap_idx], set_wrap_idx),
                ],
            ),
            Text(
                content="type to edit  ·  shift+tab: cycle wrap mode  ·  ctrl+c: quit",
                style=text_justify_center | text_color("slate", 500) | pad_y(1),
            ),
        ],
    )


@component
def input_pane(content: str) -> Div:
    return Div(
        style=grow(1)
        | min_width(0)
        | col
        | align_children_stretch
        | border_lightrounded
        | border_color("sky", 600)
        | pad_x(1),
        children=[
            Text(
                content="Input — stable wrap",
                style=text_color("sky", 400) | text_justify_center | pad_y(1),
            ),
            Text(
                content=content + "▌",
                style=grow(1) | text_wrap_stable | text_color("sky", 100),
            ),
        ],
    )


@component
def display_pane(
    content: str,
    mode: TextWrap,
    set_wrap_idx: Callable[[int | Callable[[int], int]], None],
) -> Div:
    wrap_style = {
        "none": text_wrap_none,
        "stable": text_wrap_stable,
        "balance": text_wrap_balance,
        "pretty": text_wrap_pretty,
    }[mode]

    return Div(
        style=grow(1)
        | min_width(0)
        | col
        | align_children_stretch
        | border_lightrounded
        | border_color("violet", 600)
        | pad_x(1),
        children=[
            Text(
                content="Display",
                style=text_color("violet", 400) | text_justify_center | pad_top(1),
            ),
            Div(
                style=row | justify_children_space_evenly | full_width | pad_y(1),
                children=[
                    mode_button(
                        label=m,
                        active=(m == mode),
                        on_click=_make_on_click(set_wrap_idx, i),
                    )
                    for i, m in enumerate(WRAP_MODES)
                ],
            ),
            Text(
                content=content or " ",
                style=grow(1) | wrap_style | text_color("violet", 100),
            ),
        ],
    )


@component
def mode_button(label: str, active: bool, on_click: Callable[[], None]) -> Text:
    hovered = use_hovered()

    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseUp(button=1):
                on_click()

    if active:
        style = border_heavy | border_color("violet", 400) | text_color("violet", 100)
    elif hovered.border:
        style = border_light | border_color("slate", 400) | text_color("slate", 200)
    else:
        style = border_light | border_color("slate", 700) | text_color("slate", 500)

    return Text(
        content=f" {label} ",
        on_mouse=on_mouse,
        style=style,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
