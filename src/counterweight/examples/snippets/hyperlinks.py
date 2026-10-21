"""
Rich text: Hyperlinks

Text that links to a URL, which terminals that support links open on a click.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:example]

LINK = text_underline | text_color("sky", 300)


@component
def root() -> Div:
    return Div(
        style=col | gap(1) | pad_x(1),
        children=(
            Text(
                content=(
                    Chunk(content="Counterweight is on "),
                    Chunk(content="GitHub", style=LINK | text_link("https://github.com/JoshKarpel/counterweight")),
                    Chunk(content=", and its docs are at "),
                    Chunk(content="counterweight.dev", style=LINK | text_link("https://www.counterweight.dev")),
                    Chunk(content="."),
                ),
                style=text_wrap_pretty,
            ),
            Text(
                content="This whole Text is one link.",
                style=pad_x(1) | border | border_lightrounded | text_link("https://pygments.org"),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("hyperlinks", root(), (50, 7))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
