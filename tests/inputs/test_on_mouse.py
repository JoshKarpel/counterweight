from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import MouseDown, MouseEvent, MouseMoved, MouseUp
from counterweight.geometry import Position
from counterweight.styles import Border, BorderKind, Span, Style


async def test_on_mouse_only_captures_events_in_border_rect_with_history() -> None:
    recorder = []

    @component
    def root() -> Div:
        return Div(
            on_mouse=lambda event: recorder.append(event),
            style=Style(span=Span(width=1, height=1), border=Border(kind=BorderKind.Light)),
        )

    events: list[tuple[MouseEvent, bool]] = [
        (MouseMoved(absolute=Position(1, 1), button=None), True),  # in content rect
        (MouseMoved(absolute=Position(2, 0), button=None), True),  # on border
        (MouseMoved(absolute=Position(3, 0), button=None), True),  # outside, but included because previous was inside
        (MouseMoved(absolute=Position(3, 0), button=None), False),  # outside border, not included
        (MouseMoved(absolute=Position(1, 0), button=None), True),  # back inside
        (MouseDown(absolute=Position(1, 0), button=1), True),  # back inside
        (MouseMoved(absolute=Position(1, 1), button=1), True),
        (MouseUp(absolute=Position(1, 1), button=1), True),
    ]

    await app(
        root,
        headless=True,
        autopilot=(
            *(event for event, _ in events),
            Quit(),
        ),
    )

    assert recorder == [event for event, tf in events if tf]
