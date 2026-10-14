"""Plain-text tables for the benchmark CLI's reports."""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import zip_longest


@dataclass(frozen=True, slots=True)
class Column:
    header: str
    is_right_aligned: bool = False


def render_table(columns: Sequence[Column], rows: Iterable[Sequence[str]], title: str = "") -> str:
    """
    Lay out `rows` under `columns`, each column as wide as its widest line, with a rule under the headers.

    A cell may hold several lines, which stack within its row.
    """
    split_rows = [[cell.splitlines() or [""] for cell in row] for row in rows]
    widths = [
        max([len(column.header), *(len(line) for row in split_rows for line in row[index])])
        for index, column in enumerate(columns)
    ]

    def line(cells: Sequence[str]) -> str:
        return "  ".join(
            cell.rjust(width) if column.is_right_aligned else cell.ljust(width)
            for column, width, cell in zip(columns, widths, cells, strict=True)
        ).rstrip()

    lines = [title] if title else []
    lines.append(line([column.header for column in columns]))
    lines.append(line(["─" * width for width in widths]))
    for row in split_rows:
        lines.extend(line(cells) for cells in zip_longest(*row, fillvalue=""))
    return "\n".join(lines) + "\n"
