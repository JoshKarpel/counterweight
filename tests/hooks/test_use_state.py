from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import KeyPressed
from counterweight.hooks import Setter, use_state


async def test_use_state() -> None:
    recorder = []

    def track_state_changes() -> tuple[int, Setter[int]]:
        state, set_state = use_state(0)
        recorder.append(state)
        return state, set_state

    @component
    def root() -> Div:
        state, set_state = track_state_changes()

        def on_key(event: KeyPressed) -> None:
            set_state(state + 1)

        return Div(on_key=on_key)

    await app(
        root,
        headless=True,
        autopilot=(
            KeyPressed(key="f"),
            Quit(),
        ),
    )

    assert recorder == [0, 1]
