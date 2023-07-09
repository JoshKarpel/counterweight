from pprint import pprint

from structlog import get_logger

from reprisal.components import Div, Paragraph
from reprisal.layout import build_layout_tree
from reprisal.paint import debug_paint, paint_layout
from reprisal.styles import Border, BorderKind, Span, Style
from reprisal.styles.styles import Flex

logger = get_logger()

e = Div(
    children=[
        Paragraph(
            content="top",
            style=Style(
                display=Flex(weight=2),
                span=Span(width=10, height=1),
                border=Border(kind=BorderKind.Light),
            ),
        ),
        Paragraph(
            content="bottom",
            style=Style(
                display=Flex(),
                span=Span(width=10, height=1),
                border=Border(kind=BorderKind.Light),
            ),
        ),
    ],
    style=Style(
        display=Flex(direction="column"),
        span=Span(width=30, height=10),
        border=Border(kind=BorderKind.Heavy),
    ),
)
t = build_layout_tree(e)
t.flex()
pprint(t.dict(exclude_defaults=True, include={"dims", "children"}))
p = paint_layout(t)
pprint(t.dims.dict())
for child in t.children:
    pprint(child.dims.dict())
print("-----")
print(debug_paint(p, t.dims.margin_rect()))
print("-----")
