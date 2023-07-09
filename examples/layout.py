from reprisal.components import Div, Paragraph
from reprisal.layout import BoxDimensions, Edge, Rect, build_layout_tree
from reprisal.paint import debug_paint, paint_layout
from reprisal.styles import Border, BorderKind, Padding, Span, Style, ml_auto, mr_auto, mx_auto
from reprisal.styles.styles import Hidden

b = BoxDimensions(
    content=Rect(x=0, y=0, width=30, height=0),
    margin=Edge(),
    border=Edge(),
    padding=Edge(),
)

e = Div(
    children=[
        Paragraph(
            content="width=auto",
            style=Style(
                span=Span(width="auto", height=1),
                border=Border(kind=BorderKind.Light),
                padding=Padding(top=0, bottom=0, left=0, right=0),
            ),
        ),
        Paragraph(
            content="width=20,right=auto",
            style=Style(
                span=Span(width=20, height=1),
                border=Border(kind=BorderKind.LightRounded),
                padding=Padding(top=0, bottom=0, left=0, right=0),
            )
            | mr_auto,
        ),
        Paragraph(
            content="width=20,left=auto",
            style=Style(
                span=Span(width=20, height=1),
                border=Border(kind=BorderKind.Heavy),
                padding=Padding(top=0, bottom=0, left=0, right=0),
            )
            | ml_auto,
        ),
        Paragraph(
            content="width=20,rl=auto",
            style=(
                Style(
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.Double),
                )
                | mx_auto
            ),
        ),
        Paragraph(
            content="width=20,default,pad",
            style=(
                Style(
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.LightShade),
                    padding=Padding(top=1, left=3),
                )
            ),
        ),
        Paragraph(
            content="width=20,default",
            style=(
                Style(
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.Thick),
                )
            ),
        ),
        Paragraph(
            content="none",
            style=(
                Style(
                    display=Hidden(),
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.Thick),
                )
            ),
        ),
    ],
    style=Style(
        border=Border(kind=BorderKind.Heavy),
    ),
)

t = build_layout_tree(e)
t.layout(b)
p = paint_layout(t)
print(debug_paint(p, t.dims.margin_rect()))
