from asyncio import Queue
from typing import TYPE_CHECKING
from typing import assert_type

from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import Editor
from counterweight.hooks import Setter
from counterweight.hooks import get_state
from counterweight.hooks import toggle
from counterweight.hooks import use_state
from counterweight.hooks._impls import MountStatus
from counterweight.hooks._impls import NodeKey
from counterweight.hooks._impls import UseState


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


def state(value: object) -> tuple[UseState, Queue[AnyEvent]]:
    """A mounted `use_state` hook holding `value`, and the queue its renders are requested on."""
    queue: Queue[AnyEvent] = Queue()
    return UseState(value=value, mount_status=MountStatus(is_mounted=True), node_key=NodeKey(7), queue=queue), queue


def test_a_setter_returns_the_value_it_is_given() -> None:
    setter, _ = state(3)

    assert setter(5) == 5


def test_a_setter_returns_what_an_updater_returns() -> None:
    setter, _ = state(3)

    assert setter(lambda value: value * 4) == 12


def test_several_updates_each_return_the_state_the_last_left() -> None:
    setter, queue = state(3)

    assert [setter(lambda value: value + 2) for _ in range(3)] == [5, 7, 9]
    assert queue.qsize() == 3


def test_get_state_reads_an_update_made_since_the_render() -> None:
    setter, _ = state("rendered")
    setter("updated")

    assert get_state(setter) == "updated"


def test_get_state_queues_no_render() -> None:
    setter, queue = state("rendered")

    get_state(setter)

    assert queue.empty()


def test_a_setter_after_unmounting_returns_the_state_at_unmount_and_ignores_updates() -> None:
    mount_status = MountStatus(is_mounted=True)
    queue: Queue[AnyEvent] = Queue()
    setter = UseState(value=1, mount_status=mount_status, node_key=NodeKey(7), queue=queue)
    setter(2)
    mount_status.is_mounted = False

    assert setter(lambda value: value + 10) == 2
    assert queue.qsize() == 1


def test_toggles_set_before_a_render_each_flip_the_latest_value() -> None:
    setter, _ = state(False)

    for _ in range(3):
        setter(toggle)

    assert setter.value is True


if TYPE_CHECKING:

    def toggles(set_open: Setter[bool], set_count: Setter[int]) -> None:
        set_open(toggle)
        set_count(toggle)  # type: ignore[arg-type]

    def settles(set_count: Setter[int]) -> None:
        assert_type(set_count(3), int)
        assert_type(set_count(lambda count: count + 1), int)
        assert_type(get_state(set_count), int)

    def edits(set_text: Setter[str]) -> Editor[str]:
        return set_text

    def reads_through(set_text: Editor[str]) -> None:
        assert_type(get_state(set_text), str)
