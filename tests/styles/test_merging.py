from pprint import pprint

import pytest

from reprisal.styles import Border, Span, Style
from reprisal.styles.styles import BorderKind, CellStyle, Color, Flex


@pytest.mark.parametrize(
    ["left", "right", "expected"],
    [
        (Style(), Style(), Style()),
        (Style(span=Span(width=5)), Style(), Style(span=Span(width=5))),
        (
            Style(border=Border(style=CellStyle(bold=True))),
            Style(),
            Style(border=Border(style=CellStyle(bold=True))),
        ),
        (
            Style(),
            Style(border=Border(style=CellStyle(bold=True))),
            Style(border=Border(style=CellStyle(bold=True))),
        ),
        (
            Style(border=Border(style=CellStyle(bold=False))),
            Style(border=Border(style=CellStyle(bold=True))),
            Style(border=Border(style=CellStyle(bold=True))),
        ),
        (
            Style(border=Border(style=CellStyle(bold=True))),
            Style(border=Border(style=CellStyle(bold=False))),
            Style(border=Border(style=CellStyle(bold=False))),
        ),
        (
            Style(),
            Style(border=Border(style=CellStyle(foreground=Color.from_name("green")))),
            Style(border=Border(style=CellStyle(foreground=Color.from_name("green")))),
        ),
        (
            Style(border=Border(kind=BorderKind.LightRounded)),
            Style(border=Border(style=CellStyle(foreground=Color.from_name("green")))),
            Style(border=Border(kind=BorderKind.LightRounded, style=CellStyle(foreground=Color.from_name("green")))),
        ),
        (
            Style(border=Border(style=CellStyle(foreground=Color.from_name("green")))),
            Style(border=Border(kind=BorderKind.LightRounded)),
            Style(border=Border(kind=BorderKind.LightRounded, style=CellStyle(foreground=Color.from_name("green")))),
        ),
        (
            Style(),
            Style(span=Span(width=5)),
            Style(span=Span(width=5)),
        ),
        (
            Style(span=Span(width=5)),
            Style(),
            Style(span=Span(width=5)),
        ),
        (
            Style(layout=Flex(direction="row")),
            Style(layout=Flex(direction="column")),
            Style(layout=Flex(direction="column")),
        ),
        (
            Style(layout=Flex(direction="column")),
            Style(layout=Flex(direction="row")),
            Style(layout=Flex(direction="row")),
        ),
        (
            Style(layout=Flex(direction="row")),
            Style(layout=Flex(weight=None)),
            Style(layout=Flex(direction="row", weight=None)),
        ),
        (
            Style(layout=Flex(direction="column", weight=5)),
            Style(layout=Flex(direction="row")),
            Style(layout=Flex(direction="row", weight=5)),
        ),
    ],
)
def test_style_merging(left: Style, right: Style, expected: Style) -> None:
    print("Left:")
    pprint(left.dict(exclude_unset=True))
    print("\nRight:")
    pprint(right.dict(exclude_unset=True))
    assert (left | right).dict() == expected.dict()
