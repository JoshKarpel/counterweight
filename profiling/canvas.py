import asyncio
import random
import time
from collections import deque
from itertools import product

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.hooks import use_effect, use_state
from counterweight.styles.styles import COLORS_BY_NAME
from counterweight.styles.utilities import *
from counterweight.utils import canvas, clamp

_frame_times: deque[float] = deque(maxlen=300)


@component
def fps_display() -> Text:
    fps, set_fps = use_state(0.0)

    async def tick() -> None:
        while True:
            await asyncio.sleep(0.25)
            if len(_frame_times) >= 2:
                elapsed = _frame_times[-1] - _frame_times[0]
                set_fps((len(_frame_times) - 1) / elapsed if elapsed > 0 else 0.0)

    use_effect(tick, deps=())

    return Text(
        content=[Chunk(content=f"FPS: {fps:.1f}", style=CellStyle(foreground=green_400))],
    )


@component
def root() -> Div:
    _frame_times.append(time.monotonic())
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            header(),
            fps_display(),
            Div(
                style=col | align_children_center | justify_children_center | border_collapse,
                children=[
                    Div(
                        style=row | align_children_center | justify_children_space_evenly | border_collapse,
                        children=[
                            random_walkers(),
                            random_walkers(),
                        ],
                    ),
                    Div(
                        style=row | align_children_center | justify_children_space_evenly | border_collapse,
                        children=[
                            random_walkers(),
                            random_walkers(),
                        ],
                    ),
                ],
            ),
        ],
    )


@component
def header() -> Text:
    return Text(
        content=[
            Chunk(
                content="Canvas",
                style=CellStyle(foreground=amber_600),
            ),
            Chunk.space(),
            Chunk(
                content="Demo",
                style=CellStyle(foreground=cyan_600),
            ),
            Chunk.newline(),
            Chunk(
                content="App",
                style=CellStyle(foreground=pink_600),
            ),
        ],
        style=text_justify_center,
    )


moves = [(x, y) for x, y in product((-1, 0, 1), repeat=2) if (x, y) != (0, 0)]

w, h = 30, 30
n = 30


@component
def random_walkers() -> Text:
    # We don't update the colors, but we want to generate a unique set of colors in each instance of the component,
    # so we use a state hook to generate them once and then never update them
    colors, _set_colors = use_state(lambda: random.sample(list(COLORS_BY_NAME.values()), k=n))
    walkers, set_walkers = use_state(lambda: [(random.randrange(w), random.randrange(h)) for _ in range(n)])

    def update_movers(m: list[tuple[int, int]]) -> list[tuple[int, int]]:
        new = []
        for x, y in m:
            dx, dy = random.choice(moves)
            new.append(
                (
                    clamp(0, x + dx, w - 1),
                    clamp(0, y + dy, h - 1),
                )
            )
        return new

    async def tick() -> None:
        while True:
            set_walkers(update_movers)
            await asyncio.sleep(0)

    use_effect(tick, deps=())

    return Text(
        content=canvas(
            width=w,
            height=h,
            cells=dict(zip(walkers, colors)),
        ),
        style=border_heavy | border_color("slate", 400),
    )


if __name__ == "__main__":

    async def run() -> None:
        try:
            await asyncio.wait_for(app(root), timeout=60)
        except asyncio.TimeoutError:
            pass

    asyncio.run(run())
