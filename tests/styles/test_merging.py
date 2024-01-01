import pytest

from counterweight.styles import Border, Style
from counterweight.styles.styles import Absolute, BorderKind, CellStyle, Color, Flex, Relative, Span
from counterweight.styles.utilities import absolute, border_heavy, relative


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    (
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
        (
            relative(x=3, y=5),
            border_heavy,
            Style(layout=Flex(position=Relative(x=3, y=5)), border=Border(kind=BorderKind.Heavy)),
        ),
        (
            border_heavy,
            relative(x=3, y=5),
            Style(layout=Flex(position=Relative(x=3, y=5)), border=Border(kind=BorderKind.Heavy)),
        ),
        (
            absolute(x=3, y=5),
            border_heavy,
            Style(layout=Flex(position=Absolute(x=3, y=5)), border=Border(kind=BorderKind.Heavy)),
        ),
        (
            border_heavy,
            absolute(x=3, y=5),
            Style(layout=Flex(position=Absolute(x=3, y=5)), border=Border(kind=BorderKind.Heavy)),
        ),
    ),
)
def test_style_merging(left: Style, right: Style, expected: Style) -> None:
    print(f"{left.mergeable_dump()=}")
    print()
    print(f"{right.mergeable_dump()=}")
    print()
    print(f"{(left|right).mergeable_dump()=}")
    print()
    print(f"{expected.mergeable_dump()=}")
    assert (left | right).model_dump() == expected.model_dump()
