import asyncio
import time

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_effect, use_state
from counterweight.keys import Key
from counterweight.styles import LinearGradient
from counterweight.styles.utilities import *

logger = get_logger()


@component
def root() -> Div:
    active, set_active = use_state(True)
    angle, set_angle = use_state(0)
    num_frames, set_num_frames = use_state(0)
    start_time, _ = use_state(time.monotonic)

    def toggle(event: KeyPressed) -> None:
        match event.key:
            case Key.Space:
                set_active(not active)
            case Key.Up:
                set_angle(lambda a: (a + 1) % 360)
            case Key.Down:
                set_angle(lambda a: (a - 1) % 360)

    async def rotate() -> None:
        if not active:
            return

        while True:
            logger.info("Rotating")
            set_angle(lambda a: (a + 1) % 360)
            set_num_frames(lambda n: n + 1)
            await asyncio.sleep(0)

    use_effect(rotate, (active,))

    return Div(
        style=col
        | gap_children_2
        | align_children_center
        | justify_children_center
        | margin_8
        | Style(
            margin=Margin(
                color=LinearGradient(
                    stops=(
                        Color.from_name("red"),
                        Color.from_name("blue"),
                    ),
                    angle=angle,
                )
            ),
            content=Content(
                color=LinearGradient(
                    stops=(
                        Color.from_name("orange"),
                        Color.from_name("teal"),
                    ),
                    angle=-angle,
                )
            ),
        ),
        children=[
            Text(
                style=align_self_center | weight_none,
                content=f"{angle}°",
            ),
            Text(
                style=align_self_center | weight_none,
                content=f"{num_frames / (time.monotonic() - start_time):.03} fps",
            ),
        ],
        on_key=toggle,
    )


if __name__ == "__main__":
    asyncio.run(
        app(
            root,
            line_profile=(
                app,
                # paint_to_instructions,
                # sgr_from_cell_style,
                # LinearGradient.at,
                # LinearGradient.at_many,
                # paint_edge,
                # paint_content,
                # paint_element,
                # Position.__hash__,
                # P.blank,
                # Color.blend,
                # Color._blend,
                # Color.flyweight,
            ),
        )
    )
