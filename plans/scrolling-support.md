# Plan: Scrolling Support (Vertical and Horizontal)

## Context

Counterweight has no way to display content that overflows a container's bounds. If a `Div` has
fixed dimensions (e.g. `height(10)`) and its children collectively need 30 rows, only the first 10
rows are visible — the rest paint off-screen or overlap siblings. There is no clipping, no scroll
offset, and no way for users to scroll.

This is one of the most requested capabilities for any TUI framework. Lists, log viewers, file
browsers, help text — all require scrolling.

### What taffy/waxy already provides

Taffy (via waxy) has `overflow_x`, `overflow_y` on `waxy.Style` with values `Visible`, `Hidden`,
`Clip`, and `Scroll`. With `overflow_y=Scroll` and child `flex_shrink=0`, taffy correctly:
- Constrains the **parent's box** to its declared size (e.g. 10 rows)
- Allows the **child** to keep its natural/min size (e.g. 30 rows)
- Reports `layout.content_size` on the parent as the full scrollable extent (30)
- Reports `layout.size` on the parent as the visible viewport (10)

Taffy also provides `scrollbar_width` for reserving space for a scrollbar gutter.

What taffy does **not** do: clipping, scroll offset application, or painting. Those are the
rendering engine's job — i.e., counterweight's.

---

## Design

### Overview

Scrolling requires changes at four levels:

1. **Layout** — tell taffy about overflow; extract scrollable extent from layout results
2. **Scroll state** — track scroll offsets per-container; provide a `use_scroll` hook
3. **Paint** — apply scroll offsets when painting children; clip to container bounds
4. **Input** — route mouse scroll events to the correct container; support keyboard scrolling

### How CSS/browsers do scrolling (reference model)

In CSS, `overflow: scroll` or `overflow: auto` on a container:
1. The container's box is sized normally (its own width/height constraints)
2. Children are laid out in full (they can exceed the container)
3. The container clips rendering to its **padding box**
4. A scroll offset (controlled by `scrollTop`/`scrollLeft`) shifts the visible window over the content
5. Scroll events (mouse wheel, keyboard) update the offset
6. Scrollbars are optionally rendered in the gutter

We follow this model closely.

---

## Key Design Decisions

### 1. Scroll offset is counterweight state, not taffy state

Taffy computes static layout. It does not know about scroll offsets — it just reports that a
container can scroll (via overflow mode and `content_size > size`). The scroll offset must live in
counterweight, stored per scroll-container element, and applied during painting.

The offset is stored in the `ShadowNode.hooks` for the component that owns the scroll container,
via a new `use_scroll` hook.

### 2. Clipping at the paint level via `clip_rect`

Today, `paint_element` produces `Paint` (a `dict[Position, P]`) with no awareness of parent
bounds. Elements paint wherever their resolved rects say, even if that's outside the terminal.

For scrolling, we need to:
- **Offset** child positions by the scroll amount (subtract `scroll_x` from x, `scroll_y` from y)
- **Clip** painted cells to the parent container's padding rect

Two implementation approaches:

**Option A: Clip during paint generation.** Pass a `clip_rect: waxy.Rect | None` into
`paint_element` / `paint_layout`. When `clip_rect` is set, skip any cell whose position falls
outside it. This is simple and efficient — cells are never created only to be discarded.

**Option B: Clip during paint merge.** Generate paint normally, then filter in `paint_layout`.
Simpler to implement but generates wasted cells.

**Decision:** Option A. The paint functions already operate on absolute positions, so adding a
clip check is straightforward. The cost is passing one extra parameter through the paint pipeline.

### 3. Scroll offset application during layout extraction

The scroll offset shifts where children appear *visually*, not where they are *logically*.
We apply it in `_extract_layout`: when walking a scroll container's children, subtract the
container's `(scroll_x, scroll_y)` from `abs_x`/`abs_y` before recursing. This means child
`ResolvedLayout` rects reflect their actual screen position (post-scroll), so paint and
hit-testing work without further adjustment.

### 4. `use_scroll` hook API

