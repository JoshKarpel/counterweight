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

## Scroll container children won't scroll

**Symptom:** A `use_scroll` container renders content but scrolling has no effect — the
content is stuck at the top and can't be moved.

**Cause:** `grow(1)` on a direct child of a scroll container makes that child fill the
viewport height exactly, leaving no overflow to scroll through.
`flex-grow` distributes free space *within* the container's allocated size; the child
never exceeds the viewport, so there is nothing to scroll.

**Fix:** Remove `grow(1)` from children inside scroll containers. Let them take their
natural content size so they can overflow the viewport:

```python
# ✗ text grows to fill viewport — content can never overflow, nothing to scroll
Div(
    style=size(10, 5) | scroll_style | col | align_children_stretch,
    children=[Text(content=long_text, style=grow(1) | text_wrap_none)],
)

# ✓ text takes its natural height — overflows the viewport and becomes scrollable
Div(
    style=size(10, 5) | scroll_style | col | align_children_stretch,
    children=[Text(content=long_text, style=text_wrap_none)],
)
```

---

## `auto_scroll_to_y` / `viewport_height` have no effect

**Symptom:** Passing `auto_scroll_to_y` to `use_scroll` does nothing, or `viewport_height`
in the returned `ScrollState` is the full terminal height instead of the scroll pane height.

**Cause:** `use_scroll` reads the component's dimensions via `use_rects()`, which returns the
top-level element of the *calling component* — not the inner `Div` that carries `scroll_style`.
If `use_scroll` is called in a component that returns an outer wrapper, `use_rects()` sees the
wrapper's size, not the scroll container's.

**Fix:** Move `use_scroll` into its own component whose top-level `return` value is the scroll
container `Div`:

```python
# ✗ use_scroll is in the outer component — use_rects() sees the full-screen div
@component
def root() -> Div:
    _, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True, auto_scroll_to_y=cursor)
    return Div(
        style=col | full | align_children_stretch,
        children=[
            Div(style=size(30, 20) | scroll_style | col | align_children_stretch, ...),
        ],
    )

# ✓ use_scroll is in the scroll-container component — use_rects() sees the pane size
@component
def my_pane(cursor: int) -> Div:
    _, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True, auto_scroll_to_y=cursor)
    return Div(style=size(30, 20) | scroll_style | col | align_children_stretch, ...)

@component
def root() -> Div:
    return Div(style=col | full | align_children_stretch, children=[my_pane(cursor)])
```

This same constraint applies to `auto_scroll_to_x`, `max_offset_x/y`, `ScrollState.scroll_to`,
and any direct use of `use_rects()` or `use_hovered()` — they all measure the calling
component's top-level element.

---

## Mouse scroll fights with cursor-follow scrolling

**Symptom:** You use `auto_scroll_to_y` (or `auto_scroll_to_x`) to keep a cursor row visible,
but mouse-wheel scrolling has no effect — the viewport immediately snaps back.

**Cause:** `auto_scroll_to_y` runs on every render. If the cursor is at the bottom edge,
any upward mouse scroll would put the cursor off-screen, so auto-scroll reverts it instantly.

**Fix:** Make mouse scroll move the cursor instead of the viewport.
`auto_scroll_to_y` then follows the cursor naturally, and there is no conflict:

```python
@component
def my_list(items: list[str], cursor: int, set_cursor: Setter[int]) -> Div:
    state, scroll_style, on_mouse, on_key = use_scroll(scroll_y=True, auto_scroll_to_y=cursor)

    def on_key_handler(event: KeyPressed) -> AnyControl | None:
        if event.key == "down":
            set_cursor(lambda i: min(i + 1, len(items) - 1))
            return None
        elif event.key == "up":
            set_cursor(lambda i: max(i - 1, 0))
            return None
        return on_key(event)

    def on_mouse_handler(event: MouseEvent) -> AnyControl | None:
        if isinstance(event, MouseScrolledDown):
            set_cursor(lambda i: min(i + 1, len(items) - 1))
            return StopPropagation()
        elif isinstance(event, MouseScrolledUp):
            set_cursor(lambda i: max(i - 1, 0))
            return StopPropagation()
        return None

    return Div(
        style=... | scroll_style | col | align_children_stretch,
        on_key=on_key_handler,
        on_mouse=on_mouse_handler,
        children=[...],
    )
```

Note: use lambdas in `set_cursor` (not `set_cursor(cursor + 1)`) so that rapidly queued
key/scroll events each increment from the actual current value rather than from the
stale render-time snapshot.

Use `auto_scroll_to_y` without overriding mouse scroll only when you want a read-only
indicator that always tracks some external value and mouse-wheel independence is not needed.

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
