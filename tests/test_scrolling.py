from __future__ import annotations

import io
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import PrintPaint, Quit
from counterweight.elements import Div, Text
from counterweight.events import AnyEvent, KeyPressed, MouseEvent, MouseScrolledDown, MouseScrolledUp
from counterweight.geometry import Position
from counterweight.hooks import ScrollState, use_scroll
from counterweight.styles.utilities import (
    align_children_stretch,
    col,
    full,
    overflow_hidden,
    overflow_y_hidden,
    size,
)


async def _render(root_fn: Callable[[], Component], dimensions: tuple[int, int]) -> str:
    capture = io.StringIO()
    await app(
        root_fn,
        headless=True,
        dimensions=dimensions,
        autopilot=[PrintPaint(stream=capture, ansi=False), Quit()],
    )
    return capture.getvalue().rstrip("\n")


async def _render_after_events(
    root_fn: Callable[[], Component],
    dimensions: tuple[int, int],
    events: list[AnyEvent],
) -> str:
    capture = io.StringIO()
    await app(
        root_fn,
        headless=True,
        dimensions=dimensions,
        autopilot=[*events, PrintPaint(stream=capture, ansi=False), Quit()],
    )
    return capture.getvalue().rstrip("\n")


# ---------------------------------------------------------------------------
# Clipping: overflow_hidden clips content without scrolling
# ---------------------------------------------------------------------------


async def test_overflow_hidden_clips_content() -> None:
    @component
    def root() -> Div:
        return Div(
            style=col | full | align_children_stretch,
            children=[
                Div(
                    style=size(10, 3) | overflow_hidden | col | align_children_stretch,
                    children=[
                        Text(content="AAAAAAAAAA"),
                        Text(content="BBBBBBBBBB"),
                        Text(content="CCCCCCCCCC"),
                        Text(content="DDDDDDDDDD"),  # should be clipped
                        Text(content="EEEEEEEEEE"),  # should be clipped
                    ],
                ),
            ],
        )

    result = await _render(root, (10, 5))
    lines = result.splitlines()
    assert lines[0] == "AAAAAAAAAA"
    assert lines[1] == "BBBBBBBBBB"
    assert lines[2] == "CCCCCCCCCC"
    assert "D" not in result
    assert "E" not in result


async def test_overflow_y_hidden_clips_vertically_only() -> None:
    @component
    def root() -> Div:
        return Div(
            style=size(20, 3) | overflow_y_hidden | col | align_children_stretch,
            children=[
                Text(content="AAAAAAAAAAAAAAAAAAA"),
                Text(content="BBBBBBBBBBBBBBBBBBB"),
                Text(content="CCCCCCCCCCCCCCCCCCC"),
                Text(content="DDDDDDDDDDDDDDDDDDD"),  # clipped vertically
            ],
        )

    result = await _render(root, (20, 5))
    assert "A" in result
    assert "B" in result
    assert "C" in result
    assert "D" not in result


# ---------------------------------------------------------------------------
# use_scroll: basic scroll state and style
# ---------------------------------------------------------------------------


async def test_use_scroll_initial_state_zero_offsets() -> None:
    recorded: list[ScrollState] = []

    @component
    def root() -> Div:
        state, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True)
        recorded.append(state)
        return Div(
            style=size(10, 5) | scroll_style | col | align_children_stretch,
            on_mouse=on_mouse,
            on_key=on_key,
            children=[Text(content="\n".join(str(i) for i in range(20)))],
        )

    await app(root, headless=True, dimensions=(10, 5), autopilot=[Quit()])
    assert recorded[-1].offset_x == 0
    assert recorded[-1].offset_y == 0


# ---------------------------------------------------------------------------
# Scrolling: content clipped to viewport; scroll updates offset
# ---------------------------------------------------------------------------


