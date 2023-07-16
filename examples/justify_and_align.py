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


def content(justify_children: str, align_children: str, n: int) -> Paragraph:
    return Paragraph(
        content=dedent(
            f"""\
            n={n}

            j={justify_children}

            a={align_children}

            This is long enough text that it should wrap around,
            but not necessarily at the comma.
            """
        ),
        style=Style(
            # TODO: width=auto doesn't make sense if weight=None, combine?
            display=Flex(
                weight=None,
            ),
            span=Span(
                width=20,
                height="auto",
            ),
            border=Border(kind=BorderKind.Light),
        ),
    )


children = [
    Div(
        children=[content(justify_children, align_children, n=n) for n in range(3)],
        style=Style(
            display=Flex(
                direction="row",
                justify_children=justify_children,  # type: ignore[arg-type]
                align_children=align_children,  # type: ignore[arg-type]
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
            width=w,
            height=20 * len(children),
        ),
    ),
)
print(f"{len(children)=}")

t = build_layout_tree(root)
t.compute_layout()
# pprint(t.dict(exclude_defaults=True, include={"dims", "children"}))
p = paint_layout(t)
# pprint(t.dims.dict())
# for child in t.children:
#     pprint(child.dims.dict())
print(t.dims)
for child in t.children:
    print(child.dims)
print(debug_paint(p, t.dims.margin_rect()))
