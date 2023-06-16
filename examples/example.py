from reprisal.compositor import BoxDimensions, Edge, Rect, build_layout_tree, debug, paint
from reprisal.elements.elements import Div, Text
from reprisal.styles.styles import Border, BorderKind, Padding, Span, Style
from reprisal.styles.utilities import ml_auto, mr_auto, mx_auto

b = BoxDimensions(
    content=Rect(x=0, y=0, width=30, height=0),
    margin=Edge(),
    border=Edge(),
    padding=Edge(),
)
e = Div(
    children=(
        Text(
            text="width=auto",
            style=Style(
                span=Span(width="auto", height=1),
                border=Border(kind=BorderKind.Light),
                padding=Padding(top=0, bottom=0, left=0, right=0),
            ),
        ),
        Text(
            text="width=20,right=auto",
            style=Style(
                span=Span(width=20, height=1),
                border=Border(kind=BorderKind.LightRounded),
                padding=Padding(top=0, bottom=0, left=0, right=0),
            )
            | mr_auto,
        ),
        Text(
            text="width=20,left=auto",
            style=Style(
                span=Span(width=20, height=1),
                border=Border(kind=BorderKind.Heavy),
                padding=Padding(top=0, bottom=0, left=0, right=0),
            )
            | ml_auto,
        ),
        Text(
            text="width=20,rl=auto",
            style=(
                Style(
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.Double),
                )
                | mx_auto
            ),
        ),
        Text(
            text="width=20,default,pad",
            style=(
                Style(
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.LightShade),
                    padding=Padding(top=1, left=3),
                )
            ),
        ),
        Text(
            text="width=20,default",
            style=(
                Style(
                    span=Span(width=20, height=1),
                    border=Border(kind=BorderKind.Thick),
                )
            ),
        ),
    ),
    style=Style(
        border=Border(kind=BorderKind.Heavy),
    ),
)

t = build_layout_tree(e)
t.layout(b)
p = paint(t)
print(debug(p, t.dims.margin_rect()))