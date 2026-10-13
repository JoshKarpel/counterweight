import asyncio
import glob
from fnmatch import fnmatchcase
from functools import partial

import waxy

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import ScrollIntoView
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, MouseDown, MouseScrolledDown, MouseUp, Receiver
from counterweight.geometry import Position
from counterweight.handlers import clear_focus, first, focus_receiver_on_press, on_click, scroll_on_wheel, tab_focus
from counterweight.hooks import ElementHandle, use_focus, use_rects, use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

PACKAGES = (
    "counterweight",
    "hypothesis",
    "more-itertools",
    "mypy",
    "pydantic",
    "pydantic-settings",
    "pytest",
    "pytest-asyncio",
    "pytest-xdist",
    "ruff",
    "waxy",
    "wcwidth",
)
GROUPS = ("bench", "dev", "docs", "lint", "test")
PYTHONS = ("3.13", "3.14", "3.15", "3.15t")
INDEXES = ("pypi", "testpypi", "pytorch-cpu", "pytorch-cu128")
RECIPES = ("codegen", "devlog", "docs-build", "docs-serve", "mutate", "pre-commit", "profile", "test", "upgrade")

SHOWN_ROWS = 5

below = Style(layout=waxy.Style(inset_top=waxy.Percent(1.0)))
above = Style(layout=waxy.Style(inset_bottom=waxy.Percent(1.0)))


def matches(text: str, candidates: tuple[str, ...]) -> list[str]:
    pattern = f"*{'*'.join(glob.escape(c) for c in text.lower())}*"
    return [candidate for candidate in candidates if fnmatchcase(candidate.lower(), pattern)]


@component
def autocomplete(
    candidates: tuple[str, ...],
    screen_height: int,
    auto_focus: bool = False,
    list_clip: Style = clip_to_screen,
) -> Div:
    focus = use_focus(auto_focus=auto_focus)
    rects = use_rects()
    text, set_text = use_state("")
    highlighted, set_highlighted = use_state(0)
    is_dismissed, set_dismissed = use_state(False)
    highlighted_match, _ = use_state(ElementHandle)

    shown = matches(text, candidates) if text else []
    is_open = focus.is_focused and not is_dismissed and bool(shown)

    def edit(new_text: str) -> None:
        set_text(new_text)
        set_highlighted(0)
        set_dismissed(False)

    def choose(match: str) -> None:
        set_text(match)
        set_dismissed(True)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Down) if is_open:
                set_highlighted((highlighted + 1) % len(shown))
            case KeyPressed(key=Key.Up) if is_open:
                set_highlighted((highlighted - 1) % len(shown))
            case KeyPressed(key=Key.Enter | Key.Tab) if is_open:
                choose(shown[highlighted])
            case KeyPressed(key=Key.Escape) if is_open:
                set_dismissed(True)
            case KeyPressed(key=Key.Backspace):
                edit(text[:-1])
            case KeyPressed(key=typed) if not isinstance(typed, Key):
                edit(text + typed)
            case _:
                return None
        return ScrollIntoView(highlighted_match, block="nearest")

    room_above = rects.border.top
    room_below = screen_height - rects.border.bottom
    suggestions = Div(
        style=z(1)
        | position_absolute
        | (above if room_above > room_below else below)
        | inset_x(0)
        | list_clip
        | col
        | border
        | border_lightrounded
        | border_color("sky", 400)
        | max_height(SHOWN_ROWS + 2)
        | overflow_y_scroll,
        on_input=scroll_on_wheel(1),
        children=tuple(
            Text(
                content=match,
                style=pad_x(1) | (text_bg("sky", 800) if index == highlighted else text_bg("slate", 900)),
                handle=highlighted_match if index == highlighted else None,
                on_input=on_click(partial(choose, match)),
            )
            for index, match in enumerate(shown)
        ),
    )

    return Div(
        style=width(24) | (text_bg("slate", 700) if focus.is_focused else text_bg("slate", 800)),
        on_input=first(on_input, focus_receiver_on_press),
        children=(
            Text(content=f"{text}▏" if focus.is_focused else text),
            *([suggestions] if is_open else []),
        ),
    )


@component
def labelled(label: str, field: Component) -> Div:
    return Div(style=row | gap(1), children=(Text(content=f"{label:>7}"), field))


@component
def root(list_clip: Style = clip_to_screen) -> Div:
    screen = use_rects()
    height = screen.border.height

    return Div(
        style=full | col,
        on_input=first(tab_focus, clear_focus),
        children=(
            Div(
                style=fill(1) | col | border | border_lightrounded | pad_x(1),
                children=(
                    Text(content=" Add a dependency ", style=position_absolute | inset_top(-1) | clip_to_border),
                    Div(
                        style=fill(1) | col | gap(1) | overflow_y_scroll,
                        on_input=scroll_on_wheel(1),
                        children=(
                            labelled("Package", autocomplete(PACKAGES, height, auto_focus=True, list_clip=list_clip)),
                            labelled("Group", autocomplete(GROUPS, height, list_clip=list_clip)),
                            labelled("Python", autocomplete(PYTHONS, height, list_clip=list_clip)),
                            labelled("Index", autocomplete(INDEXES, height, list_clip=list_clip)),
                        ),
                    ),
                ),
            ),
            Text(
                content="Type to see suggestions. Down and Up move through them, "
                "Enter or Tab chooses one, and Escape closes them.",
                style=fill(1) | pad(1) | text_wrap_pretty | text_color("slate", 400),
            ),
            labelled("just", autocomplete(RECIPES, height, list_clip=list_clip)),
        ),
    )


# --8<-- [end:example]


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


def press(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


DOWN = KeyPressed(key=Key.Down)
TAB = KeyPressed(key=Key.Tab)
DIMENSIONS = (40, 14)

SCREENSHOTS = [
    ScreenshotSpec(root(), "autocomplete-open", DIMENSIONS, events=typed("py")),
    ScreenshotSpec(root(list_clip=clip_to_padding), "autocomplete-clipped", DIMENSIONS, events=typed("py")),
    ScreenshotSpec(root(), "autocomplete-highlighted", DIMENSIONS, events=(*typed("py"), DOWN, DOWN)),
    ScreenshotSpec(root(), "autocomplete-long", DIMENSIONS, events=(*typed("py"), *(DOWN for _ in range(5)))),
    ScreenshotSpec(
        root(), "autocomplete-chosen", DIMENSIONS, events=(*typed("py"), DOWN, DOWN, KeyPressed(key=Key.Enter))
    ),
    ScreenshotSpec(root(), "autocomplete-upward", DIMENSIONS, events=(TAB, TAB, TAB, TAB, *typed("dc"))),
    ScreenshotSpec(
        root(),
        "autocomplete-scrolled",
        DIMENSIONS,
        events=(TAB, TAB, *typed("3"), *(MouseScrolledDown(absolute=Position(4, 1)) for _ in range(3))),
    ),
]


if __name__ == "__main__":
    asyncio.run(app(root()))
