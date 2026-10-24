"""
A fuzzy finder drawn inline, as `fzf --height` draws one: the best matches for a query among five thousand paths,
each with its matched characters highlighted, and one of them selected, above a count and the query,
which is typed a character a frame and then erased.

The region never changes height and nothing is printed, so this measures an inline frame at its plainest:
a region of a fixed size whose every row changes as the query does,
drawn with relative cursor moves and fed to the emulator.
Matching is cached by query, so after the first pass through the queries, the workload's own work is small.
"""

import random
from dataclasses import dataclass
from functools import cache
from itertools import groupby

from benchmarks.harness import Workload
from counterweight import Inline
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles import CellStyle
from counterweight.styles.utilities import amber_400
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_400
from counterweight.styles.utilities import slate_300
from counterweight.styles.utilities import slate_500
from counterweight.styles.utilities import slate_800
from counterweight.styles.utilities import text_bg
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_none

DIRECTORIES = ("src", "tests", "docs", "benchmarks", "codegen", "examples")
PACKAGES = ("counterweight", "layout", "paint", "hooks", "styles", "widgets", "headless", "painters", "input")
STEMS = ("shadow", "routing", "output", "capture", "viewports", "text", "markdown", "gradients", "focus", "clock")
EXTENSIONS = ("py", "md", "txt", "svg", "cast", "json")
PATHS = tuple(
    sorted(
        {
            f"{rng.choice(DIRECTORIES)}/{rng.choice(PACKAGES)}/{rng.choice(STEMS)}_{rng.choice(STEMS)}{n % 97}"
            f".{rng.choice(EXTENSIONS)}"
            for rng in (random.Random(0),)
            for n in range(5000)
        }
    )
)
SHOWN = 15
QUERY = "srcpaintout"
# Typed a character a frame, then erased a character a frame.
QUERIES = tuple(QUERY[:n] for n in range(len(QUERY) + 1)) + tuple(QUERY[:n] for n in range(len(QUERY) - 1, 0, -1))


@dataclass(frozen=True, slots=True)
class Match:
    path: str
    positions: frozenset[int]


def fuzzy_match(query: str, path: str) -> Match | None:
    """`path`, with where it matches each of `query`'s characters in order, the first place each fits."""
    positions = []
    start = 0
    for char in query:
        found = path.find(char, start)
        if found < 0:
            return None
        positions.append(found)
        start = found + 1
    return Match(path, frozenset(positions))


@cache
def matches(query: str) -> tuple[tuple[Match, ...], int]:
    """The best `SHOWN` matches for `query`, the tightest first, and how many paths match."""
    found = [match for path in PATHS if (match := fuzzy_match(query, path)) is not None]
    found.sort(key=lambda match: (max(match.positions, default=0) - min(match.positions, default=0), match.path))
    return tuple(found[:SHOWN]), len(found)


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    query: str
    shown: tuple[Match, ...]
    count: int
    selected: int


def initial() -> Model:
    shown, count = matches("")
    return Model(tick=0, query="", shown=shown, count=count, selected=0)


def step(model: Model) -> Model:
    tick = model.tick + 1
    query = QUERIES[tick % len(QUERIES)]
    shown, count = matches(query)
    return Model(tick=tick, query=query, shown=shown, count=count, selected=tick % SHOWN % max(len(shown), 1))


MATCHED = CellStyle(foreground=amber_400)
UNMATCHED = CellStyle(foreground=slate_300)


def highlighted(match: Match) -> tuple[Chunk, ...]:
    """`match`'s path in chunks, alternating between runs of matched and unmatched characters."""
    return tuple(
        Chunk(
            content="".join(char for _, char in run),
            style=MATCHED if is_matched else UNMATCHED,
        )
        for is_matched, run in groupby(enumerate(match.path), key=lambda item: item[0] in match.positions)
    )


def view(model: Model) -> Div:
    return Div(
        style=col,
        children=(
            *(
                Text(
                    content=(Chunk(content="▌ " if index == model.selected else "  "), *highlighted(match)),
                    style=text_wrap_none | (text_bg(slate_800) if index == model.selected else text_color(slate_300)),
                )
                for index, match in enumerate(model.shown)
            ),
            *(Text(content=" ") for _ in range(SHOWN - len(model.shown))),
            Text(content=f"  {model.count}/{len(PATHS)}", style=text_color(slate_500)),
            Text(content=(Chunk(content="> ", style=CellStyle(foreground=cyan_400)), Chunk(content=model.query))),
        ),
    )


WORKLOAD = Workload(
    name="picker",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(100, 30),
    viewport=Inline(),
)
