from pprint import pprint

from reprisal.components import Div, Paragraph
from reprisal.layout import BoxDimensions, Edge, Rect, build_layout_tree
from reprisal.styles import Border, BorderKind, Span, Style

b = BoxDimensions(
    content=Rect(x=0, y=0, width=30, height=0),
    margin=Edge(),
    border=Edge(),
    padding=Edge(),
)


e = Div(
    children=[
        Paragraph(
            content="top",
            style=Style(
                display="block",
                span=Span(width=5),
                border=Border(kind=BorderKind.LightRounded),
            ),
        ),
        Paragraph(
            content="left",
            style=Style(
                display="inline",
                span=Span(width=5),
                border=Border(kind=BorderKind.LightRounded),
            ),
        ),
        Paragraph(
            content="right",
            style=Style(
                display="inline",
                span=Span(width=5),
                border=Border(kind=BorderKind.LightRounded),
            ),
        ),
        Paragraph(
            content="bottom",
            style=Style(
                display="block",
                span=Span(width=5),
                border=Border(kind=BorderKind.LightRounded),
            ),
        ),
    ],
    style=Style(border=Border(kind=BorderKind.Thick)),
)

t = build_layout_tree(e)
pprint(t.dict(exclude_defaults=True, exclude_unset=True))
# t.layout(b)
# p = paint_layout(t)
# print(debug_paint(p, t.dims.margin_rect()))
