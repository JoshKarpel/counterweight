from asyncio import Event
from asyncio import timeout

from counterweight import app
from counterweight._utils import forever
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import ControlSender
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_state


async def test_a_control_sent_from_an_effect_reaches_the_app() -> None:
    @component
    def root() -> Div:
        send_control = use_controls()

        async def quit_on_mount() -> None:
            send_control(Quit())

        use_effect(quit_on_mount, deps=())

        return Div()

    async with timeout(5):
        await app(root(), headless=True)


async def test_every_render_returns_an_equal_sender() -> None:
    senders: list[ControlSender] = []

    @component
    def root() -> Div:
        _, set_count = use_state(0)
        senders.append(use_controls())

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_count(lambda count: count + 1)

        return Div(on_input=on_input)

    await app(root(), headless=True, autopilot=(KeyPressed(key="a"), KeyPressed(key="b"), Quit()))

    assert len(senders) > 1
    assert all(sender == senders[0] for sender in senders)


async def test_a_control_sent_as_a_component_unmounts_reaches_the_app() -> None:
    started = Event()

    @component
    def child() -> Div:
        send_control = use_controls()

        async def quit_on_unmount() -> None:
            started.set()
            try:
                await forever()
            finally:
                send_control(Quit())

        use_effect(quit_on_unmount, deps=())

        return Div()

    @component
    def root() -> Div:
        is_shown, set_shown = use_state(True)

        async def unmount_child() -> None:
            await started.wait()
            set_shown(False)

        use_effect(unmount_child, deps=())

        return Div(children=(child(),) if is_shown else ())

    async with timeout(5):
        await app(root(), headless=True)