```python
@dataclass(frozen=True, slots=True)
class ScrollState:
    offset_x: int          # current horizontal scroll offset (0 = fully left)
    offset_y: int          # current vertical scroll offset (0 = fully top)
    max_offset_x: int      # maximum meaningful scroll offset (content_width - viewport_width)
    max_offset_y: int      # maximum meaningful scroll offset (content_height - viewport_height)
    viewport_width: int    # visible width (container padding box)
    viewport_height: int   # visible height (container padding box)
    content_width: int     # total scrollable width
    content_height: int    # total scrollable height

def use_scroll(
    scroll_x: bool = False,
    scroll_y: bool = True,
) -> tuple[ScrollState, Style]:
```

The hook returns:
- `ScrollState` — the current scroll position and bounds (read-only snapshot)
- `Style` — a style that must be merged onto the scroll container's element; it sets
  `overflow_x`/`overflow_y` on `waxy.Style` and a marker that the layout/paint system reads

The hook internally calls `use_state` for the offset and `use_rects` for viewport dimensions.
The scroll state is updated by the framework in response to mouse scroll events and keyboard
input — the component does not need to wire up event handlers manually.

**Why return a `Style`?** The alternative is adding `overflow` fields to `Div`/`Text` directly.
Returning a style keeps elements simple and follows the existing pattern where layout behavior is
configured via style merging. The style also carries an internal marker (a new `Style` field) that
the layout system reads to identify scroll containers.

### 5. Framework-managed scroll events

Scroll events (mouse wheel, arrow keys in a focused scroll container) are handled by the framework,
not by user `on_mouse` handlers. This avoids every scrollable component needing boilerplate event
wiring.

In `app.py`, when a `MouseScrolledUp` or `MouseScrolledDown` event arrives:
1. Walk `elements_and_layouts` (in reverse z-order, same as existing mouse dispatch)
2. Find the innermost scroll container whose border rect contains the mouse position
3. Adjust that container's scroll offset

This requires knowing which elements are scroll containers. The layout step already identifies
them (see §6 below); we store a mapping from element identity to scroll state setter.

### 6. `ResolvedLayout` gains scroll metadata

```python
@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: waxy.Rect
    padding: waxy.Rect
    border: waxy.Rect
    margin: waxy.Rect
    order: int
    # New fields:
    scroll_container: bool = False        # True if this element is a scroll container
    content_size: waxy.Size | None = None # full content size (from taffy) if scroll_container
    scroll_offset_x: int = 0             # applied scroll offset for painting
    scroll_offset_y: int = 0
```

### 7. No visual scrollbars in v1

Scrollbars (the visual indicator showing scroll position) are a nice-to-have but add significant
complexity: they need to be painted in the gutter, respond to mouse drag, and update dynamically.
The first version ships without visible scrollbars.

Users can build their own scrollbar indicators using `ScrollState.offset_y` and
`ScrollState.max_offset_y` if needed. Taffy's `scrollbar_width` can reserve gutter space for
a future built-in scrollbar.

### 8. Clip rect propagation for nested scroll containers

Scroll containers can nest. A scrollable list inside a scrollable panel should clip to the
*intersection* of both clip rects. During `_extract_layout`, we pass a `clip_rect` parameter
that narrows as we enter nested scroll containers:

```python
def _extract_layout(tree, node_id, node_map, abs_x, abs_y, results, clip_rect=None):
    ...
    if is_scroll_container:
        child_clip = padding_rect
        if clip_rect is not None:
            child_clip = intersect_rects(clip_rect, child_clip)
    else:
        child_clip = clip_rect
    for child_node_id in tree.children(node_id):
        _extract_layout(tree, child_node_id, node_map, ..., clip_rect=child_clip)
```

---

## Implementation Steps

### Step 1: Add scroll state infrastructure to hooks

**File:** `src/counterweight/hooks/hooks.py`

Add `ScrollState` dataclass and `use_scroll` hook function.

`use_scroll` internally:
- Calls `use_state((0, 0))` for the scroll offset
- Calls `use_rects()` to get viewport dimensions (from previous frame, same as `use_hovered`)
- Returns `ScrollState` (computed from rects + offset) and a `Style` with overflow set
- Registers a scroll-state setter in a context var (similar to `use_mouse_listeners`)

**File:** `src/counterweight/hooks/impls.py`

Add `scroll_setters` tracking (a dict mapping component identity to offset setter) to `Hooks`
or a context var, so the event loop can find the right setter for a scroll container.