async def test_scroll_container_clips_children_to_viewport() -> None:
    @component
    def root() -> Div:
        _, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            children=[
                Div(
                    style=size(10, 3) | scroll_style | col | align_children_stretch,
                    on_mouse=on_mouse,
                    on_key=on_key,
                    children=[
                        Text(content="AAAAAAAAAA"),
                        Text(content="BBBBBBBBBB"),
                        Text(content="CCCCCCCCCC"),
                        Text(content="DDDDDDDDDD"),
                        Text(content="EEEEEEEEEE"),
                    ],
                ),
            ],
        )

    result = await _render(root, (10, 5))
    lines = result.splitlines()
    assert lines[0] == "AAAAAAAAAA"
    assert lines[1] == "BBBBBBBBBB"
    assert lines[2] == "CCCCCCCCCC"
    assert "D" not in result
    assert "E" not in result


async def test_mouse_scroll_down_moves_content_up() -> None:
    @component
    def root() -> Div:
        _, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            children=[
                Div(
                    style=size(10, 3) | scroll_style | col | align_children_stretch,
                    on_mouse=on_mouse,
                    on_key=on_key,
                    children=[
                        Text(content="AAAAAAAAAA"),
                        Text(content="BBBBBBBBBB"),
                        Text(content="CCCCCCCCCC"),
                        Text(content="DDDDDDDDDD"),
                        Text(content="EEEEEEEEEE"),
                    ],
                ),
            ],
        )

    result = await _render_after_events(
        root,
        (10, 5),
        [
            MouseScrolledDown(absolute=Position(5, 1)),
            MouseScrolledDown(absolute=Position(5, 1)),
            MouseScrolledDown(absolute=Position(5, 1)),
        ],
    )
    # after 3 scroll-down events (1 row each), A/B/C shift off the top, D/E are visible
    assert "A" not in result
    assert "B" not in result
    assert "C" not in result
    assert "D" in result
    assert "E" in result


async def test_mouse_scroll_up_clamps_at_zero() -> None:
    @component
    def root() -> Div:
        _, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            children=[
                Div(
                    style=size(10, 3) | scroll_style | col | align_children_stretch,
                    on_mouse=on_mouse,
                    on_key=on_key,
                    children=[
                        Text(content="AAAAAAAAAA"),
                        Text(content="BBBBBBBBBB"),
                        Text(content="CCCCCCCCCC"),
                        Text(content="DDDDDDDDDD"),
                        Text(content="EEEEEEEEEE"),
                    ],
                ),
            ],
        )

    result = await _render_after_events(
        root,
        (10, 5),
        [
            MouseScrolledUp(absolute=Position(5, 1)),
            MouseScrolledUp(absolute=Position(5, 1)),
        ],
    )
    # Should still show top content since offset is clamped at 0
    lines = result.splitlines()
    assert lines[0] == "AAAAAAAAAA"


# ---------------------------------------------------------------------------
# Keyboard scrolling
# ---------------------------------------------------------------------------


async def test_arrow_down_scrolls_vertically() -> None:
    @component
    def root() -> Div:
        _, scroll_style, _on_mouse, on_key = use_scroll(scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            on_key=on_key,
            children=[
                Div(
                    style=size(10, 3) | scroll_style | col | align_children_stretch,
                    children=[
                        Text(content="AAAAAAAAAA"),
                        Text(content="BBBBBBBBBB"),
                        Text(content="CCCCCCCCCC"),
                        Text(content="DDDDDDDDDD"),
                        Text(content="EEEEEEEEEE"),
                    ],
                ),
            ],
        )

    result = await _render_after_events(
        root,
        (10, 5),
        [KeyPressed(key="down"), KeyPressed(key="down"), KeyPressed(key="down")],
    )
    assert "A" not in result
    assert "D" in result


