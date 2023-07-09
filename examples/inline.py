import asyncio

from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Paragraph, component
from reprisal.styles import Border, BorderKind, Span, Style
from reprisal.styles.styles import CellStyle, Inline, Text
from reprisal.styles.utilities import text_fuchsia_600, text_rose_500, text_teal_600

logger = get_logger(__name__)

width = 6


@component
def text(*parts: str | tuple[str, CellStyle | Style]) -> Div:
    children = []
    for part in parts:
        match part:
            case str() as part:
                children.append(
                    Paragraph(
                        content=part,
                        style=Style(
                            display=Inline(),
                            span=Span(height=1),
                        ),
                    )
                )
            case (str() as part, CellStyle() as style):
                children.append(
                    Paragraph(
                        content=part,
                        style=Style(
                            display=Inline(),
                            span=Span(height=1),
                            text=Text(style=style),
                        ),
                    )
                )
            case (str() as part, Style() as style):
                children.append(
                    Paragraph(
                        content=part,
                        style=(
                            style
                            | Style(
                                display=Inline(),
                                span=Span(height=1),
                            )
                        ),
                    )
                )

    return Div(children=children)


@component
def root() -> Div:
    return Div(
        children=[
            Paragraph(
                content="top",
                style=Style(
                    span=Span(width="auto", height=1),
                    border=Border(kind=BorderKind.LightRounded),
                ),
            ),
            text(
                ("left", text_teal_600),
                ("next", text_fuchsia_600),
                ("right", text_rose_500),
            ),
            Paragraph(
                content="bottom",
                style=Style(
                    span=Span(width=width, height=1),
                    border=Border(kind=BorderKind.LightRounded),
                ),
            ),
        ],
        style=Style(border=Border(kind=BorderKind.Thick)),
    )


asyncio.run(app(root))
