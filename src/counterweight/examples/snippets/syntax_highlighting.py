"""
Rich text: Syntax highlighting

Source code highlighted for its language, in code blocks and laid out line by line beside line numbers.
"""

import asyncio
import sys

from counterweight import app
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.highlighting import code_block
from counterweight.highlighting import code_style
from counterweight.highlighting import highlight
from counterweight.styles.utilities import *

# --8<-- [start:example]

SOURCE = '''\
@component
def greeting(name: str) -> Text:
    """Say hello."""
    return Text(content=f"Hello, {name}!")
'''


@component
def root() -> Div:
    return Div(
        style=col | gap(1),
        children=tuple(
            Div(
                style=col,
                children=(
                    Text(content=f" {theme} ", style=text_color("slate", 400)),
                    code_block(SOURCE.rstrip("\n"), "python", theme=theme, style=pad(1)),
                ),
            )
            for theme in ("github-dark", "monokai", "solarized-light")
        ),
    )


# --8<-- [end:example]

# --8<-- [start:lines]

PATCHED = """\
def mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)
"""


def lines_of(chunks: tuple[Chunk, ...]) -> list[tuple[Chunk, ...]]:
    """The chunks on each line, split where a chunk holds a line break."""
    lines: list[list[Chunk]] = [[]]
    for chunk in chunks:
        first, *rest = chunk.content.split("\n")
        lines[-1].append(Chunk(content=first, style=chunk.style))
        lines.extend([Chunk(content=part, style=chunk.style)] for part in rest)
    return [tuple(chunk for chunk in line if chunk.content) for line in lines]


@component
def numbered(code: str, marked: int, theme: str = "github-dark") -> Div:
    base = code_style(theme)
    mark = text_bg("slate", 700) | content_color("slate", 700)
    return Div(
        style=col | pad_y(1) | base | fit_content_width,
        children=tuple(
            Div(
                style=row,
                children=(
                    Text(
                        content=f" {number:>2} ",
                        style=base
                        | (text_color("amber", 400) | mark if number == marked else text_color("slate", 500)),
                    ),
                    Text(
                        content=line,
                        style=base | grow(1) | pad_right(2) | (mark if number == marked else default),
                    ),
                ),
            )
            for number, line in enumerate(lines_of(highlight(code.rstrip("\n"), "python", theme)), start=1)
        ),
    )


@component
def lines() -> Div:
    return Div(children=(numbered(PATCHED, marked=3),))


# --8<-- [end:lines]


ROOTS = (root, lines)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("syntax-highlighting", root(), (50, 24)),
    Still("syntax-highlighting-lines", lines(), (46, 7)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
