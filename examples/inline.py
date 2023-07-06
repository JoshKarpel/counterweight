from pprint import pprint

from reprisal.components import Div, Paragraph
from reprisal.layout import BoxDimensions, Edge, Rect, build_layout_tree
from reprisal.paint import debug_paint, paint_layout
from reprisal.styles import Border, BorderKind, Margin, Span, Style
from reprisal.styles.styles import Inline

b = BoxDimensions(
    content=Rect(x=0, y=0, width=30, height=0),
    margin=Edge(),
    border=Edge(),
    padding=Edge(),
)

width = 6

e = Div(
    children=[
        Paragraph(
            content="top",
            style=Style(
                span=Span(width=width, height=1),
                border=Border(kind=BorderKind.LightRounded),
            ),
        ),
        Paragraph(
            content="left",
            style=Style(
                display=Inline(),
                span=Span(width=width, height=1),
                border=Border(kind=BorderKind.LightRounded),
            ),
        ),
        Paragraph(
            content="right",
            style=Style(
                display=Inline(justify="right"),
                span=Span(width=width, height=1),
                margin=Margin(left=5),
                border=Border(kind=BorderKind.LightRounded),
            ),
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

t = build_layout_tree(e)
pprint(t.dict(exclude_defaults=True, exclude_unset=True))
t.layout(b.content)
p = paint_layout(t)
print(debug_paint(p, t.dims.margin_rect()))
