# Clipping

A box's content can be larger than the box.
Its overflow, as in CSS's [`overflow`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow),
decides whether what doesn't fit is drawn anyway or cut off.
This page covers cutting it off, and how a box draws on its parent's border when its parent cuts things off.

## Hiding overflow

By default a box's overflow is visible:
children that don't fit are drawn past its padding box, over its border and whatever lies beyond.
`overflow_hidden` clips them to its padding box instead,
so nothing inside the box is drawn outside its border.

```python
--8<-- "layout_clipping.py:hidden"
```

![Visible and hidden overflow](../assets/layout-clipping-hidden.svg)

Layout doesn't change: the clipped children are just as large, and only the part inside the box is drawn.
The constraint utilities, `length`, `percentage`, `ratio` and `fill`, hide their box's overflow,
so a constrained box always clips its children.

`overflow_clip` clips the same way.
The two differ in layout, as they do in CSS:
a flex item with `overflow_hidden` can shrink below its content's size,
while one with `overflow_clip` keeps the content's size as its minimum, as a visible one does
(see [Content sets a minimum size](how-layout-sizes-things.md#content-sets-a-minimum-size)).

## Clipping one axis

`overflow_x_hidden` clips only at the left and right of the padding box,
and `overflow_y_hidden` only at the top and bottom.
The `overflow_x_*` and `overflow_y_*` utilities each set one axis,
so they combine with each other, as `overflow_x_hidden | overflow_y_clip`.

```python
--8<-- "layout_clipping.py:one-axis"
```

![Clipping one axis at a time](../assets/layout-clipping-one-axis.svg)

## Clipping applies whatever the `z`

A clip cuts off everything inside the box, wherever it's positioned and however high its `z`,
as on the web: a raised menu inside a box that hides its overflow is cut off at the box's padding box.

```python
--8<-- "layout_clipping.py:raised"
```

![A raised menu clipped by its container](../assets/layout-clipping-raised.svg)

Nested boxes that clip combine: a box inside two of them is drawn only where both let it.

## Drawing on the parent's border

A [border title](../cookbook/border-titles.md) is positioned on its parent's border,
outside the padding box, so a parent that hides its overflow clips it away.
`clip_to_border` clips a box to its parent's border box instead,
so it can draw on the border and is still cut off at the border's outer edge.
`clip_to_padding` is the default.

```python
--8<-- "layout_clipping.py:clip-to"
```

![A title clipped to the padding box, and to the border box](../assets/layout-clipping-clip-to.svg)

A parent whose overflow is visible clips nothing, so the two agree there,
but a title that sets `clip_to_border` keeps working when its parent starts to clip.
CSS has no equivalent property: its
[`overflow-clip-margin`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow-clip-margin)
widens the clip for every child of the box that sets it,
where `clip_to` is set on the child, so a title can reach the border while the rest of the content stops at the padding box.

## Percentage insets and borders

Insets on an absolutely positioned box are measured from its parent's padding box, as in CSS,
so `inset_top=Percent(1.0)` puts the box's top edge at the bottom of the padding box,
which is the bottom border's row when the parent has a border.

```python
--8<-- "layout_clipping.py:percent-inset"
```

![A box at a percentage inset on its parent's border row](../assets/layout-clipping-percent-inset.svg)

## Clipping and the mouse

A box receives the mouse only where it's drawn.
Over a part of a box that's clipped away, mouse events go to whatever is drawn there instead,
[`use_hovered`](../hooks/use_hovered.md) reports the mouse outside the box,
and [`on_click`](../input-handling/handlers.md) doesn't click it.

[`use_rects`](../hooks/use_rects.md) still reports each box whole,
since a box that's partly clipped is still where layout put it.
Its `clip` is the region the box's ancestors let it draw in,
and its `visible` is the part of its border box inside that region, or `None` when none of it is.
