"""
Tests that lock down current_paint tracking correctness.

These cover the cases relevant to the dirty-region refactor:
  - initial render (new content appearing on a blank screen)
  - content replacement (text changes between frames)
  - content removal (element disappears; positions become blank)
  - content addition (element appears; positions fill in)
  - terminal resize (current_paint reset; full re-render)

All tests use headless autopilot with PrintPaint(ansi=False) to capture
the plain-text grid written to current_paint.
"""

from __future__ import annotations

import io

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import PrintPaint, Quit
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, TerminalResized
from counterweight.hooks import use_state
from counterweight.styles.utilities import col, size


async def _render(root_fn: type[Component], dimensions: tuple[int, int]) -> str:
    capture = io.StringIO()
    await app(
        root_fn,
        headless=True,
        dimensions=dimensions,
        autopilot=[PrintPaint(stream=capture, ansi=False), Quit()],
    )
    return capture.getvalue().rstrip("\n")


async def _two_frames(root_fn: type[Component], dimensions: tuple[int, int]) -> tuple[str, str]:
    """Capture paint before and after a single key press."""
    c1, c2 = io.StringIO(), io.StringIO()
    await app(
        root_fn,
        headless=True,
        dimensions=dimensions,
        autopilot=[
            PrintPaint(stream=c1, ansi=False),
            KeyPressed(key="n"),
            PrintPaint(stream=c2, ansi=False),
            Quit(),
        ],
    )
    return c1.getvalue().rstrip("\n"), c2.getvalue().rstrip("\n")


# ---------------------------------------------------------------------------
# Initial render
# ---------------------------------------------------------------------------


async def test_initial_render_shows_text() -> None:
    @component
    def root() -> Div:
        return Div(children=[Text(content="Hello")])

    assert await _render(root, (10, 1)) == "Hello     "


async def test_initial_render_empty_screen_is_all_spaces() -> None:
    @component
    def root() -> Div:
        return Div()

    assert await _render(root, (5, 1)) == "     "


async def test_initial_render_multiline() -> None:
    @component
    def root() -> Div:
        return Div(
            style=col | size(6, 2),
            children=[
                Text(content="Hello"),
                Text(content="World"),
            ],
        )

    assert await _render(root, (6, 2)) == "\n".join(["Hello ", "World "])


# ---------------------------------------------------------------------------
# Content replacement
# ---------------------------------------------------------------------------


async def test_replacement_new_text_appears() -> None:
    @component
    def root() -> Div:
        text, set_text = use_state("Hello")

        def on_key(event: KeyPressed) -> None:
            set_text("World")

        return Div(on_key=on_key, children=[Text(content=text)])

    before, after = await _two_frames(root, (10, 1))
    assert before == "Hello     "
    assert after == "World     "


async def test_replacement_shorter_text_pads_with_spaces() -> None:
    """Trailing characters from the longer string must not bleed through."""

    @component
    def root() -> Div:
        text, set_text = use_state("Hello")

        def on_key(event: KeyPressed) -> None:
            set_text("Hi")

        return Div(on_key=on_key, children=[Text(content=text)])

    before, after = await _two_frames(root, (10, 1))
    assert before == "Hello     "
    assert after == "Hi        "


async def test_replacement_longer_text_fills_space() -> None:
    @component
    def root() -> Div:
        text, set_text = use_state("Hi")

        def on_key(event: KeyPressed) -> None:
            set_text("Hello")

        return Div(on_key=on_key, children=[Text(content=text)])

    before, after = await _two_frames(root, (10, 1))
    assert before == "Hi        "
    assert after == "Hello     "


# ---------------------------------------------------------------------------
# Content removal
# ---------------------------------------------------------------------------


async def test_removal_positions_become_spaces() -> None:
    @component
    def root() -> Div:
        visible, set_visible = use_state(True)

        def on_key(event: KeyPressed) -> None:
            set_visible(False)

        children = [Text(content="Hello")] if visible else []
        return Div(on_key=on_key, children=children)

    before, after = await _two_frames(root, (10, 1))
    assert before == "Hello     "
    assert after == "          "


