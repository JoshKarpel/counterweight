from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import KeyPressed
from counterweight.styles import Span, Style


async def test_on_key() -> None:
    recorder = []

    @component
    def root() -> Div:
        return Div(
            on_key=lambda event: recorder.append(event),
            style=Style(span=Span(width=10, height=10)),
        )

    await app(
        root,
        headless=True,
        autopilot=(
            KeyPressed(key="f"),
            Quit(),
        ),
    )

    assert recorder == [
        KeyPressed(key="f"),
    ]
