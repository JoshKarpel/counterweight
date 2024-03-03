# Layout

## Box Model

Counterweight's layout system is roughly based on the
[CSS box model](https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/The_box_model).
When you build your application, you represent it as a hierarchy of nested elements.
The layout system constructs a mirrored nested hierarchy of layout boxes,
each of which has a size and position (calculated by the layout system).
Each layout box is composed of four **areas** or **rectangles**:

- **Content**: The area where the element's "content" is laid out.
  What the content actually is depends on the element's type.
  For example, a [`Div`'s][counterweight.elements.Div] content is its children,
  while a [`Text`'s][counterweight.elements.Text] content is its text.
- **Padding**: The area between the content and the border.
- **Border**: The area between the padding and the margin,
  with a border drawn from box-drawing characters.
- **Margin**: The area between the border and the next element.

The size, background color, and other display properties of each area are controlled via dedicated styles.
The example below shows how the four areas are laid out for a simple `Div` element.

```python
--8<-- "box_model.py:example"
```

![Box Model](../_examples/box-model.svg)

!!! tip "Terminal cells are not square!"

    Unlike in a web browser, where pixel coordinates in the `x` and `y` directions represent the same physical distance,
    terminal cell coordinates (which is what Counterweight uses) *are not square*:
    they are twice as tall as they are wide.

    Be careful with vertical padding and margin in particular,
    as they will appear to be twice as large as horizontal padding and margin,
    which can throw off your layout. Adding only horizontal padding/margin is often sufficient.
    Note how the example above uses twice as much horizontal padding/margin as vertical padding/margin
    in order to achieve a more equal aspect ratio.

## Positioning

### Relative Positioning

::: counterweight.styles.Relative

```python
--8<-- "relative_positioning.py:example"
```

![Relative Positioning](../_examples/relative-positioning.svg)

### Absolute Positioning

::: counterweight.styles.Absolute

```python
--8<-- "absolute_positioning.py:example"
```

![Absolute Positioning](../_examples/absolute-positioning.svg)

#### Controlling Overlapping with `z`

```python
--8<-- "z.py:example"
```

![Z Layers](../_examples/z.svg)


```python
--8<-- "absolute_positioning_insets.py:example"
```

![Absolute Positioning Insets](../_examples/absolute-positioning-insets.svg)


### Fixed Positioning

::: counterweight.styles.Fixed

```python
--8<-- "fixed_positioning.py:example"
```

![Fixed Positioning](../_examples/fixed-positioning.svg)