async def test_removal_of_second_row_becomes_spaces() -> None:
    @component
    def root() -> Div:
        two_lines, set_two_lines = use_state(True)

        def on_key(event: KeyPressed) -> None:
            set_two_lines(False)

        children: list[Text] = [Text(content="Line 1")]
        if two_lines:
            children.append(Text(content="Line 2"))
        return Div(style=col | size(6, 2), on_key=on_key, children=children)

    before, after = await _two_frames(root, (6, 2))
    assert before == "\n".join(["Line 1", "Line 2"])
    assert after == "\n".join(["Line 1", "      "])


# ---------------------------------------------------------------------------
# Content addition
# ---------------------------------------------------------------------------


async def test_addition_positions_fill_in() -> None:
    @component
    def root() -> Div:
        visible, set_visible = use_state(False)

        def on_key(event: KeyPressed) -> None:
            set_visible(True)

        children = [Text(content="Hello")] if visible else []
        return Div(on_key=on_key, children=children)

    before, after = await _two_frames(root, (10, 1))
    assert before == "          "
    assert after == "Hello     "


async def test_addition_of_second_row_fills_in() -> None:
    @component
    def root() -> Div:
        two_lines, set_two_lines = use_state(False)

        def on_key(event: KeyPressed) -> None:
            set_two_lines(True)

        children: list[Text] = [Text(content="Line 1")]
        if two_lines:
            children.append(Text(content="Line 2"))
        return Div(style=col | size(6, 2), on_key=on_key, children=children)

    before, after = await _two_frames(root, (6, 2))
    assert before == "\n".join(["Line 1", "      "])
    assert after == "\n".join(["Line 1", "Line 2"])


# ---------------------------------------------------------------------------
# Terminal resize
# ---------------------------------------------------------------------------


async def test_resize_rerenders_content_correctly() -> None:
    """After TerminalResized, current_paint is reset and content redraws correctly."""

    @component
    def root() -> Div:
        return Div(children=[Text(content="Hello")])

    c1, c2 = io.StringIO(), io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(10, 1),
        autopilot=[
            PrintPaint(stream=c1, ansi=False),
            TerminalResized(),
            PrintPaint(stream=c2, ansi=False),
            Quit(),
        ],
    )
    assert c1.getvalue().rstrip("\n") == "Hello     "
    assert c2.getvalue().rstrip("\n") == "Hello     "


async def test_resize_with_new_dimensions() -> None:
    """TerminalResized(w, h) switches to the given dimensions."""

    @component
    def root() -> Div:
        return Div(children=[Text(content="Hi")])

    c1, c2 = io.StringIO(), io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(5, 1),
        autopilot=[
            PrintPaint(stream=c1, ansi=False),
            TerminalResized(dimensions=(8, 1)),
            PrintPaint(stream=c2, ansi=False),
            Quit(),
        ],
    )
    assert c1.getvalue().rstrip("\n") == "Hi   "
    assert c2.getvalue().rstrip("\n") == "Hi      "


async def test_resize_clears_stale_content() -> None:
    """After TerminalResized, positions that had content still show correctly."""

    @component
    def root() -> Div:
        text, set_text = use_state("Hello")

        def on_key(event: KeyPressed) -> None:
            set_text("Hi")

        return Div(on_key=on_key, children=[Text(content=text)])

    c1, c2, c3 = io.StringIO(), io.StringIO(), io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(10, 1),
        autopilot=[
            PrintPaint(stream=c1, ansi=False),
            KeyPressed(key="n"),
            PrintPaint(stream=c2, ansi=False),
            TerminalResized(),
            PrintPaint(stream=c3, ansi=False),
            Quit(),
        ],
    )
    assert c1.getvalue().rstrip("\n") == "Hello     "
    assert c2.getvalue().rstrip("\n") == "Hi        "
    assert c3.getvalue().rstrip("\n") == "Hi        "