async def test_arrow_key_scroll_x_disabled_by_default() -> None:
    @component
    def root() -> Div:
        _, scroll_style, _on_mouse, on_key = use_scroll(scroll_x=False, scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            on_key=on_key,
            children=[
                Div(
                    style=size(5, 5) | scroll_style | col | align_children_stretch,
                    children=[Text(content="AAAA\nBBBB\nCCCC\nDDDD\nEEEE\nFFFF")],
                ),
            ],
        )

    result_before = await _render(root, (10, 5))
    result_after = await _render_after_events(
        root,
        (10, 5),
        [KeyPressed(key="right"), KeyPressed(key="right")],
    )
    # Horizontal scroll keys should be ignored when scroll_x=False
    assert result_before == result_after


# ---------------------------------------------------------------------------
# StopPropagation: scroll doesn't bubble to outer containers
# ---------------------------------------------------------------------------


async def test_stop_propagation_prevents_outer_scroll() -> None:
    outer_events: list[MouseEvent] = []

    @component
    def root() -> Div:
        _, scroll_style, on_mouse, _on_key = use_scroll(scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            on_mouse=outer_events.append,
            children=[
                Div(
                    style=size(10, 3) | scroll_style | col | align_children_stretch,
                    on_mouse=on_mouse,
                    children=[
                        Text(content="AAAAAAAAAA"),
                        Text(content="BBBBBBBBBB"),
                        Text(content="CCCCCCCCCC"),
                        Text(content="DDDDDDDDDD"),
                    ],
                ),
            ],
        )

    await app(
        root,
        headless=True,
        dimensions=(10, 5),
        autopilot=[MouseScrolledDown(absolute=Position(5, 1)), Quit()],
    )
    # The outer element's on_mouse should not have received the scroll event
    scroll_events = [e for e in outer_events if isinstance(e, (MouseScrolledDown, MouseScrolledUp))]
    assert scroll_events == []


# ---------------------------------------------------------------------------
# Nested scroll containers clip to intersection
# ---------------------------------------------------------------------------


async def test_nested_scroll_clips_to_intersection() -> None:
    @component
    def root() -> Div:
        _, outer_style, outer_mouse, _outer_key = use_scroll(scroll_y=True)
        _, inner_style, inner_mouse, _inner_key = use_scroll(scroll_y=True)
        return Div(
            style=col | full | align_children_stretch,
            children=[
                Div(
                    style=size(10, 4) | outer_style | col | align_children_stretch,
                    on_mouse=outer_mouse,
                    children=[
                        Div(
                            style=size(10, 6) | inner_style | col | align_children_stretch,
                            on_mouse=inner_mouse,
                            children=[
                                Text(content="AAAAAAAAAA"),
                                Text(content="BBBBBBBBBB"),
                                Text(content="CCCCCCCCCC"),
                                Text(content="DDDDDDDDDD"),
                                Text(content="EEEEEEEEEE"),
                                Text(content="FFFFFFFFFF"),
                                Text(content="GGGGGGGGGG"),
                                Text(content="HHHHHHHHHH"),
                            ],
                        ),
                    ],
                ),
            ],
        )

    result = await _render(root, (10, 5))
    # Outer viewport is 4 rows, inner content should be clipped to outer
    assert "E" not in result
    assert "F" not in result


# ---------------------------------------------------------------------------
# Horizontal scrolling
# ---------------------------------------------------------------------------


async def test_horizontal_scroll_moves_content_left() -> None:
    @component
    def root() -> Div:
        _, scroll_style, _on_mouse, on_key = use_scroll(scroll_x=True, scroll_y=False)
        return Div(
            style=col | full | align_children_stretch,
            on_key=on_key,
            children=[
                Div(
                    style=size(5, 1) | scroll_style | align_children_stretch,
                    children=[
                        Text(content="ABCDEFGHIJ"),
                    ],
                ),
            ],
        )

    result_initial = await _render(root, (10, 3))
    result_scrolled = await _render_after_events(
        root,
        (10, 3),
        [KeyPressed(key="right"), KeyPressed(key="right"), KeyPressed(key="right")],
    )
    assert "A" in result_initial
    assert "A" not in result_scrolled
    assert "D" in result_scrolled