**File:** `src/counterweight/_context_vars.py`

Add `current_scroll_listeners` context var — a mapping from element identity to scroll-offset
setter, populated by `use_scroll` during render and read by the event loop.

### Step 2: Propagate scroll offset through layout

**File:** `src/counterweight/layout.py`

Modify `_extract_layout` to:
1. Detect scroll containers: check `waxy.Style.overflow_x`/`overflow_y` on the element's style
2. Read the scroll offset from the shadow node's hooks (via a new field or a mapping)
3. When recursing into a scroll container's children, subtract `(scroll_x, scroll_y)` from
   `(abs_x, abs_y)` — this shifts children upward/leftward by the scroll amount
4. Read `layout.content_size` from taffy and store it on `ResolvedLayout`
5. Pass and intersect `clip_rect` for nested containers

Modify `ResolvedLayout` to include scroll metadata fields.

### Step 3: Clip during painting

**File:** `src/counterweight/paint.py`

Modify `paint_layout` to accept and propagate clip rects. Modify `paint_element` (and its
sub-functions `_paint_text`, `paint_border`, `paint_edge`, `fill_rect`) to accept an optional
`clip_rect` and skip cells outside it.

The clip rect is the **padding rect** of the scroll container ancestor (or the intersection of
all ancestor scroll container padding rects for nested scrolling).

Since many paint functions are `@lru_cache`d, the clip rect must be part of the cache key.
For `fill_rect` and `paint_edge`, this means adding a `clip: waxy.Rect | None` parameter.
This slightly reduces cache hit rates but is unavoidable.

**Alternative considered:** Instead of clipping during paint, clip during `paint_layout`'s merge
step — after generating all paints, filter out positions outside the clip rect. This avoids
changing cached paint functions but wastes work generating cells that are immediately discarded.
For large scroll containers with small viewports (e.g. a 1000-item list in a 20-row window),
Option A (clip during generation) is significantly more efficient.

### Step 4: Route scroll events in the event loop

**File:** `src/counterweight/app.py`

In the `MouseScrolledDown` / `MouseScrolledUp` handling:
1. After existing `on_mouse` dispatch, check for scroll containers at the mouse position
2. Find the innermost scroll container whose border rect contains the event position
3. Call that container's scroll-offset setter with the new offset (clamped to `[0, max_offset]`)
4. This triggers a `StateSet` event, causing a re-render with the updated scroll position

For keyboard scrolling: when a focused element is inside a scroll container, arrow keys
(or Page Up/Down) adjust the scroll offset. This requires focus tracking, which counterweight
does not currently have — defer keyboard scrolling to a future step.

### Step 5: Style utilities for overflow

**File:** `codegen/generate_utilities.py` → `src/counterweight/styles/utilities.py`

Add generated overflow utilities:

```python
overflow_visible = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Visible, overflow_y=waxy.Overflow.Visible))
overflow_hidden = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Hidden, overflow_y=waxy.Overflow.Hidden))
overflow_clip = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Clip, overflow_y=waxy.Overflow.Clip))
overflow_scroll = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Scroll, overflow_y=waxy.Overflow.Scroll))
overflow_x_visible = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Visible))
overflow_x_hidden = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Hidden))
overflow_x_clip = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Clip))
overflow_x_scroll = Style(layout=waxy.Style(overflow_x=waxy.Overflow.Scroll))
overflow_y_visible = Style(layout=waxy.Style(overflow_y=waxy.Overflow.Visible))
overflow_y_hidden = Style(layout=waxy.Style(overflow_y=waxy.Overflow.Hidden))
overflow_y_clip = Style(layout=waxy.Style(overflow_y=waxy.Overflow.Clip))
overflow_y_scroll = Style(layout=waxy.Style(overflow_y=waxy.Overflow.Scroll))
```

These are useful even without `use_scroll` — `overflow_hidden` / `overflow_clip` enable
content clipping without scrolling (useful for text truncation, masked overlays, etc.).

### Step 6: `use_scroll` populates scroll metadata on hooks

**File:** `src/counterweight/hooks/impls.py`

Add a `scroll_offset: tuple[int, int]` field to `Hooks`, default `(0, 0)`. When `use_scroll`
is called, it stores the setter and reads the offset from hooks. The layout step reads
`hooks.scroll_offset` when it encounters a scroll container.

