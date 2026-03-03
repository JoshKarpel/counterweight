# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit, Screenshot, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.keys import Key
from counterweight.styles.utilities import *

container_style = grow(1) | align_self_stretch | border_collapse
box_style = grow(1) | align_self_stretch | justify_children_center | align_children_center
border_kind = border_double


@component
def root() -> Div:
    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Space:
                return ToggleBorderHealing()
            case _:
                return None

    return Div(
        style=row | container_style,
        on_key=on_key,
        children=[
            Div(
                style=col | container_style,
                children=[
                    box("A1"),
                    box("A2"),
                ],
            ),
            Div(
                style=col | container_style,
                children=[
                    Div(
                        style=row | container_style,
                        children=[
                            box("B1"),
                            box("B2"),
                        ],
                    ),
                    Div(
                        style=row | container_style,
                        children=[
                            box("C1"),
                            box("C2"),
                            box("C3"),
                            box("C4"),
                        ],
                    ),
                    Div(
                        style=row | container_style,
                        children=[
                            box("D1"),
                            box("D2"),
                            box("D3"),
                        ],
                    ),
                ],
            ),
        ],
    )


@component
def box(s: str) -> Div:
    return Div(
        style=box_style | border_kind,
        children=[
            Text(
                style=text_justify_center | text("cyan", 500),
                content=s,
            )
        ],
    )


# --8<-- [end:example]

if __name__ == "__main__":
    import asyncio
    from pathlib import Path

    THIS_DIR = Path(__file__).parent

    asyncio.run(
        app(
            root,
            headless=True,
            dimensions=(60, 20),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "border-healing-on.svg", indent=1),
                KeyPressed(key=Key.Space),
                Screenshot.to_file(THIS_DIR.parent / "assets" / "border-healing-off.svg", indent=1),
                Quit(),
            ],
        )
    )
