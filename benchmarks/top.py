"""
Many small changing numbers: an htop-style process monitor, with per-core meters and a sorted process table.

Every number changes every frame and the table re-sorts, so hundreds of short `Text`s
are re-measured, laid out and painted each frame in a grid-and-rows layout.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from functools import partial

from benchmarks.harness import Workload
from counterweight.components import Component
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles._styles import CellStyle
from counterweight.styles._styles import Style
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_400
from counterweight.styles.utilities import display_grid
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import fr
from counterweight.styles.utilities import gap_width
from counterweight.styles.utilities import green_500
from counterweight.styles.utilities import grid_template_columns
from counterweight.styles.utilities import length
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import red_500
from counterweight.styles.utilities import row
from counterweight.styles.utilities import slate_100
from counterweight.styles.utilities import slate_500
from counterweight.styles.utilities import slate_950
from counterweight.styles.utilities import text_bg
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_justify_right

CORES = 16
PROCESSES = 120
VISIBLE_PROCESSES = 38
METER_WIDTH = 50
MEMORY_KIB = 64 * 1024 * 1024
SWAP_KIB = 8 * 1024 * 1024

USERS = ("root", "postgres", "www-data", "josh", "redis", "systemd+")
COMMANDS = (
    "/usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main",
    "postgres: checkpointer",
    "postgres: walwriter",
    "nginx: worker process",
    "/usr/bin/redis-server 127.0.0.1:6379",
    "python -m uvicorn app.main:app --workers 4",
    "/usr/lib/systemd/systemd --user",
    "node /usr/local/bin/vite --host 0.0.0.0",
    "cargo build --release --target x86_64-unknown-linux-gnu",
    "/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock",
    "sshd: josh@pts/3",
    "zsh -l",
    "htop",
    "rust-analyzer",
    "/opt/google/chrome/chrome --type=renderer --enable-features=WebUIDarkMode",
)

COLUMNS: tuple[tuple[str, int], ...] = (
    ("PID", 8),
    ("USER", 10),
    ("PRI", 4),
    ("NI", 4),
    ("VIRT", 8),
    ("RES", 8),
    ("SHR", 8),
    ("S", 2),
    ("CPU%", 6),
    ("MEM%", 6),
    ("TIME+", 10),
)


@dataclass(frozen=True, slots=True)
class Process:
    pid: int
    user: str
    priority: int
    nice: int
    virtual_kib: int
    resident_kib: int
    shared_kib: int
    state: str
    cpu: float
    centiseconds: int
    command: str

    @property
    def memory(self) -> float:
        return 100 * self.resident_kib / MEMORY_KIB


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    cores: tuple[float, ...]
    memory_kib: int
    swap_kib: int
    processes: tuple[Process, ...]


def initial() -> Model:
    rng = random.Random(0)
    return Model(
        tick=0,
        cores=tuple(rng.random() for _ in range(CORES)),
        memory_kib=MEMORY_KIB // 3,
        swap_kib=SWAP_KIB // 10,
        processes=tuple(
            Process(
                pid=rng.randrange(1, 400_000),
                user=rng.choice(USERS),
                priority=20,
                nice=rng.choice((0, 0, 0, -5, 5, 19)),
                virtual_kib=rng.randrange(10_000, 40_000_000),
                resident_kib=rng.randrange(1_000, 4_000_000),
                shared_kib=rng.randrange(500, 200_000),
                state="S",
                cpu=rng.random() * 30,
                centiseconds=rng.randrange(0, 10_000_000),
                command=rng.choice(COMMANDS),
            )
            for _ in range(PROCESSES)
        ),
    )


def step(model: Model) -> Model:
    rng = random.Random(model.tick)
    return Model(
        tick=model.tick + 1,
        cores=tuple(clamp_fraction(core + rng.uniform(-0.1, 0.1)) for core in model.cores),
        memory_kib=max(0, min(MEMORY_KIB, model.memory_kib + rng.randrange(-50_000, 50_000))),
        swap_kib=max(0, min(SWAP_KIB, model.swap_kib + rng.randrange(-1_000, 1_000))),
        processes=tuple(step_process(process, rng) for process in model.processes),
    )


def step_process(process: Process, rng: random.Random) -> Process:
    cpu = max(0.0, min(100.0, process.cpu + rng.uniform(-3, 3)))
    return replace(
        process,
        cpu=cpu,
        resident_kib=max(1_000, process.resident_kib + rng.randrange(-2_000, 2_000)),
        state="R" if cpu > 20 else "S",
        centiseconds=process.centiseconds + round(cpu),
    )


def clamp_fraction(value: float) -> float:
    return max(0.0, min(1.0, value))


def view(model: Model, row_component: Callable[[Process, bool], Component]) -> Div:
    busiest = sorted(model.processes, key=lambda p: p.cpu, reverse=True)[:VISIBLE_PROCESSES]
    selected = model.tick % VISIBLE_PROCESSES
    return Div(
        style=col,
        children=(
            Div(
                style=row | pad_x(1),
                children=(
                    Div(
                        style=fill(2) | display_grid | grid_template_columns(fr(1), fr(1)) | gap_width(2),
                        children=(
                            *(meter(f"{index:>3}", fraction) for index, fraction in enumerate(model.cores)),
                            meter("Mem", model.memory_kib / MEMORY_KIB),
                            meter("Swp", model.swap_kib / SWAP_KIB),
                        ),
                    ),
                    summary(model),
                ),
            ),
            table_header(),
            Div(
                style=fill(1) | col,
                children=tuple(row_component(process, index == selected) for index, process in enumerate(busiest)),
            ),
            footer(),
        ),
    )


@component
def meter(label: str, fraction: float) -> Text:
    filled = round(fraction * METER_WIDTH)
    low = min(filled, METER_WIDTH * 2 // 3)
    return Text(
        content=(
            Chunk(content=label, style=CellStyle(foreground=cyan_400)),
            Chunk(content="[", style=CellStyle(bold=True)),
            Chunk(content="|" * low, style=CellStyle(foreground=green_500)),
            Chunk(content="|" * (filled - low), style=CellStyle(foreground=red_500)),
            Chunk(content=" " * (METER_WIDTH - filled)),
            Chunk(content=f"{fraction:6.1%}", style=CellStyle(foreground=slate_500)),
            Chunk(content="]", style=CellStyle(bold=True)),
        )
    )


@component
def summary(model: Model) -> Text:
    running = sum(1 for process in model.processes if process.state == "R")
    load = sum(model.cores)
    return Text(
        style=fill(1),
        content=(
            Chunk(content="Tasks: ", style=CellStyle(foreground=cyan_400)),
            Chunk(content=f"{len(model.processes)}, {running} running", style=CellStyle(bold=True)),
            Chunk.newline(),
            Chunk(content="Load average: ", style=CellStyle(foreground=cyan_400)),
            Chunk(content=f"{load:.2f} {load * 0.9:.2f} {load * 0.8:.2f}", style=CellStyle(bold=True)),
            Chunk.newline(),
            Chunk(content="Uptime: ", style=CellStyle(foreground=cyan_400)),
            Chunk(content=f"{model.tick // 3600:02}:{model.tick // 60 % 60:02}:{model.tick % 60:02}"),
        ),
    )


@component
def table_header() -> Div:
    header_style = text_bg("green", 600) | Style(text_style=CellStyle(foreground=slate_950, bold=True))
    return Div(
        style=row,
        children=(
            *(Text(content=name, style=length(width) | header_style | text_justify_right) for name, width in COLUMNS),
            Text(content=" Command", style=fill(1) | header_style),
        ),
    )


def render_process_row(process: Process, selected: bool) -> Div:
    background = text_bg("cyan", 800) if selected else Style()
    hours, rest = divmod(process.centiseconds, 360_000)
    minutes, rest = divmod(rest, 6_000)
    cells = (
        str(process.pid),
        process.user,
        str(process.priority),
        str(process.nice),
        kib(process.virtual_kib),
        kib(process.resident_kib),
        kib(process.shared_kib),
        process.state,
        f"{process.cpu:.1f}",
        f"{process.memory:.1f}",
        f"{hours}:{minutes:02}.{rest // 100:02}",
    )
    return Div(
        style=row,
        children=(
            *(
                Text(content=cell, style=length(width) | text_justify_right | cell_color(name) | background)
                for cell, (name, width) in zip(cells, COLUMNS, strict=True)
            ),
            Text(content=f" {process.command}", style=fill(1) | background),
        ),
    )


process_row = component(render_process_row)
memo_process_row = component(memo=True)(render_process_row)


def cell_color(column: str) -> Style:
    match column:
        case "CPU%" | "MEM%":
            return text_color("cyan", 300)
        case "USER":
            return text_color("amber", 300)
        case _:
            return Style(text_style=CellStyle(foreground=slate_100))


def kib(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.1f}G"
    if value >= 10 * 1024:
        return f"{value // 1024}M"
    return str(value)


@component
def footer() -> Text:
    keys = ("Help", "Setup", "Search", "Filter", "Tree", "SortBy", "Nice -", "Nice +", "Kill", "Quit")
    content: list[Chunk] = []
    for number, name in enumerate(keys, start=1):
        content.append(Chunk(content=f"F{number}", style=CellStyle(foreground=slate_100)))
        content.append(Chunk(content=f"{name:<6}", style=CellStyle(foreground=slate_950, background=cyan_400)))
    return Text(content=tuple(content))


WORKLOAD = Workload(
    name="top",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=partial(view, row_component=process_row),
    dimensions=(160, 50),
)

MEMO_WORKLOAD = replace(
    WORKLOAD,
    name="top-memo",
    description="""
`top`, with each process row a `memo` component.

The rows are unkeyed and the table re-sorts every frame, so a row is reused only when the process at its index
and whether it's selected are both unchanged, which a re-sort usually prevents:
this measures what comparing arguments costs when memo mostly misses.
""",
    view=partial(view, row_component=memo_process_row),
)
