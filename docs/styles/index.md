# Styles

## Merging

Styles are merged using the `|` operator: `left | right`.
Every field starts out unset (the `counterweight.styles.UNSET` sentinel),
and the result takes `right`'s value for every field `right` sets, and `left`'s value otherwise.

A field set to its default value is still set, so it overrides `left`.
`CellStyle(bold=True) | CellStyle(bold=False)` is `CellStyle(bold=False)`,
`border | border_none` draws no border,
and `text_justify_center | text_justify_left` justifies left.
Utilities set only the fields they are about, so they layer without clearing each other:
`text_color("red", 500) | text_bg("slate", 900)` is red text on a slate background.

[`merge`][counterweight.styles.merge] does the same for any number of `Style`s:
`merge(a, b, c)` is `a | b | c`.
It skips `None` wherever it appears, so a style that only sometimes applies can be passed inline,
as in `merge(base, hover_style if hovered else None)`, and `merge()` is an empty `Style()`.

Nested styles merge field by field too:
`Style(text_style=CellStyle(bold=True)) | Style(text_style=CellStyle(italic=True))`
is both bold and italic.
`layout` follows the same rule, field by field.

Any color a style holds can be a [gradient](gradients.md) instead, which colors each cell by where it is in its box.

When an element is drawn, any field still unset takes its default from
[`STYLE_DEFAULTS`][counterweight.styles.STYLE_DEFAULTS]
and [`CELL_STYLE_DEFAULTS`][counterweight.styles.CELL_STYLE_DEFAULTS].

## API

::: counterweight.styles.Style
::: counterweight.styles.merge

::: counterweight.styles.Color
::: counterweight.styles.IndexedColor
::: counterweight.styles.TerminalDefault
::: counterweight.styles.TERMINAL_DEFAULT
::: counterweight.styles.AnyColor
::: counterweight.styles.DEFAULT_PALETTE
::: counterweight.styles.CellStyle
::: counterweight.styles.STYLE_DEFAULTS
::: counterweight.styles.CELL_STYLE_DEFAULTS
