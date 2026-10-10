import dataclasses
from dataclasses import dataclass

import pytest
import waxy

from counterweight.styles.styles import (
    CELL_STYLE_DEFAULTS,
    STYLE_DEFAULTS,
    BorderKind,
    CellStyle,
    Color,
    Style,
    StyleFragment,
    resolve_cell_style,
    resolve_style,
)
from counterweight.styles.utilities import border_heavy, inset_left, inset_top, position_absolute, position_relative


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    (
        (Style(), Style(), Style()),
        (
            Style(border_style=CellStyle(bold=True)),
            Style(),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(),
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(border_style=CellStyle(bold=False)),
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(bold=False)),
            Style(border_style=CellStyle(bold=False)),
        ),
        (
            Style(),
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
        ),
        (
            Style(border_kind=BorderKind.LightRounded),
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
            Style(border_kind=BorderKind.LightRounded, border_style=CellStyle(foreground=Color.from_name("green"))),
        ),
        (
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
            Style(border_kind=BorderKind.LightRounded),
            Style(border_kind=BorderKind.LightRounded, border_style=CellStyle(foreground=Color.from_name("green"))),
        ),
        (
            Style(border_kind=BorderKind.Heavy),
            Style(border_kind=BorderKind.Double),
            Style(border_kind=BorderKind.Double),
        ),
        (
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(italic=True)),
            Style(border_style=CellStyle(bold=True, italic=True)),
        ),
    ),
)
def test_style_merging(left: Style, right: Style, expected: Style) -> None:
    assert (left | right) == expected


def test_layout_retained_from_left() -> None:
    result = Style(layout=waxy.Style(size_width=waxy.Length(5))) | Style()
    assert result.layout.size_width == waxy.Length(5)


def test_layout_retained_from_right() -> None:
    result = Style() | Style(layout=waxy.Style(size_width=waxy.Length(5)))
    assert result.layout.size_width == waxy.Length(5)


def test_layout_right_overrides_left() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)) | Style(
        layout=waxy.Style(flex_direction=waxy.FlexDirection.Column)
    )
    assert result.layout.flex_direction == waxy.FlexDirection.Column


def test_layout_left_overrides_right() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Column)) | Style(
        layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)
    )
    assert result.layout.flex_direction == waxy.FlexDirection.Row


def test_layout_merges_independent_fields() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)) | Style(layout=waxy.Style(flex_grow=0.0))
    assert result.layout.flex_direction == waxy.FlexDirection.Row
    assert result.layout.flex_grow == 0.0


def test_layout_merges_left_non_default_retained() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Column, flex_grow=5.0)) | Style(
        layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)
    )
    assert result.layout.flex_direction == waxy.FlexDirection.Row
    assert result.layout.flex_grow == 5.0


def test_layout_merge_with_visual() -> None:
    """Layout fields merge independently from visual fields."""
    result = position_relative | inset_left(3) | inset_top(5) | border_heavy
    assert result.border_kind == BorderKind.Heavy
    assert result.layout.position == waxy.Position.Relative
    assert result.layout.inset_left == waxy.Length(3)
    assert result.layout.inset_top == waxy.Length(5)
    assert result.layout.border_top == waxy.Length(1)


def test_absolute_merge_with_visual() -> None:
    result = position_absolute | inset_left(3) | inset_top(5) | border_heavy
    assert result.border_kind == BorderKind.Heavy
    assert result.layout.position == waxy.Position.Absolute
    assert result.layout.inset_left == waxy.Length(3)
    assert result.layout.inset_top == waxy.Length(5)
    assert result.layout.border_top == waxy.Length(1)


def test_styles_with_different_layouts_are_not_equal() -> None:
    assert Style(layout=waxy.Style(flex_grow=1)) != Style(layout=waxy.Style(flex_grow=2))


def test_styles_with_equal_layouts_are_equal_and_hash_equal() -> None:
    left = Style(layout=waxy.Style(flex_grow=3))
    right = Style(layout=waxy.Style(flex_grow=3))

    assert left == right
    assert hash(left) == hash(right)


@dataclass(frozen=True, slots=True)
class CollidingFragment(StyleFragment):
    value: int = 0

    def __hash__(self) -> int:
        return 7


def test_merge_cache_distinguishes_fragments_whose_hashes_collide() -> None:
    first = CollidingFragment(value=3) | CollidingFragment(value=5)
    second = CollidingFragment(value=11) | CollidingFragment(value=13)

    assert (first, second) == (CollidingFragment(value=5), CollidingFragment(value=13))


RED = Color.from_name("red")
GREEN = Color.from_name("green")
BLUE = Color.from_name("blue")

EXPLICIT_DEFAULT_CELL_STYLE = CellStyle(
    foreground=CELL_STYLE_DEFAULTS.foreground,
    background=CELL_STYLE_DEFAULTS.background,
    bold=CELL_STYLE_DEFAULTS.bold,
    dim=CELL_STYLE_DEFAULTS.dim,
    italic=CELL_STYLE_DEFAULTS.italic,
    underline=CELL_STYLE_DEFAULTS.underline,
    strikethrough=CELL_STYLE_DEFAULTS.strikethrough,
)

