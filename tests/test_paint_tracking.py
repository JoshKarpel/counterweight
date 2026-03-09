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
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import PrintPaint, Quit
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, TerminalResized
from counterweight.hooks import use_state
from counterweight.styles.utilities import col, size


async def _render(root_fn: Callable[[], Component], dimensions: tuple[int, int]) -> str:
    capture = io.StringIO()
    await app(
        root_fn,
        headless=True,
        dimensions=dimensions,
        autopilot=[PrintPaint(stream=capture, ansi=False), Quit()],
    )
    return capture.getvalue().rstrip("\n")


async def _two_frames(root_fn: Callable[[], Component], dimensions: tuple[int, int]) -> tuple[str, str]:
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

    assert await _render(root, (5, 3)) == "\n".join(["     ", "     ", "     "])


async def test_initial_render_uncovered_rows_are_spaces() -> None:
    """Rows not touched by any element must still render as spaces."""

    @component
    def root() -> Div:
        return Div(
            style=size(5, 1),
            children=[Text(content="Hello")],
        )

    assert await _render(root, (5, 3)) == "\n".join(["Hello", "     ", "     "])


async def test_ansi_background_is_explicit_black() -> None:
    """With ansi=True, every cell — even blank ones — has explicit black-background ANSI codes."""

    @component
    def root() -> Div:
        return Div()

    capture = io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(2, 1),
        autopilot=[PrintPaint(stream=capture, ansi=True), Quit()],
    )
    output = capture.getvalue()
    # Every position should carry the black background escape
    assert output.count("\x1b[48;2;0;0;0m") == 2  # one per column


async def test_ansi_uncovered_area_has_explicit_black_background() -> None:
    """With ansi=True, positions not covered by any element still show black background."""

    @component
    def root() -> Div:
        return Div(style=size(1, 1), children=[Text(content="X")])

    capture = io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(2, 1),
        autopilot=[PrintPaint(stream=capture, ansi=True), Quit()],
    )
    output = capture.getvalue()
    # Both the "X" cell and the blank cell to its right should set a background
    assert output.count("\x1b[48;2;0;0;0m") == 2


async def test_ansi_after_resize_new_area_has_explicit_black_background() -> None:
    """After resize to a larger terminal, the new uncovered cells have explicit black background."""

    @component
    def root() -> Div:
        return Div()

    c1, c2 = io.StringIO(), io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(1, 1),
        autopilot=[
            PrintPaint(stream=c1, ansi=True),
            TerminalResized(dimensions=(2, 1)),
            PrintPaint(stream=c2, ansi=True),
            Quit(),
        ],
    )
    # Before: 1 column, 1 black background code
    assert c1.getvalue().count("\x1b[48;2;0;0;0m") == 1
    # After: 2 columns, both should have explicit black background
    assert c2.getvalue().count("\x1b[48;2;0;0;0m") == 2


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


async def test_resize_to_larger_new_area_is_spaces() -> None:
    """After growing the terminal, the new rows/columns show as spaces."""

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
            TerminalResized(dimensions=(5, 3)),
            PrintPaint(stream=c2, ansi=False),
            Quit(),
        ],
    )
    assert c1.getvalue().rstrip("\n") == "Hi   "
    assert c2.getvalue().rstrip("\n") == "\n".join(["Hi   ", "     ", "     "])


async def test_resize_to_smaller_no_stale_rows() -> None:
    """After shrinking the terminal, rows outside the new bounds are gone."""

    @component
    def root() -> Div:
        return Div(
            style=col | size(5, 3),
            children=[Text(content="L1"), Text(content="L2"), Text(content="L3")],
        )

    c1, c2 = io.StringIO(), io.StringIO()
    await app(
        root,
        headless=True,
        dimensions=(5, 3),
        autopilot=[
            PrintPaint(stream=c1, ansi=False),
            TerminalResized(dimensions=(5, 1)),
            PrintPaint(stream=c2, ansi=False),
            Quit(),
        ],
    )
    assert c1.getvalue().rstrip("\n") == "\n".join(["L1   ", "L2   ", "L3   "])
    assert c2.getvalue().rstrip("\n") == "L1   "


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
