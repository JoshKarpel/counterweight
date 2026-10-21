"""
Performance: Skipping unchanged rows

A process table of memo rows, so moving the selection re-runs only the two rows it moves between.
"""

import asyncio
from dataclasses import dataclass

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import on_click
from counterweight.hooks import Setter
from counterweight.hooks import use_focus
from counterweight.hooks import use_memo
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

# --8<-- [start:example]


@dataclass(frozen=True, slots=True)
class Process:
    pid: int
    name: str
    cpu: float


@component(memo=True)
def process_row(process: Process, is_selected: bool, select: Setter[int]) -> Text:
    return Text(
        content=f"{process.pid:>6}  {process.name:<10} {process.cpu:>5.1f}%",
        style=text_bg("slate", 700) if is_selected else text_color("slate", 300),
        on_input=on_click(lambda: select(process.pid)),
    )


@component
def process_table(processes: tuple[Process, ...]) -> Div:
    use_focus(auto_focus=True)
    by_cpu = use_memo(lambda: sorted(processes, key=lambda process: process.cpu, reverse=True), deps=(processes,))
    selected_pid, set_selected_pid = use_state(by_cpu[0].pid)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        pids = [process.pid for process in by_cpu]
        index = pids.index(selected_pid) if selected_pid in pids else 0
        match event:
            case KeyPressed(key=Key.Up):
                set_selected_pid(pids[max(index - 1, 0)])
                return ()
            case KeyPressed(key=Key.Down):
                set_selected_pid(pids[min(index + 1, len(pids) - 1)])
                return ()
            case _:
                return None

    return Div(
        style=col,
        on_input=on_input,
        children=tuple(
            process_row(process, process.pid == selected_pid, set_selected_pid).with_key(str(process.pid))
            for process in by_cpu
        ),
    )


# --8<-- [end:example]

PROCESSES = (
    Process(pid=412, name="postgres", cpu=3.1),
    Process(pid=977, name="python", cpu=41.7),
    Process(pid=1203, name="nginx", cpu=0.4),
    Process(pid=2048, name="node", cpu=12.9),
    Process(pid=3311, name="redis", cpu=1.8),
)


@component
def root() -> Div:
    return Div(style=pad(1), children=(process_table(PROCESSES),))


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("performance-process-table", root(), (32, 7), steps=(KeyPressed(key=Key.Down),))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
