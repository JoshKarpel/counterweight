from asyncio import Queue
from typing import TYPE_CHECKING

from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import Setter
from counterweight.hooks import toggle
from counterweight.hooks import use_state
from counterweight.hooks.impls import MountStatus
from counterweight.hooks.impls import NodeKey
from counterweight.hooks.impls import UseState


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
    queue: Queue[AnyEvent] = Queue()
    setter = UseState(value=1, mount_status=MountStatus(is_mounted=True), node_key=NodeKey(7), queue=queue).setter

    setter(2)

    assert queue.empty()


def test_toggles_set_before_a_render_each_flip_the_latest_value() -> None:
    state = UseState(value=False, mount_status=MountStatus(is_mounted=True), node_key=NodeKey(7), queue=Queue())

    for _ in range(3):
        state.setter(toggle)

    assert state.value is True


if TYPE_CHECKING:

    def toggles(set_open: Setter[bool], set_count: Setter[int]) -> None:
        set_open(toggle)
        set_count(toggle)  # type: ignore[arg-type]
