import shutil
from textwrap import dedent

from structlog import get_logger

from reprisal.components import Div, Paragraph
from reprisal.layout import build_layout_tree
from reprisal.paint import debug_paint, paint_layout
from reprisal.styles import Border, BorderKind, Span, Style
from reprisal.styles.styles import Flex

logger = get_logger()

w, h = shutil.get_terminal_size()


def content(justify_children: str, align_children: str) -> Paragraph:
    return Paragraph(
        content=dedent(
            f"""\
            j={justify_children}

            a={align_children}

            This is long enough text that it should wrap around,
            but not necessarily at the comma.
            """
        ),
        style=Style(
            display=Flex(weight=None),
            span=Span(width=20, height="auto"),
            border=Border(kind=BorderKind.Light),
        ),
    )


children = [
    Div(
        children=[
            content(justify_children, align_children),
            content(justify_children, align_children),
            content(justify_children, align_children),
        ],
        style=Style(
            display=Flex(
                direction="row",
                justify_children=justify_children,
                align_children=align_children,
            ),
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
    for align_children in [
        "start",
        "center",
        "end",
        "stretch",
    ]
]

root = Div(
    children=children,
    style=Style(
        display=Flex(direction="column", align_children="stretch"),
        span=Span(
            width=w - 5,
            height=10 * len(children),
        ),
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
