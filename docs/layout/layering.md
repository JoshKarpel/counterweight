# Layering

Most boxes sit where layout puts them, side by side.
Positioning moves a box off that spot, so it can overlap others,
and `z` decides which of the overlapping boxes is drawn on top.

## Relative positioning

`position_relative` with insets moves a box from where layout placed it,
without moving anything else: its siblings keep the space it would have taken.
Insets are measured in cells, and `inset_top(2)` moves the box down two rows.

```python
--8<-- "layout_layering.py:relative"
```

![Relative positioning](../assets/layout-relative.svg)

## Absolute positioning

`position_absolute` takes a box out of the flow:
its siblings are laid out as if it weren't there,
and its insets place it relative to its parent's padding box.

```python
--8<-- "layout_layering.py:absolute"
```

![Absolute positioning](../assets/layout-absolute.svg)

## Placing a box at an edge or corner

The `inset_*` utilities position a box absolutely at one of nine places in its parent.
Their `center` axes leave the insets on that axis unset,
which leaves the box where its parent's alignment puts it,
so they center only in a parent that centers its children, as this one does.
Margins push the box away from where it was placed.

```python
--8<-- "absolute_positioning_insets.py:example"
```

![The inset utilities](../assets/absolute-positioning-insets.svg)

## Controlling overlap with `z`

Where boxes overlap, the one with the higher `z` is drawn on top.
Boxes with equal `z` are drawn in the order they appear.

```python
--8<-- "z.py:example"
```

![Z layers](../assets/z.svg)

## A dialog centered over the app

To center a box over its parent, as CSS does,
position it absolutely with insets of 0, `auto` margins, and a fit-content size.
The insets make its whole parent the space to place it in,
the fit-content size keeps it as small as its content,
and the `auto` margins split the space left over evenly on each side,
whether or not the parent centers its children.
A margin paints nothing unless its element sets `margin_color`,
so the app's content shows around the dialog.
The dialog is drawn over the content because it comes after it;
a dialog that comes earlier in the tree needs a higher `z`.

An absolutely positioned box is always placed in its own parent, never a more distant ancestor or the screen,
so a dialog centers over the whole app only when it's a child of an element that fills the screen,
such as the root component's element here.
A dialog rendered deeper in the tree centers over its own parent.

```python
--8<-- "layout_layering.py:dialog"
```

![A dialog over the app](../assets/layout-dialog.svg)

!!! warning "Known issue: parents with a border, and grids"

    The layout engine, [Taffy](https://github.com/DioxusLabs/taffy), mismeasures `auto` margins
    on an absolutely positioned box in two kinds of parent.
    In a flex parent with a border, the dialog lands one cell right of and below center,
    because the space its margins split includes the parent's border.
    In a grid parent, the `auto` margins are ignored, so the dialog sits at the parent's top-left corner.
    A parent with padding and no border centers it correctly.

## A badge pinned to a corner

Negative insets reach past the parent's padding box onto its border.
`inset_top(-1)` puts a box on the top border, and `inset_right(-1)` on the right border.

```python
--8<-- "layout_layering.py:badge"
```

![Badges on borders](../assets/layout-badge.svg)
