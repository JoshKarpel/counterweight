from asyncio import Queue
from asyncio import TaskGroup
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta
from weakref import WeakSet

from counterweight import app
from counterweight._context_vars import app_scope
from counterweight._context_vars import current_event_queue
from counterweight._context_vars import current_task_group
from counterweight._context_vars import current_use_mouse_listeners
from counterweight._output import Frame
from counterweight.autopilot import WaitFor
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Text
from counterweight.events import AnyEvent
from counterweight.hooks import Mouse
from counterweight.hooks import Setter
from counterweight.hooks import use_state

TIMEOUT = timedelta(seconds=10)


@component
def counter(label: str, setters: list[Setter[int]]) -> Text:
    count, set_count = use_state(0)
    setters.append(set_count)
    return Text(content=f"{label}={count}")


async def run_counter_until(
    shows: str, setters: list[Setter[int]], handler: Callable[[Frame], Awaitable[None]], frames: list[Frame]
) -> None:
    await app(
        counter("outer", setters),
        headless=True,
        dimensions=(12, 1),
        autopilot=(
            Screenshot(handler=handler),
            WaitFor(lambda frame: shows in frame.text(ansi=False), timeout=TIMEOUT),
            Screenshot(handler=frames.append),
            Quit(),
        ),
    )


async def test_a_setter_called_after_an_app_ran_inside_a_handler_still_reaches_its_app() -> None:
    outer_setters: list[Setter[int]] = []
    frames: list[Frame] = []

    async def run_inner_then_count(frame: Frame) -> None:
        await app(counter("inner", []), headless=True, dimensions=(12, 1), autopilot=(Quit(),))
        outer_setters[-1](1)

    await run_counter_until("outer=1", outer_setters, run_inner_then_count, frames)

    assert frames[-1].text(ansi=False).strip() == "outer=1"


async def test_a_setter_called_while_another_app_runs_reaches_its_own_app() -> None:
    outer_setters: list[Setter[int]] = []
    frames: list[Frame] = []

    def count_outer(frame: Frame) -> None:
        outer_setters[-1](2)

    async def run_inner_that_counts_outer(frame: Frame) -> None:
        await app(
            counter("inner", []),
            headless=True,
            dimensions=(12, 1),
            autopilot=(Screenshot(handler=count_outer), Quit()),
        )

    await run_counter_until("outer=2", outer_setters, run_inner_that_counts_outer, frames)

    assert frames[-1].text(ansi=False).strip() == "outer=2"


async def test_an_app_leaves_whatever_its_caller_had_current() -> None:
    queue: Queue[AnyEvent] = Queue()
    listeners: WeakSet[Callable[[Mouse], object]] = WeakSet()

    async with TaskGroup() as task_group:
        with app_scope(queue, task_group, listeners):
            await app(counter("app", []), headless=True, dimensions=(12, 1), autopilot=(Quit(),))
            after = (current_event_queue.get(), current_task_group.get(), current_use_mouse_listeners.get())

    assert all(found is expected for found, expected in zip(after, (queue, task_group, listeners), strict=True))
