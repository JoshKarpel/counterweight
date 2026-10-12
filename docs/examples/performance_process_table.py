from dataclasses import dataclass

from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed, MouseEvent, MouseUp
from counterweight.hooks import Setter, use_memo, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@dataclass(frozen=True, slots=True)
class Process:
    pid: int
    name: str
    cpu: float


@component(memo=True)
def process_row(process: Process, is_selected: bool, select: Setter[int]) -> Text:
    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseUp(button=1):
                select(process.pid)

    return Text(
        content=f"{process.pid:>6}  {process.name:<10} {process.cpu:>5.1f}%",
        style=text_bg("slate", 700) if is_selected else text_color("slate", 300),
        on_mouse=on_mouse,
    )


@component
def process_table(processes: tuple[Process, ...]) -> Div:
    by_cpu = use_memo(lambda: sorted(processes, key=lambda process: process.cpu, reverse=True), deps=(processes,))
    selected_pid, set_selected_pid = use_state(by_cpu[0].pid)

    def on_key(event: KeyPressed) -> None:
        pids = [process.pid for process in by_cpu]
        index = pids.index(selected_pid) if selected_pid in pids else 0
        match event.key:
            case Key.Up:
                set_selected_pid(pids[max(index - 1, 0)])
            case Key.Down:
                set_selected_pid(pids[min(index + 1, len(pids) - 1)])

    return Div(
        style=col,
        on_key=on_key,
        children=[
            process_row(process, process.pid == selected_pid, set_selected_pid).with_key(str(process.pid))
            for process in by_cpu
        ],
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
    return Div(style=pad(1), children=[process_table(PROCESSES)])


SCREENSHOTS = [ScreenshotSpec(root(), "performance-process-table", (32, 7), events=(KeyPressed(key=Key.Down),))]
