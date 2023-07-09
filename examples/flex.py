from pprint import pprint

from structlog import get_logger

from reprisal.components import Div, Paragraph
from reprisal.layout import Rect, build_layout_tree
from reprisal.paint import debug_paint, paint_layout
from reprisal.styles import Border, BorderKind, Span, Style
from reprisal.styles.styles import Flex

logger = get_logger()

b = Rect(x=0, y=0, width=30, height=0)


e = Div(
    children=[
        Paragraph(
            content="top",
            style=Style(
                display=Flex(),
                span=Span(width="auto", height=1),
                border=Border(kind=BorderKind.Light),
            ),
        ),
        Paragraph(
            content="bottom",
            style=Style(
                display=Flex(),
                span=Span(width="auto", height=1),
                border=Border(kind=BorderKind.Light),
            ),
        ),
    ],
    style=Style(
        display=Flex(direction="column"),
        border=Border(kind=BorderKind.Heavy),
    ),
)

t = build_layout_tree(e)
t.flex()
pprint(t.dict(exclude_defaults=True))
p = paint_layout(t)
print("-----")
print(debug_paint(p, t.dims.margin_rect()))
print("-----")
