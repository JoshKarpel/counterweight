import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any

import psutil

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Chunk, Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import Ref, use_effect, use_rects, use_ref, use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import (
    ColorName,
    Shade,
    align_children_center,
    align_children_stretch,
    border_collapse,
    border_color,
    border_light,
    col,
    default,
    flex_wrap,
    full,
    full_width,
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
_SPARKLINE_DISPLAY = 20  # chars shown per core row

# Each core row: "CPU11 " (6) + "100.1% " (7) + sparkline (20) = 33 content; +2 pad = 35
_CORE_ROW_WIDTH = 35

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


def _usage_color(pct: float) -> tuple[ColorName, Shade]:
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
    )
    return stats, tuple(procs)


def _sparkline_chunks(history: deque[float]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for val in list(history)[-_SPARKLINE_DISPLAY:]:
        idx = min(int(val / 100 * len(_SPARKLINE_CHARS)), len(_SPARKLINE_CHARS) - 1)
        char = _SPARKLINE_CHARS[idx]
        color, shade = _usage_color(val)
        chunks.append(Chunk(content=char, style=CellStyle(foreground=text_color(color, shade).text_style.foreground)))
    return chunks


SORT_COLS = ["PID", "USER", "CPU%", "MEM%", "COMMAND"]
_SORT_INDICATOR_WIDTH = 2  # " ↑" or " ↓"


def _col_widths(procs: tuple[ProcessInfo, ...]) -> list[int]:
    # Compute content width for each fixed column, then add 2 for pad_x(1) (border-box)
    header_content = [len(label) + _SORT_INDICATOR_WIDTH for label in SORT_COLS[:-1]]
    if procs:
        data_content = [
            max(len(str(p.pid)) for p in procs),
            max(len(p.user) for p in procs),
            max(len(f"{p.cpu_percent:.1f}%") for p in procs),
            max(len(f"{p.mem_percent:.2f}%") for p in procs),
        ]
        content = [max(h, d) for h, d in zip(header_content, data_content)]
    else:
        content = header_content
    return [c + 2 for c in content] + [0]  # 0 = grow for COMMAND


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
            case "1" | "2" | "3" | "4" | "5" as k:
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

    def _loading(style: Style) -> Div:
        return Div(
            style=style | align_children_center | justify_children_center,
            children=[Text(content="Loading…", style=text_color("slate", 500))],
        )

    if data is None:
        return Div(
            style=col | full | align_children_stretch | border_collapse,
            on_key=on_key,
            children=[
                Div(
                    style=col | align_children_stretch | border_collapse,
                    children=[
                        _loading(col | grow(1) | border_light | border_color("slate", 700)),
                        _loading(col | border_light | border_color("slate", 700)),
                    ],
                ),
                _loading(col | grow(1) | align_children_stretch | border_light | border_color("slate", 700)),
                status_bar(filter_active=filter_active, filter_text=filter_text),
            ],
        )

    stats, procs = data

    return Div(
        style=col | full | align_children_stretch | border_collapse,
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
        style=col | align_children_stretch | border_collapse,
        children=[
            cpu_panel(cpu_history=cpu_history, cpu_percents=stats.cpu_percents),
            memory_panel(
                used_gb=stats.mem_used_gb,
                total_gb=stats.mem_total_gb,
                mem_percent=stats.mem_percent,
            ),
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
                style=width(_CORE_ROW_WIDTH) | pad_x(1),
            )
        )

    return Div(
        style=row | flex_wrap | grow(1) | min_width(0) | border_light | border_color("slate", 700),
        children=rows,
    )


@component
def memory_panel(used_gb: float, total_gb: float, mem_percent: float) -> Text:
    rects = use_rects()
    prefix = "MEM "
    label = f"  {used_gb:.2f}/{total_gb:.2f} GB ({mem_percent:.2f}%)"
    bar_width = max(0, int(rects.content.width) - len(prefix) - len(label))
    filled = int(mem_percent / 100 * bar_width)
    empty = bar_width - filled
    color, shade = _usage_color(mem_percent)
    chunks = [
        Chunk(content=prefix, style=CellStyle(foreground=text_color("slate", 400).text_style.foreground)),
        Chunk(content="█" * filled, style=CellStyle(foreground=text_color(color, shade).text_style.foreground)),
        Chunk(content="░" * empty, style=CellStyle(foreground=text_color("slate", 600).text_style.foreground)),
        Chunk(content=label, style=CellStyle(foreground=text_color("slate", 400).text_style.foreground)),
    ]
    return Text(content=chunks, style=pad_x(1) | border_light | border_color("slate", 700))


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
            case _:
                return p.command

    visible.sort(key=sort_key, reverse=not sort_asc)
    num_visible = len(visible)

    widths = _col_widths(tuple(visible))

    table = Div(
        style=col | grow(1) | align_children_stretch | border_light | border_color("slate", 700),
        children=[
            process_header(sort_col=sort_col, sort_asc=sort_asc, col_widths=widths),
            process_list(procs=tuple(visible), selected=selected, num_procs=num_visible, col_widths=widths),
        ],
    )

    return Div(
        style=col | grow(1) | align_children_stretch,
        children=([filter_bar(filter_text=filter_text), table] if filter_active else [table]),
    )


@component
def filter_bar(filter_text: str) -> Text:
    return Text(
        content=f"Filter: {filter_text}▌",
        style=text_color("yellow", 300) | border_light | border_color("yellow", 600) | pad_x(1),
    )


@component
def process_header(sort_col: int, sort_asc: bool, col_widths: list[int]) -> Div:
    indicator = "↑" if sort_asc else "↓"
    cols = []
    for i, (label, w) in enumerate(zip(SORT_COLS, col_widths)):
        suffix = f" {indicator}" if i == sort_col else "  "
        cell_style = text_color("amber", 300) | _text_bold
        if w > 0:
            cols.append(Text(content=f"{label}{suffix}", style=cell_style | width(w) | pad_x(1)))
        else:
            cols.append(Text(content=f"{label}{suffix}", style=cell_style | grow(1) | min_width(0) | pad_x(1)))
    return Div(
        style=row | align_children_stretch,
        children=cols,
    )


@component
def process_list(procs: tuple[ProcessInfo, ...], selected: int, num_procs: int, col_widths: list[int]) -> Div:
    rects = use_rects()
    visible_height = int(rects.content.height)

    clamped = min(selected, max(0, num_procs - 1))
    half = visible_height // 2
    start = max(0, min(clamped - half, num_procs - visible_height))
    end = min(start + visible_height, num_procs)

    rows = [process_row(proc=procs[i], is_selected=(i == clamped), col_widths=col_widths) for i in range(start, end)]

    return Div(
        style=col | grow(1) | align_children_stretch,
        children=rows,
    )


@component
def process_row(proc: ProcessInfo, is_selected: bool, col_widths: list[int]) -> Div:
    cpu_color, cpu_shade = _usage_color(proc.cpu_percent)
    mem_color, mem_shade = _usage_color(proc.mem_percent)

    sel = _text_bold if is_selected else default

    pid_cell = Text(content=str(proc.pid), style=sel | width(col_widths[0]) | pad_x(1) | text_color("slate", 300))
    user_cell = Text(content=proc.user[:12], style=sel | width(col_widths[1]) | pad_x(1) | text_color("cyan", 300))
    cpu_cell = Text(
        content=f"{proc.cpu_percent:.1f}%",
        style=sel | width(col_widths[2]) | pad_x(1) | text_color(cpu_color, cpu_shade),
    )
    mem_cell = Text(
        content=f"{proc.mem_percent:.2f}%",
        style=sel | width(col_widths[3]) | pad_x(1) | text_color(mem_color, mem_shade),
    )
    cmd_cell = Text(
        content=proc.command,
        style=sel | grow(1) | min_width(0) | pad_x(1) | text_color("slate", 200),
    )

    return Div(
        style=row | align_children_stretch,
        children=[pid_cell, user_cell, cpu_cell, mem_cell, cmd_cell],
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