Alternatively, `use_scroll` could store the offset as a regular `use_state` value and the
layout step finds it via a mapping keyed by shadow node identity. This avoids adding fields to
`Hooks` but requires the mapping to be populated before layout runs.

**Decision:** Add `scroll_offset` directly to `Hooks`. It's simpler and mirrors how `dims` is
already stored on `Hooks` for `use_rects`.

### Step 7: Hit-testing adjustment for scrolled content

**File:** `src/counterweight/app.py`

Mouse event dispatch currently checks `resolved.border.contains(pos)` for each element.
Since scroll-offset children have their `ResolvedLayout` rects already adjusted (Step 2),
hit-testing works automatically — a child scrolled off-screen has rects outside the viewport
and won't match.

However, we must also ensure that children scrolled outside the clip rect don't receive
mouse events. Add a clip-rect check: only dispatch mouse events to elements whose resolved
rects intersect the clip rect of their scroll container ancestor.

The simplest approach: store a `clip_rect: waxy.Rect | None` on `ResolvedLayout`. During
mouse dispatch, skip elements whose border rect doesn't intersect their clip rect.

### Step 8: Tests

**File:** `tests/test_scrolling.py`

- Scroll container clips children outside viewport
- `use_scroll` returns correct `ScrollState` values
- Mouse scroll events update scroll offset
- Scroll offset is clamped to `[0, max_offset]`
- Nested scroll containers clip to intersection
- Children scrolled off-screen don't receive mouse events
- `overflow_hidden` clips without enabling scrolling
- Horizontal scrolling works independently of vertical

---

## Files to Modify

| File | Change |
|---|---|
| `src/counterweight/hooks/hooks.py` | Add `ScrollState`, `use_scroll` |
| `src/counterweight/hooks/impls.py` | Add `scroll_offset` to `Hooks`, scroll setter tracking |
| `src/counterweight/hooks/__init__.py` | Export new symbols |
| `src/counterweight/_context_vars.py` | Add `current_scroll_listeners` |
| `src/counterweight/layout.py` | Scroll offset application, clip rect propagation, `ResolvedLayout` new fields |
| `src/counterweight/paint.py` | Clip rect parameter on paint functions |
| `src/counterweight/app.py` | Scroll event routing |
| `codegen/generate_utilities.py` | Overflow utility generation |
| `src/counterweight/styles/utilities.py` | Generated overflow utilities (via codegen) |
| `tests/test_scrolling.py` | New test file |

---

## Open Questions

1. **Should `overflow_hidden` clip without `use_scroll`?** CSS `overflow: hidden` clips content
   without enabling scrolling. This is useful independently (e.g. truncating text in a fixed-size
   box). The paint clipping logic should activate based on the overflow style, not the presence of
   `use_scroll`. The scroll offset just defaults to (0, 0) when there's no `use_scroll`.

2. **Smooth scrolling vs line-by-line?** Mouse wheel events in terminals typically report
   one scroll event per "notch". Mapping 1 event → 1 row of scroll offset is the standard TUI
   behavior. Smooth (sub-cell) scrolling is not possible in a terminal.

3. **Scroll-to-item API?** A future `scroll_to(offset)` or `scroll_to_item(index)` function
   returned from `use_scroll` would let components programmatically scroll. This can be added
   to `ScrollState` or as an additional return value from `use_scroll` without changing the
   architecture.

4. **Performance: large scroll containers.** A scroll container with 10,000 items but a 20-row
   viewport should not lay out or paint all 10,000 items. This requires virtualization — only
   rendering items near the viewport. This is a separate, larger feature (think React's
   `react-window`/`react-virtualized`). The basic scrolling plan here handles moderate content
   sizes; virtualization is future work.

---

## Future Work

- **Visual scrollbar rendering** — paint a scrollbar track/thumb in the gutter
- **Keyboard scrolling** — arrow keys, Page Up/Down, Home/End within focused scroll containers
- **Virtualized scrolling** — only render items near the viewport for large lists
- **`scroll_to` API** — programmatic scroll positioning
- **`overflow: auto`** — show scrollbar only when content exceeds viewport (requires scrollbar first)
- **Scroll snapping** — snap to item boundaries after scroll
