import shutil

from structlog import get_logger

from reprisal.components import Div, Paragraph
from reprisal.layout import build_layout_tree
from reprisal.paint import debug_paint, paint_layout
from reprisal.styles import Border, BorderKind, Span, Style
from reprisal.styles.styles import Flex

logger = get_logger()

w, h = shutil.get_terminal_size()


children = [
    *(
        Div(
            children=[
                Paragraph(
                    content=f"{align_children} weight=1",
                    style=Style(
                        display=Flex(weight=1),
                        span=Span(width="auto", height=1 if align_children != "stretch" else "auto"),
                        border=Border(kind=BorderKind.Light),
                    ),
                ),
                Paragraph(
                    content=f"{align_children} weight=2",
                    style=Style(
                        display=Flex(weight=2),
                        span=Span(width="auto", height=1 if align_children != "stretch" else "auto"),
                        border=Border(kind=BorderKind.Light),
                    ),
                ),
                Paragraph(
                    content=f"{align_children} weight=3",
                    style=Style(
                        display=Flex(weight=3),
                        span=Span(width="auto", height=1 if align_children != "stretch" else "auto"),
                        border=Border(kind=BorderKind.Light),
                    ),
                ),
            ],
            style=Style(
                display=Flex(direction="row", align_children=align_children),
                border=Border(kind=BorderKind.Heavy),
            ),
        )
        for align_children in [
            "start",
            "center",
            "end",
            "stretch",
        ]
    ),
    *(
        Div(
            children=[
                Paragraph(
                    content=f"{justify_children}",
                    style=Style(
                        display=Flex(weight=None),
                        span=Span(width="auto", height=1),
                        border=Border(kind=BorderKind.Light),
                    ),
                ),
                Paragraph(
                    content=f"{justify_children}",
                    style=Style(
                        display=Flex(weight=None),
                        span=Span(width="auto", height=1),
                        border=Border(kind=BorderKind.Light),
                    ),
                ),
                Paragraph(
                    content=f"{justify_children}",
                    style=Style(
                        display=Flex(weight=None),
                        span=Span(width="auto", height=1),
                        border=Border(kind=BorderKind.Light),
                    ),
                ),
            ],
            style=Style(
                display=Flex(direction="row", justify_children=justify_children, align_children="center"),
                border=Border(kind=BorderKind.Heavy),
            ),
        )
        for justify_children in [
            "start",
            "center",
            "end",
            "space-between",
            "space-around",
            "space-evenly",
        ]
    ),
]
root = Div(
    children=children,
    style=Style(
        display=Flex(direction="column", align_children="stretch"),
        span=Span(width=w - 5, height=10 * len(children)),
        border=Border(kind=BorderKind.Heavy),
    ),
)
t = build_layout_tree(root)
t.flex()
# pprint(t.dict(exclude_defaults=True, include={"dims", "children"}))
p = paint_layout(t)
# pprint(t.dims.dict())
# for child in t.children:
#     pprint(child.dims.dict())
print(debug_paint(p, t.dims.margin_rect()))
