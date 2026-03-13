# Common Layout Problems

Counterweight's layout engine is [Taffy](https://github.com/DioxusLabs/taffy),
a Rust implementation of CSS flexbox (and grid).
If you've used CSS flexbox before, most concepts transfer directly —
but a few defaults differ from what browsers do, and the terminal grid adds its own wrinkles.

---

## Children don't fill their container's width

**Symptom:** Elements are narrower than their parent even though you expect them to stretch.

**Cause:** Taffy does *not* default `align-items` to `stretch`.
Without explicitly requesting it, children are sized to their content on the cross axis.

**Fix:** Add `align_children_stretch` to every container whose children should fill its cross axis.

```python
# ✗ children hug their content width
Div(style=col)

# ✓ children fill the full width of the column
Div(style=col | align_children_stretch)
```

This is almost always needed on:

- The **root** container (`col | full | align_children_stretch`)
- Any intermediate `col` container whose `Text` children need a definite width for text wrapping

---

## `grow(1)` panels don't split the screen — they overflow instead

**Symptom:** Two sibling `Div`s with `grow(1)` both expand to their full content width
and overflow the row rather than sharing it equally.

**Cause:** This is a well-known CSS flexbox quirk (see
[Defensive CSS](https://defensivecss.dev/tip/flexbox-min-content-size/)).
Flex items have `min-width: auto` by default, which resolves to the item's
*min-content size* — the narrowest it can be without clipping content.
For a pane containing a long unwrapped text string, that minimum is the full string length.
Taffy honours this floor before distributing free space via `flex-grow`, so both panes
claim their full content width and the row overflows.

`flex-shrink` does **not** fix this. `flex-shrink: 1` is already the default, and shrink
factors are applied *after* minimums — an item will never shrink below `min-width`.

**Fix:** Add `min_width(0)` to each flex-grown pane to replace `auto` with an explicit zero
minimum, allowing the flex algorithm to freely distribute space:

```python
# ✗ each pane expands to content width and overflows
Div(style=row | align_children_stretch, children=[
    pane_a(),   # has grow(1) but no min_width(0)
    pane_b(),
])

# ✓ panes share the available width equally
Div(style=row | align_children_stretch, children=[
    pane_a(),   # has grow(1) | min_width(0)
    pane_b(),
])
```

The full pattern for an equal two-column split:

```python
# container
Div(
    style=col | full | align_children_stretch,
    children=[
        Div(
            style=row | grow(1) | align_children_stretch,
            children=[left_pane(), right_pane()],
        ),
    ],
)

# each pane
Div(style=grow(1) | min_width(0) | col | align_children_stretch | ...)
```

The same applies vertically: use `min_height(0)` on panes stacked in a `col` with `grow`.

---

## The root component doesn't fill the terminal

**Symptom:** Your root `Div` is only as large as its content instead of filling the screen.

**Cause:** `flex_grow` does not work on the root node in Taffy —
the root must declare its own size explicitly.

**Fix:** Use `full` (or `full_width` / `full_height`) on the root element:

```python
# ✗ root sizes to content
@component
def root() -> Div:
    return Div(style=col | align_children_stretch, children=[...])

# ✓ root fills the terminal
@component
def root() -> Div:
    return Div(style=col | full | align_children_stretch, children=[...])
```

---

## Text wrapping doesn't happen

**Symptom:** A `Text` element with `text_wrap_stable` (or `balance`/`pretty`) renders as a
single long line instead of wrapping.

**Cause:** Text wrapping requires the element to receive a *definite* width from layout.
This happens when the `Text`'s containing column has `align_children_stretch` and a known width.
Without it, the measure callback receives an indefinite available width and returns the
text's natural (unwrapped) width.

**Fix:** Ensure the `Text`'s parent column has `align_children_stretch`, and that the column
itself has a constrained width (see the two points above):

```python
Div(
    style=col | align_children_stretch | ...,  # ← gives Text a definite width
    children=[
        Text(
            content="A long paragraph of text...",
            style=text_wrap_stable,
        ),
    ],
)
```

---

## `text_justify_center` has no effect

**Symptom:** Centered text appears left-aligned.

**Cause:** `text_justify_center` (and `_right`) align text *within the element's width*.
If the element is only as wide as its content, there is no room to center into.

**Fix:** Same as above — ensure the `Text` element has a definite width wider than its content,
either from `align_children_stretch` on its parent or from an explicit `width(n)` / `full_width`.

---

## Terminal cells are not square

**Tip:** Terminal cells are roughly twice as tall as they are wide.
`pad_y(1)` adds one row above and below; `pad_x(1)` adds one column on each side —
but visually the horizontal padding looks half the size of the vertical padding.

Use twice as much horizontal padding as vertical to achieve a balanced appearance:

```python
# ✓ visually balanced padding
style=pad_x(2) | pad_y(1)
```
