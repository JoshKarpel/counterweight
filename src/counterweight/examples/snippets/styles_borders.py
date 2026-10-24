"""
Styles: Borders

Each kind of border.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles import Style
from counterweight.styles.utilities import *

# --8<-- [start:example]

KINDS: tuple[tuple[str, Style], ...] = (
    ("border_light", border_light),
    ("border_lightrounded", border_lightrounded),
    ("border_lightangled", border_lightangled),
    ("border_heavy", border_heavy),
    ("border_double", border_double),
    ("border_thick", border_thick),
    ("border_mcgugan", border_mcgugan),
    ("border_lightshade", border_lightshade),
    ("border_mediumshade", border_mediumshade),
    ("border_heavyshade", border_heavyshade),
    ("border_star", border_star),
)


@component
def gallery() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1), fr(1)) | gap(1),
        children=tuple(Text(style=border | kind | pad(1) | text_justify_center, content=name) for name, kind in KINDS),
    )


# --8<-- [end:example]


ROOTS = (gallery,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("styles-border-kinds", gallery(), (74, 23))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(gallery()))
