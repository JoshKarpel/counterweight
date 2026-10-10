# Spacing and Borders

## The box model

Counterweight's layout follows the
[CSS box model](https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/The_box_model).
Every element's box is four nested rectangles:

- **Content**: where the element's content goes.
  A [`Div`'s][counterweight.elements.Div] content is its children,
  and a [`Text`'s][counterweight.elements.Text] content is its text.
- **Padding**: space between the content and the border.
- **Border**: the box-drawing characters around the padding.
- **Margin**: space between the border and the element's neighbors.

The example below colors each rectangle:

```python
--8<-- "box_model.py:example"
```

![The box model](../assets/box-model.svg)

!!! tip "Terminal cells are not square"

    Terminal cells are about twice as tall as they are wide,
    so one row of vertical padding or margin looks about as big as two columns of horizontal.
    The example above uses twice as much horizontal spacing as vertical for that reason,
    and horizontal spacing alone is often enough.

## Gap, margin and padding

All three put space around children, but they belong to different elements:

- `gap` is set on the parent, and puts space _between_ its children only.
- `margin` is set on a child, and puts space all around it, including at the ends of the row.
  Margins don't collapse into each other, so two children with `margin_x(1)` are two cells apart.
- `pad` is set on the parent, and puts space between its border and all of its children.

`margin_color` and `padding_color` color the margin and padding, in red and blue here.

```python
--8<-- "layout_spacing.py:gap-margin-pad"
```

![Gap, margin and padding](../assets/layout-gap-margin-pad.svg)

## Sharing borders between neighbors

`border_collapse` on a parent overlaps its children's borders by one cell,
so neighbors share a border instead of drawing two side by side.
Where the shared borders meet, [border healing](../cookbook/border-healing.md)
joins them with the right junction characters.

```python
--8<-- "layout_spacing.py:collapse"
```

![Collapsed borders](../assets/layout-border-collapse.svg)

## Borders on some sides

A border kind such as `border_light` reserves and draws all four sides.
To draw only some sides, follow it with `border_sides`, which sets every side, on or off.
The edge utilities such as `border_top` only turn sides _on_,
so after `border_light`, which already turned all four on, they change nothing.

```python
--8<-- "layout_spacing.py:sides"
```

![Borders on some sides](../assets/layout-border-sides.svg)

## Shortening edges next to missing sides

`border_contract(n)` stops each edge `n` cells short at an end next to a side that isn't drawn.

```python
--8<-- "layout_spacing.py:contract"
```

![Contracted borders](../assets/layout-border-contract.svg)
