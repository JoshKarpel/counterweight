import asyncio
from collections import deque
from dataclasses import dataclass
from time import time
from typing import Any

import psutil
import waxy

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Chunk, Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import Ref, use_effect, use_rects, use_ref, use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import (
    align_children_center,
    align_children_stretch,
    border_color,
    border_light,
    col,
    default,
    display_grid,
    full,
    full_width,
    grid_template_rows,
    grow,
    justify_children_center,
    min_width,
    pad_x,
    row,
    text_bg,
    text_color,
    width,
)

_SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"
_HISTORY_LEN = 60

_text_bold = Style(text_style=CellStyle(bold=True))


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    status: str
    command: str


@dataclass(frozen=True)
class SystemStats:
    cpu_percents: tuple[float, ...]
    mem_total_gb: float
    mem_used_gb: float
    mem_percent: float
    load_avg: tuple[float, float, float]
    uptime_seconds: float
    num_processes: int


def _usage_color(pct: float) -> tuple[str, int]:
    if pct < 25:
        return "green", 400
    elif pct < 50:
        return "yellow", 400
    elif pct < 75:
        return "orange", 400
    else:
        return "red", 400


def collect_stats() -> tuple[SystemStats, tuple[ProcessInfo, ...]]:
    cpu_percents = tuple(psutil.cpu_percent(percpu=True))
    mem = psutil.virtual_memory()
    load = psutil.getloadavg()
    boot_time = psutil.boot_time()

    procs: list[ProcessInfo] = []
    for proc in psutil.process_iter(["pid", "username", "cpu_percent", "memory_percent", "status", "name", "cmdline"]):
        try:
            info = proc.info
            cmdline = info.get("cmdline") or []
            command = " ".join(cmdline) if cmdline else (info.get("name") or "")
            procs.append(
                ProcessInfo(
                    pid=info["pid"] or 0,
                    user=(info.get("username") or "")[:12],
                    cpu_percent=info.get("cpu_percent") or 0.0,
                    mem_percent=info.get("memory_percent") or 0.0,
                    status=info.get("status") or "",
                    command=command,
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    stats = SystemStats(
        cpu_percents=cpu_percents,
        mem_total_gb=mem.total / 1024**3,
        mem_used_gb=mem.used / 1024**3,
        mem_percent=mem.percent,
        load_avg=(load[0], load[1], load[2]),
        uptime_seconds=time() - boot_time,
        num_processes=len(procs),
    )
    return stats, tuple(procs)


def _sparkline_chunks(history: deque[float]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for val in history:
        idx = min(int(val / 100 * len(_SPARKLINE_CHARS)), len(_SPARKLINE_CHARS) - 1)
        char = _SPARKLINE_CHARS[idx]
        color, shade = _usage_color(val)
        chunks.append(Chunk(content=char, style=CellStyle(foreground=text_color(color, shade).text_style.foreground)))
    return chunks


SORT_COLS = ["PID", "USER", "CPU%", "MEM%", "STATUS", "COMMAND"]
_COL_WIDTHS = [7, 13, 6, 6, 9, 0]  # 0 = grow


@component
def root() -> Div:
    _no_data: tuple[SystemStats, tuple[ProcessInfo, ...]] | None = None
    data, set_data = use_state(_no_data)
    sort_col, set_sort_col = use_state(2)  # default CPU%
    sort_asc, set_sort_asc = use_state(False)
    selected, set_selected = use_state(0)
    filter_text, set_filter_text = use_state("")
    filter_active, set_filter_active = use_state(False)

    # Per-core CPU history ring buffers
    cpu_history: Ref[dict[int, deque[float]]] = use_ref(dict)

    async def poll() -> None:
        while True:
            stats, procs = collect_stats()
            history = cpu_history.current
            for i, pct in enumerate(stats.cpu_percents):
                if i not in history:
                    history[i] = deque([0.0] * _HISTORY_LEN, maxlen=_HISTORY_LEN)
                history[i].append(pct)
            set_data((stats, procs))
            await asyncio.sleep(1.5)

    use_effect(poll, deps=())

    def on_key(event: KeyPressed) -> Quit | None:
        match event.key:
            case "q":
                return Quit()
            case "/":
                set_filter_active(True)
            case Key.Escape:
                set_filter_text("")
                set_filter_active(False)
                set_selected(0)
            case Key.Down | "j":
                set_selected(lambda s: s + 1)
            case Key.Up | "k":
                set_selected(lambda s: max(0, s - 1))
            case Key.ControlD:
                set_selected(lambda s: s + 10)
            case Key.ControlU:
                set_selected(lambda s: max(0, s - 10))
            case "1" | "2" | "3" | "4" | "5" | "6" as k:
                col = int(k) - 1
                if col == sort_col:
                    set_sort_asc(not sort_asc)
                else:
                    set_sort_col(col)
                    set_sort_asc(False)
                set_selected(0)
            case _ if filter_active and len(event.key) == 1 and event.key.isprintable():
                set_filter_text(lambda t: t + event.key)
            case Key.Backspace if filter_active:
                set_filter_text(lambda t: t[:-1])
        return None

    if data is None:
        return Div(
            style=full | col | align_children_center | justify_children_center,
            on_key=on_key,
            children=[Text(content="Collecting data…", style=text_color("slate", 400))],
        )

    stats, procs = data

    return Div(
        style=display_grid
        | grid_template_rows(waxy.Length(5), waxy.Fraction(1), waxy.Length(1))
        | full
        | align_children_stretch,
        on_key=on_key,
        children=[
            system_overview(stats=stats, cpu_history=cpu_history.current),
            process_section(
                procs=procs,
                sort_col=sort_col,
                sort_asc=sort_asc,
                selected=selected,
                set_selected=set_selected,
                filter_text=filter_text,
                filter_active=filter_active,
            ),
            status_bar(filter_active=filter_active, filter_text=filter_text),
        ],
    )


@component
def system_overview(stats: SystemStats, cpu_history: dict[int, deque[float]]) -> Div:
    return Div(
        style=row | align_children_stretch | border_light | border_color("slate", 700),
        children=[
            cpu_panel(cpu_history=cpu_history, cpu_percents=stats.cpu_percents),
            memory_panel(
                used_gb=stats.mem_used_gb,
                total_gb=stats.mem_total_gb,
                mem_percent=stats.mem_percent,
            ),
            system_info_panel(stats=stats),
        ],
    )


@component
def cpu_panel(cpu_history: dict[int, deque[float]], cpu_percents: tuple[float, ...]) -> Div:
    rows: list[Text] = []
    for i, pct in enumerate(cpu_percents):
        hist = cpu_history.get(i, deque([0.0] * _HISTORY_LEN, maxlen=_HISTORY_LEN))
        color, shade = _usage_color(pct)
        label = Chunk(content=f"CPU{i:<2} ", style=CellStyle(foreground=text_color("slate", 400).text_style.foreground))
        pct_chunk = Chunk(
            content=f"{pct:5.1f}% ", style=CellStyle(foreground=text_color(color, shade).text_style.foreground)
        )
        rows.append(
            Text(
                content=[label, pct_chunk, *_sparkline_chunks(hist)],
                style=grow(1) | min_width(0),
            )
        )

    return Div(
        style=col | grow(1) | min_width(0) | align_children_stretch | pad_x(1),
        children=rows,
    )


@component
def memory_panel(used_gb: float, total_gb: float, mem_percent: float) -> Div:
    bar_width = 30
    filled = int(mem_percent / 100 * bar_width)
    empty = bar_width - filled
    color, shade = _usage_color(mem_percent)
    bar_chunks = [
        Chunk(content="█" * filled, style=CellStyle(foreground=text_color(color, shade).text_style.foreground)),
        Chunk(content="░" * empty, style=CellStyle(foreground=text_color("slate", 600).text_style.foreground)),
    ]

    return Div(
        style=col | grow(1) | min_width(0) | pad_x(1) | justify_children_center,
        children=[
            Text(
                content=[
                    Chunk(content="MEM ", style=CellStyle(foreground=text_color("slate", 400).text_style.foreground)),
                    *bar_chunks,
                ],
            ),
            Text(
                content=f"    {used_gb:.1f} GB / {total_gb:.1f} GB ({mem_percent:.1f}%)",
                style=text_color("slate", 400),
            ),
        ],
    )


@component
def system_info_panel(stats: SystemStats) -> Div:
    h = int(stats.uptime_seconds) // 3600
    m = (int(stats.uptime_seconds) % 3600) // 60
    s = int(stats.uptime_seconds) % 60

    return Div(
        style=col | grow(1) | min_width(0) | pad_x(1) | justify_children_center,
        children=[
            Text(
                content=f"Uptime:   {h:02d}:{m:02d}:{s:02d}",
                style=text_color("slate", 300),
            ),
            Text(
                content=f"Load:     {stats.load_avg[0]:.2f}  {stats.load_avg[1]:.2f}  {stats.load_avg[2]:.2f}",
                style=text_color("slate", 300),
            ),
            Text(
                content=f"Procs:    {stats.num_processes}",
                style=text_color("slate", 300),
            ),
        ],
    )


@component
def process_section(
    procs: tuple[ProcessInfo, ...],
    sort_col: int,
    sort_asc: bool,
    selected: int,
    set_selected: object,
    filter_text: str,
    filter_active: bool,
) -> Div:
    # Filter
    ft = filter_text.lower()
    visible = [p for p in procs if ft in p.command.lower()] if ft else list(procs)

    # Sort
    def sort_key(p: ProcessInfo) -> Any:
        match sort_col:
            case 0:
                return p.pid
            case 1:
                return p.user
            case 2:
                return p.cpu_percent
            case 3:
                return p.mem_percent
            case 4:
                return p.status
            case _:
                return p.command

    visible.sort(key=sort_key, reverse=not sort_asc)
    num_visible = len(visible)

    children: list[object] = [
        process_header(sort_col=sort_col, sort_asc=sort_asc),
        process_list(procs=tuple(visible), selected=selected, num_procs=num_visible),
    ]
    if filter_active:
        children = [filter_bar(filter_text=filter_text), *children]

    return Div(
        style=col | grow(1) | align_children_stretch,
        children=children,  # type: ignore[arg-type]
    )


@component
def filter_bar(filter_text: str) -> Text:
    return Text(
        content=f"Filter: {filter_text}▌",
        style=text_color("yellow", 300) | border_light | border_color("yellow", 600) | pad_x(1),
    )


@component
def process_header(sort_col: int, sort_asc: bool) -> Div:
    indicator = "↑" if sort_asc else "↓"
    cols = []
    for i, (label, w) in enumerate(zip(SORT_COLS, _COL_WIDTHS)):
        suffix = f" {indicator}" if i == sort_col else "  "
        cell_style = text_color("amber", 300) | _text_bold
        if w > 0:
            cols.append(Text(content=f"{label}{suffix}", style=cell_style | width(w) | pad_x(1)))
        else:
            cols.append(Text(content=f"{label}{suffix}", style=cell_style | grow(1) | min_width(0) | pad_x(1)))
    return Div(
        style=row | align_children_stretch | border_color("slate", 700) | border_light,
        children=cols,
    )


@component
def process_list(procs: tuple[ProcessInfo, ...], selected: int, num_procs: int) -> Div:
    rects = use_rects()
    visible_height = max(1, int(rects.content.height))

    clamped = min(selected, max(0, num_procs - 1))
    half = visible_height // 2
    start = max(0, min(clamped - half, num_procs - visible_height))
    end = min(start + visible_height, num_procs)

    rows = [process_row(proc=procs[i], is_selected=(i == clamped)) for i in range(start, end)]

    return Div(
        style=col | grow(1) | align_children_stretch,
        children=rows,
    )


@component
def process_row(proc: ProcessInfo, is_selected: bool) -> Div:
    cpu_color, cpu_shade = _usage_color(proc.cpu_percent)
    mem_color, mem_shade = _usage_color(proc.mem_percent)

    base_style = text_bg("blue", 900) if is_selected else default

    pid_cell = Text(
        content=str(proc.pid), style=base_style | width(_COL_WIDTHS[0]) | pad_x(1) | text_color("slate", 300)
    )
    user_cell = Text(
        content=proc.user[:12], style=base_style | width(_COL_WIDTHS[1]) | pad_x(1) | text_color("cyan", 300)
    )
    cpu_cell = Text(
        content=f"{proc.cpu_percent:5.1f}%",
        style=base_style | width(_COL_WIDTHS[2]) | pad_x(1) | text_color(cpu_color, cpu_shade),
    )
    mem_cell = Text(
        content=f"{proc.mem_percent:5.1f}%",
        style=base_style | width(_COL_WIDTHS[3]) | pad_x(1) | text_color(mem_color, mem_shade),
    )
    status_cell = Text(
        content=proc.status,
        style=base_style | width(_COL_WIDTHS[4]) | pad_x(1) | text_color("slate", 400),
    )
    cmd_cell = Text(
        content=proc.command,
        style=base_style | grow(1) | min_width(0) | pad_x(1) | text_color("slate", 200),
    )

    return Div(
        style=row | align_children_stretch,
        children=[pid_cell, user_cell, cpu_cell, mem_cell, status_cell, cmd_cell],
    )


@component
def status_bar(filter_active: bool, filter_text: str) -> Text:
    def kv(key: str, action: str) -> list[Chunk]:
        return [
            Chunk(
                content=f" {key} ",
                style=CellStyle(
                    foreground=text_color("slate", 950).text_style.foreground,
                    background=text_color("slate", 400).text_style.foreground,
                ),
            ),
            Chunk(content=f" {action} ", style=CellStyle(foreground=text_color("slate", 300).text_style.foreground)),
        ]

    chunks = [
        *kv("q", "quit"),
        *kv("/", "filter"),
        *kv("esc", "clear filter"),
        *kv("j/k", "navigate"),
        *kv("^D/^U", "page"),
        *kv("1-6", "sort"),
    ]

    return Text(
        content=chunks,
        style=text_bg("slate", 800) | full_width,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