# Each field, a style that sets it to a non-default value, and one that sets it to its default.
STYLE_FIELD_CASES: tuple[tuple[str, Style, Style], ...] = (
    ("z", Style(z=5), Style(z=STYLE_DEFAULTS.z)),
    ("margin_color", Style(margin_color=RED), Style(margin_color=STYLE_DEFAULTS.margin_color)),
    ("padding_color", Style(padding_color=GREEN), Style(padding_color=STYLE_DEFAULTS.padding_color)),
    ("content_color", Style(content_color=BLUE), Style(content_color=STYLE_DEFAULTS.content_color)),
    ("border_kind", Style(border_kind=BorderKind.Heavy), Style(border_kind=STYLE_DEFAULTS.border_kind)),
    ("border_style", Style(border_style=CellStyle(bold=True)), Style(border_style=EXPLICIT_DEFAULT_CELL_STYLE)),
    ("border_contract", Style(border_contract=2), Style(border_contract=STYLE_DEFAULTS.border_contract)),
    ("text_style", Style(text_style=CellStyle(italic=True)), Style(text_style=EXPLICIT_DEFAULT_CELL_STYLE)),
    ("text_justify", Style(text_justify="center"), Style(text_justify=STYLE_DEFAULTS.text_justify)),
    ("text_wrap", Style(text_wrap="pretty"), Style(text_wrap=STYLE_DEFAULTS.text_wrap)),
)

CELL_STYLE_FIELD_CASES: tuple[tuple[str, CellStyle, CellStyle], ...] = (
    ("foreground", CellStyle(foreground=RED), CellStyle(foreground=CELL_STYLE_DEFAULTS.foreground)),
    ("background", CellStyle(background=GREEN), CellStyle(background=CELL_STYLE_DEFAULTS.background)),
    ("bold", CellStyle(bold=True), CellStyle(bold=CELL_STYLE_DEFAULTS.bold)),
    ("dim", CellStyle(dim=True), CellStyle(dim=CELL_STYLE_DEFAULTS.dim)),
    ("italic", CellStyle(italic=True), CellStyle(italic=CELL_STYLE_DEFAULTS.italic)),
    ("underline", CellStyle(underline=True), CellStyle(underline=CELL_STYLE_DEFAULTS.underline)),
    ("strikethrough", CellStyle(strikethrough=True), CellStyle(strikethrough=CELL_STYLE_DEFAULTS.strikethrough)),
)


def init_field_names(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls) if f.init}


def test_style_cases_cover_every_field() -> None:
    assert {name for name, _, _ in STYLE_FIELD_CASES} == init_field_names(Style) - {"layout"}


def test_cell_style_cases_cover_every_field() -> None:
    assert {name for name, _, _ in CELL_STYLE_FIELD_CASES} == init_field_names(CellStyle)


@pytest.mark.parametrize(("name", "non_default", "explicit_default"), STYLE_FIELD_CASES)
def test_style_explicit_default_overrides_non_default(name: str, non_default: Style, explicit_default: Style) -> None:
    assert getattr(resolve_style(non_default | explicit_default), name) == getattr(STYLE_DEFAULTS, name)


@pytest.mark.parametrize(("name", "non_default", "explicit_default"), STYLE_FIELD_CASES)
def test_style_unset_field_keeps_left_value(name: str, non_default: Style, explicit_default: Style) -> None:
    resolved = getattr(resolve_style(non_default | Style()), name)

    assert resolved == getattr(resolve_style(non_default), name)
    assert resolved != getattr(STYLE_DEFAULTS, name)


@pytest.mark.parametrize(("name", "non_default", "explicit_default"), CELL_STYLE_FIELD_CASES)
def test_cell_style_explicit_default_overrides_non_default(
    name: str, non_default: CellStyle, explicit_default: CellStyle
) -> None:
    assert getattr(resolve_cell_style(non_default | explicit_default), name) == getattr(CELL_STYLE_DEFAULTS, name)


@pytest.mark.parametrize(("name", "non_default", "explicit_default"), CELL_STYLE_FIELD_CASES)
def test_cell_style_unset_field_keeps_left_value(
    name: str, non_default: CellStyle, explicit_default: CellStyle
) -> None:
    resolved = getattr(resolve_cell_style(non_default | CellStyle()), name)

    assert resolved == getattr(resolve_cell_style(non_default), name)
    assert resolved != getattr(CELL_STYLE_DEFAULTS, name)


def test_resolving_empty_style_gives_defaults() -> None:
    assert resolve_style(Style()) == STYLE_DEFAULTS


def test_resolving_empty_cell_style_gives_defaults() -> None:
    assert resolve_cell_style(CellStyle()) == CELL_STYLE_DEFAULTS


def test_resolving_against_resolved_base_matches_merging_first() -> None:
    base = CellStyle(foreground=RED, bold=True)
    overlay = CellStyle(background=BLUE, bold=False)

    assert resolve_cell_style(overlay, resolve_cell_style(base)) == resolve_cell_style(base | overlay)
