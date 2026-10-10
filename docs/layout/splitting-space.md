# Splitting Space

Each split on this page can be built two ways.
With flexbox, each child carries its own share, through `grow`, `width` and the like.
With grid, the parent lists the shares as track sizes,
and children fill the tracks in order.
Both give the same screenshot.

The flexbox versions set `min_width(0)` (or `min_height(0)` in a `col`)
on every child that grows, so that content can't push a share wider than its due;
[Content sets a minimum size](how-layout-sizes-things.md#content-sets-a-minimum-size) explains why.
The grid versions get the same guarantee from their track sizes, as the last sections show.

## Equal shares

=== "Flexbox"

    ```python
    --8<-- "layout_splitting.py:equal-flex"
    ```

    ![Equal shares with flexbox](../assets/layout-split-equal-flex.svg)

=== "Grid"

    ```python
    --8<-- "layout_splitting.py:equal-grid"
    ```

    ![Equal shares with grid](../assets/layout-split-equal-grid.svg)

`grow(1)` also sets the flex basis to 0,
so every child starts from nothing and the whole row is shared out by the grow factors.

## A fixed sidebar beside a filling pane

=== "Flexbox"

    ```python
    --8<-- "layout_splitting.py:sidebar-flex"
    ```

    ![A sidebar with flexbox](../assets/layout-split-sidebar-flex.svg)

=== "Grid"

    ```python
    --8<-- "layout_splitting.py:sidebar-grid"
    ```

    ![A sidebar with grid](../assets/layout-split-sidebar-grid.svg)

## Ratios

Grow factors and fractions divide the space in proportion,
so `1` and `2` give the second pane twice the width of the first.

=== "Flexbox"

    ```python
    --8<-- "layout_splitting.py:ratio-flex"
    ```

    ![A 1:2 split with flexbox](../assets/layout-split-ratio-flex.svg)

=== "Grid"

    ```python
    --8<-- "layout_splitting.py:ratio-grid"
    ```

    ![A 1:2 split with grid](../assets/layout-split-ratio-grid.svg)

## Nested splits

With flexbox, a split inside a split is a container inside a container:
here a `col` that grows to fill the row, split in turn between two children.
With grid, one parent can hold both axes,
and a child spans tracks to cover the space a nested container would have.

=== "Flexbox"

    ```python
    --8<-- "layout_splitting.py:nested-flex"
    ```

    ![Nested splits with flexbox](../assets/layout-split-nested-flex.svg)

=== "Grid"

    ```python
    --8<-- "layout_splitting.py:nested-grid"
    ```

    ![Nested splits with grid](../assets/layout-split-nested-grid.svg)

## Content wider than its share

A bare `Fraction` track has the same floor as a flex item:
it is never narrower than its content's minimum size.
In the top grid below, two lines of unwrapped text push their columns past the grid's edge.
`Minmax(Length(0), Fraction(1))` (CSS's `minmax(0, 1fr)`) lowers the floor to zero,
so in the bottom grid the columns split the space and the text is cut off instead.

```python
--8<-- "layout_splitting.py:overflow-grid"
```

![Grid columns overflowing, and fixed](../assets/layout-split-overflow-grid.svg)

For the flexbox version of the same failure,
see [Content sets a minimum size](how-layout-sizes-things.md#content-sets-a-minimum-size).

## Percentages and gaps

A percentage is a share of the parent's whole content box, and gaps aren't subtracted first,
so two halves and a gap don't fit.
By default, children shrink to fit, so in the top row each half gives up one cell to the gap.
With `shrink(0)`, the halves keep their size and overflow the row by the width of the gap.
To split a row with gaps into equal shares, use `grow` as in [Equal shares](#equal-shares).

```python
--8<-- "layout_splitting.py:percent-gap"
```

![Percentages with a gap](../assets/layout-split-percent-gap.svg)
