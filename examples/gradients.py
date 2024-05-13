import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_effect, use_state
from counterweight.keys import Key
from counterweight.paint import paint_content, paint_edge, paint_element
from counterweight.styles import LinearGradient
from counterweight.styles.utilities import *

logger = get_logger()


@component
def root() -> Div:
    active, set_active = use_state(True)
    angle, set_angle = use_state(0)

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
            await asyncio.sleep(0)

    use_effect(rotate, (active,))

    return Div(
        style=row
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
        ],
        on_key=toggle,
    )


# @component
# def root() -> Div:
#     return Div(
#         style=row
#         | align_children_center
#         | justify_children_center
#         | border_heavy
#         | margin_5
#         | Style(
#             border=Border(
#                 style=CellStyle(
#                     foreground=LinearGradient(
#                         stops=(
#                             Color.from_name("black"),
#                             Color.from_name("red"),
#                         ),
#                         angle=45,
#                     ),
#                     background=LinearGradient(
#                         stops=(
#                             Color.from_name("teal"),
#                             Color.from_name("yellow"),
#                         ),
#                         angle=45,
#                     ),
#                 )
#             ),
#             margin=Margin(
#                 color=LinearGradient(
#                     stops=(
#                         Color.from_name("red"),
#                         Color.from_name("cyan"),
#                     ),
#                     angle=0,
#                 )
#             ),
#             content=Content(
#                 color=LinearGradient(
#                     stops=(
#                         Color.from_name("orange"),
#                         Color.from_name("blue"),
#                     ),
#                     angle=90,
#                 )
#             ),
#         ),
#         children=[
#             Text(
#                 style=weight_none
#                 | pad_2
#                 | border_mcgugan
#                 | margin_2
#                 | Style(
#                     typography=Typography(
#                         style=CellStyle(
#                             foreground=LinearGradient(
#                                 stops=(
#                                     Color.from_name("greenyellow"),
#                                     Color.from_name("lightsalmon"),
#                                 ),
#                                 angle=45,
#                             ),
#                             background=LinearGradient(
#                                 stops=(
#                                     Color.from_name("blue"),
#                                     Color.from_name("black"),
#                                 ),
#                                 angle=45,
#                             ),
#                         )
#                     ),
#                     border=Border(
#                         style=CellStyle(
#                             foreground=LinearGradient(
#                                 stops=(
#                                     Color.from_name("black"),
#                                     Color.from_name("red"),
#                                 ),
#                                 angle=45,
#                             ),
#                             background=LinearGradient(
#                                 stops=(
#                                     Color.from_name("teal"),
#                                     Color.from_name("yellow"),
#                                 ),
#                                 angle=45,
#                             ),
#                         )
#                     ),
#                     margin=Margin(
#                         color=LinearGradient(
#                             stops=(
#                                 Color.from_name("red"),
#                                 Color.from_name("cyan"),
#                             ),
#                             angle=60,
#                         )
#                     ),
#                     padding=Padding(
#                         color=LinearGradient(
#                             stops=(
#                                 Color.from_name("purple"),
#                                 Color.from_name("green"),
#                             ),
#                             angle=30,
#                         )
#                     ),
#                 ),
#                 content="Hello, Gradients!",
#             ),
#         ],
#     )


if __name__ == "__main__":
    asyncio.run(
        app(
            root,
            line_profile=(
                app,
                # LinearGradient.at,
                paint_edge,
                paint_content,
                paint_element,
                # Position.__hash__,
                # P.blank,
                # Color._blend,
                # Color.flyweight,
            ),
        )
    )
