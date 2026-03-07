import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = get_logger()


@dataclass(frozen=True)
class Peak:
    mountain: str
    height: int  # meters
    massif: str
    first_ascent: int  # year


# All 14 peaks above 8000m, in order of first ascent
PEAKS = [
    Peak("Annapurna I", 8091, "Himalayas", 1950),
    Peak("Everest", 8849, "Himalayas", 1953),
    Peak("Nanga Parbat", 8126, "Himalayas", 1953),
    Peak("K2", 8611, "Karakoram", 1954),
    Peak("Cho Oyu", 8188, "Himalayas", 1954),
    Peak("Kangchenjunga", 8586, "Himalayas", 1955),
    Peak("Makalu", 8485, "Himalayas", 1955),
    Peak("Gasherbrum II", 8035, "Karakoram", 1956),
    Peak("Lhotse", 8516, "Himalayas", 1956),
    Peak("Manaslu", 8163, "Himalayas", 1956),
    Peak("Broad Peak", 8051, "Karakoram", 1957),
    Peak("Gasherbrum I", 8080, "Karakoram", 1958),
    Peak("Dhaulagiri I", 8167, "Himalayas", 1960),
    Peak("Shishapangma", 8027, "Himalayas", 1964),
]

# (label, display value, sort key)
COLUMNS: list[tuple[str, Callable[[Peak], str], Callable[[Peak], Any]]] = [
    ("Mountain", lambda p: p.mountain, lambda p: p.mountain),
    ("Height (m)", lambda p: str(p.height), lambda p: p.height),
    ("Massif", lambda p: p.massif, lambda p: p.massif),
    ("First Ascent", lambda p: str(p.first_ascent), lambda p: p.first_ascent),
]

_SORT_INDICATOR_WIDTH = 2  # " ↑" or " ↓"


def _col_width(label: str, display: Callable[[Peak], str]) -> int:
    return max(len(label) + _SORT_INDICATOR_WIDTH, *(len(display(peak)) for peak in PEAKS))


COL_WIDTHS = [_col_width(label, display) for label, display, _ in COLUMNS]

text_bold = Style(text_style=CellStyle(bold=True))


@component
def root() -> Div:
    selected, set_selected = use_state(0)
    sort_col, set_sort_col = use_state(1)  # default: height
    sort_asc, set_sort_asc = use_state(False)  # default: descending

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case Key.Up:
                set_selected(lambda s: max(0, s - 1))
            case Key.Down:
                set_selected(lambda s: min(len(PEAKS) - 1, s + 1))
            case "1" | "2" | "3" | "4" as k:
                col = int(k) - 1
                if col == sort_col:
                    set_sort_asc(not sort_asc)
                else:
                    set_sort_col(col)
                    set_sort_asc(True)
                set_selected(0)

    _, _, sort_key = COLUMNS[sort_col]
    sorted_peaks = tuple(sorted(PEAKS, key=sort_key, reverse=not sort_asc))

    return Div(
        style=col | align_children_center | justify_children_center,
        on_key=on_key,
        children=[
            Text(
                content="Eight-Thousanders",
                style=text("amber", 400) | pad_y(1),
            ),
            data_table(peaks=sorted_peaks, selected=selected, sort_col=sort_col, sort_asc=sort_asc),
            Text(
                content=f"  ↑ / ↓  navigate  •  1-4  sort by column  •  {selected + 1} / {len(PEAKS)}",
                style=text("slate", 400) | pad_y(1),
            ),
        ],
    )


@component
def data_table(peaks: tuple[Peak, ...], selected: int, sort_col: int, sort_asc: bool) -> Div:
    return Div(
        style=col | border_collapse,
        children=[
            header_row(sort_col=sort_col, sort_asc=sort_asc),
            *[data_row(peak=peaks[i], selected=(i == selected)) for i in range(len(peaks))],
        ],
    )


@component
def header_row(sort_col: int, sort_asc: bool) -> Div:
    return Div(
        style=row | border_collapse,
        children=[
            header_cell(label=label, col_width=COL_WIDTHS[idx], col_idx=idx, sort_col=sort_col, sort_asc=sort_asc)
            for idx, (label, _, _) in enumerate(COLUMNS)
        ],
    )


@component
def header_cell(label: str, col_width: int, col_idx: int, sort_col: int, sort_asc: bool) -> Text:
    indicator = (" ↑" if sort_asc else " ↓") if col_idx == sort_col else ""
    return Text(
        content=f"{label}{indicator}",
        style=content_box | border_light | width(col_width) | pad_x(1) | text("amber", 300) | text_bold,
    )


@component
def data_row(peak: Peak, selected: bool) -> Div:
    return Div(
        style=row | border_collapse,
        children=[
            data_cell(value=display(peak), col_width=COL_WIDTHS[idx], selected=selected)
            for idx, (_, display, _) in enumerate(COLUMNS)
        ],
    )


@component
def data_cell(value: str, col_width: int, selected: bool) -> Text:
    return Text(
        content=value,
        style=(
            content_box
            | border_light
            | width(col_width)
            | pad_x(1)
            | (text_bold | text("sky", 200) if selected else text("slate", 300))
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root))
