# Styles

## Merging

Styles are merged using the `|` operator: `left | right`.
The result contains `left`'s values as the baseline, with `right`'s **non-default** values taking precedence.

This means style merging is **additive only**: a field that equals its default is treated as "not set" and does not override `left`.
For example, `CellStyle(bold=True) | CellStyle(bold=False)` produces `CellStyle(bold=True)` because `bold=False` is the default and is therefore not considered an explicit override.

This design keeps style composition predictable — utility constants like `text_bold` can be freely layered without accidentally clearing each other — but it means you cannot use a default value to explicitly clear a previously-set property.
Structure your components to avoid needing to reset style properties back to their defaults.

## API

::: counterweight.styles.Style

::: counterweight.styles.Color
::: counterweight.styles.CellStyle
