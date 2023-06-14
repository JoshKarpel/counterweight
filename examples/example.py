import shutil

from reprisal.compositor import Dimensions, Edge, Rect, build_layout_tree, debug, paint
from reprisal.elements import Border, BorderKind, Div, Margin, Padding, Span, Style, Text

w, h = shutil.get_terminal_size()
b = containing_box = Dimensions(
    content=Rect(x=0, y=0, width=30, height=0),
    margin=Edge(),
    border=Edge(),
    padding=Edge(),
)

t = build_layout_tree(
    element=Div(
        # there seems to be margin even though I didn't ask for any?
        # off-by-one errors in how I nest boxes?
        # padding seems to behave just like margin...
        children=[
            Text(
                text="width=auto",
                style=Style(
                    span=Span(width="auto", height=1),
                    margin=Margin(top=0, bottom=0, left=0, right=0),
                    border=Border(kind=BorderKind.LightRounded),
                    # border=None,
                    padding=Padding(top=0, bottom=0, left=0, right=0),
                ),
            ),
            Text(
                text="width=20,right=auto",
                style=Style(
                    span=Span(width=20, height=1),
                    margin=Margin(top=0, bottom=0, left=0, right="auto"),
                    border=Border(kind=BorderKind.LightRounded),
                    # border=None,
                    padding=Padding(top=0, bottom=0, left=0, right=0),
                ),
            ),
            Text(
                text="width=20,left=auto",
                style=Style(
                    span=Span(width=20, height=1),
                    margin=Margin(top=0, bottom=0, left="auto", right=0),
                    border=Border(kind=BorderKind.LightRounded),
                    # border=None,
                    padding=Padding(top=0, bottom=0, left=0, right=0),
                ),
            ),
            Text(
                text="width=20,rl=auto",
                style=Style(
                    span=Span(width=20, height=1),
                    margin=Margin(top=0, bottom=0, left="auto", right="auto"),
                    border=Border(kind=BorderKind.LightRounded),
                    # border=None,
                    padding=Padding(top=0, bottom=0, left=0, right=0),
                ),
            ),
        ],
        style=Style(
            border=Border(kind=BorderKind.Heavy),
        ),
    ),
)
t.layout(b)
# pprint(t.dict())
p = paint(t)
# pprint(p)
# pprint(t.dims.margin_rect().dict())
print(debug(p, t.dims.margin_rect()))
