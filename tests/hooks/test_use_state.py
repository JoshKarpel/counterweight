from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.hooks import Setter, use_state
from counterweight.hooks.impls import MountStatus, NodeKey, UseState
from tests.rendering import state_sets


async def test_use_state() -> None:
    recorder = []

    def track_state_changes() -> tuple[int, Setter[int]]:
        state, set_state = use_state(0)
        recorder.append(state)
        return state, set_state

    @component
    def root() -> Div:
        state, set_state = track_state_changes()

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_state(state + 1)

        return Div(on_input=on_input)

    await app(
        root(),
        headless=True,
        autopilot=(
            KeyPressed(key="f"),
            Quit(),
        ),
    )

    assert recorder == [0, 0, 1]


def test_a_setter_outliving_its_state_does_nothing() -> None:
    with state_sets() as queue:
        setter = UseState(value=1, mount_status=MountStatus(is_mounted=True), node_key=NodeKey(7)).setter

        setter(2)

    assert queue.empty()
