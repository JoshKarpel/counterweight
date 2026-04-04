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

### 2. Clipping at the paint level via `ClipDict`

Today, `paint_element` produces `Paint` (a `dict[Position, P]`) with no awareness of parent
bounds. Elements paint wherever their resolved rects say, even if that's outside the terminal.

For scrolling, we need to:
- **Offset** child positions by the scroll amount (subtract `scroll_x` from x, `scroll_y` from y)
- **Clip** painted cells to the parent container's padding rect

The clip rect for each element is fully determined during `_extract_layout` (where the tree
hierarchy is available) and stored on `ResolvedLayout.clip_rect`. By the time painting runs,
the flat `(element, ResolvedLayout)` list already carries each element's effective clip rect —
no propagation is needed at paint time.

`waxy.Rect.intersection` (available in waxy 0.5.0) computes the intersection of two rects,
returning `None` if they don't overlap. Use this instead of a hand-written `intersect_rects`.

Rather than threading a `clip_rect` parameter through every paint sub-function, we introduce
`ClipDict[T]`, a `MutableMapping[Position, T]` that silently discards writes whose key falls
outside the clip rect:

```python
T = TypeVar("T")

class ClipDict(UserDict[Position, T]):
    def __init__(self, clip: waxy.Rect | None) -> None:
        super().__init__()
        self._clip = clip

    def __setitem__(self, key: Position, value: T) -> None:
        if self._clip is None or key in self._clip:
            super().__setitem__(key, value)
```

`UserDict` (from `collections`) stores data in `self.data` and is designed for subclassing —
`__getitem__`, `__delitem__`, `__iter__`, `__len__`, and `|=` are all inherited.

`paint_element` creates a `ClipDict[P]` (for cell paint) and a `ClipDict[JoinedBorderParts]`
(for border healing hints) using `resolved.clip_rect`, then merges the results from the
unchanged sub-functions into them via `|=`. Clipping happens automatically at merge
time — no clip parameters are added to `fill_rect`, `paint_edge`, `_paint_text`, or
`paint_border`. These functions continue to return plain dicts.
(`fill_rect`, `paint_edge`, `_paint_text` are lru_cached; `paint_border` is not, but all four
are unchanged and continue to return plain dicts regardless.)

`paint_element` returns `tuple[Mapping[Position, P], Mapping[Position, JoinedBorderParts], int, int]`
(relaxed from `dict` to `Mapping`). `paint_layout` accumulates into a plain `dict` as before,
using `|=` which iterates the `Mapping`.

### 3. Scroll offset application during layout extraction

The scroll offset shifts where children appear *visually*, not where they are *logically*.
We apply it in `_extract_layout`: when walking a scroll container's children, subtract the
container's `(scroll_x, scroll_y)` from `abs_x`/`abs_y` before recursing. This means child
`ResolvedLayout` rects reflect their actual screen position (post-scroll), so paint and
hit-testing work without further adjustment.

The offset is available at layout time because `use_scroll` runs during component render
(which precedes layout) and writes the current offset to `hooks.scroll_offset`. This is the
same timing as `use_rects` / `hooks.dims`: render produces data that layout reads.
`_extract_layout` reads `shadow.hooks.scroll_offset` when it encounters a scroll container.

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
    initial_offset_x: int = 0,
    initial_offset_y: int = 0,
) -> tuple[ScrollState, Style, Callable[[AnyMouseEvent], AnyControl | None], Callable[[KeyPressed], AnyControl | None]]:
```

The hook returns:
- `ScrollState` — the current scroll position and bounds (read-only snapshot)
- `Style` — a style that must be merged onto the scroll container's element; it sets
  `overflow_x`/`overflow_y` on `waxy.Style` and a marker that the layout/paint system reads
- `on_mouse` handler — an `on_mouse`-compatible callable that handles `MouseScrolledUp` /
  `MouseScrolledDown` events and returns `StopPropagation()` when it acts on them; the
  component applies this to the scroll container element via `on_mouse=scroll_on_mouse`
- `on_key` handler — an `on_key`-compatible callable that handles arrow key presses:
  `"up"`/`"down"` scroll vertically (if `scroll_y`), `"left"`/`"right"` scroll horizontally
  (if `scroll_x`); returns `StopPropagation()` when it acts, `None` otherwise; the component
  applies this to the scroll container element via `on_key=scroll_on_key`

The hook internally calls `use_state` for the offset and `use_rects` for viewport dimensions.

**Why return a `Style`?** The alternative is adding `overflow` fields to `Div`/`Text` directly.
Returning a style keeps elements simple and follows the existing pattern where layout behavior is
configured via style merging. The style also carries an internal marker (a new `Style` field) that
the layout system reads to identify scroll containers.

**Note on flex direction:** taffy only reports a meaningful `content_size` when the container's
children are laid out along the scroll axis. For vertical scroll (`scroll_y=True`), the returned
`Style` sets `flex_direction=Column` so children stack vertically. Horizontal scroll sets
`flex_direction=Row`. Without this, a single child can report `content_size=(0,0)` (verified
empirically against waxy).

### 5. Scroll events via `on_mouse` + `on_key` + `StopPropagation`

Scroll events are handled via the existing `on_mouse` and `on_key` element dispatch.
`use_scroll` returns both handlers.

**Mouse:** When `MouseScrolledUp` or `MouseScrolledDown` arrives and the event position is
within the container's border rect, the `on_mouse` handler updates the scroll offset (clamped
to `[0, max_offset]`) and returns `StopPropagation()` to prevent outer scroll containers from
also scrolling.

**Keyboard:** The `on_key` handler matches `KeyPressed(key="up")` / `KeyPressed(key="down")`
for vertical scroll and `KeyPressed(key="left")` / `KeyPressed(key="right")` for horizontal
scroll (controlled by the `scroll_x`/`scroll_y` flags passed to `use_scroll`). It returns
`StopPropagation()` when it acts, `None` otherwise. Arrow key strings come from the `Key` enum
in `counterweight/keys.py` (`Key.Up = "up"`, `Key.Down = "down"`, etc.).

Both handlers share the same offset-update and clamp logic.

A new `StopPropagation` control is added to `controls.py`:

```python
@dataclass(frozen=True, slots=True)
class StopPropagation(_Control):
    """Stop dispatching the current event to further elements."""
```

`handle_control` returns `bool` (`True` = stop propagation). All dispatch loops in `app.py`
that iterate elements and call `handle_control` gain a `break` on `True`. This applies
consistently to both `on_mouse` and `on_key` dispatch loops — not just scroll events.

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
    clip_rect: waxy.Rect | None = None   # effective clip rect (intersection of all ancestor scroll containers)
```

### 7. No visual scrollbars in v1

Scrollbars (the visual indicator showing scroll position) are a nice-to-have but add significant
complexity: they need to be painted in the gutter, respond to mouse drag, and update dynamically.
The first version ships without visible scrollbars.

Users can build their own scrollbar indicators using `ScrollState.offset_y` and
`ScrollState.max_offset_y` if needed. Taffy's `scrollbar_width` can reserve gutter space for
a future built-in scrollbar.

### 8. `overflow_hidden` clips without `use_scroll`

CSS `overflow: hidden` clips content without enabling scrolling — useful for text truncation,
masked overlays, etc. The paint clipping logic activates based on the overflow style on
`waxy.Style`, not on the presence of `use_scroll`. For elements with `overflow: hidden` or
`overflow: clip`, the clip rect is set to the padding rect (same as scroll containers) and the
scroll offset defaults to `(0, 0)`. The `overflow_hidden` / `overflow_clip` utilities are
therefore useful on their own without `use_scroll`.

### 9. Clip rect propagation for nested scroll containers

Scroll containers can nest. A scrollable list inside a scrollable panel should clip to the
*intersection* of both clip rects. During `_extract_layout`, we pass a `clip_rect` parameter
that narrows as we enter nested scroll/hidden/clip containers. Each node's `ResolvedLayout`
receives the *incoming* clip rect (the constraint imposed by its ancestors), which is what
`paint_element` and mouse hit-testing use:

```python
def _extract_layout(tree, node_id, node_map, abs_x, abs_y, results, clip_rect=None):
    ...
    resolved = ResolvedLayout(..., clip_rect=clip_rect)
    results.append((shadow.element, resolved))

    if is_clipping_container:
        child_clip = padding_rect if clip_rect is None else clip_rect.intersection(padding_rect)
    else:
        child_clip = clip_rect
    for child_node_id in tree.children(node_id):
        _extract_layout(tree, child_node_id, node_map, ..., clip_rect=child_clip)
```

"Clipping container" covers `overflow: hidden`, `overflow: clip`, and `overflow: scroll`
(any overflow mode that restricts visible content). `hidden` and `clip` are effectively
identical in counterweight — both clip without scrolling; the distinction (whether programmatic
scroll manipulation is allowed) only matters in browsers. `use_scroll` always sets `scroll`.
See decision 8 for `overflow_hidden` standalone behavior.

---

## Implementation Steps

### Step 1: Add scroll state infrastructure to hooks

**File:** `src/counterweight/hooks/impls.py`

Add `scroll_offset: tuple[int, int]` field to `Hooks` (default `(0, 0)`). `use_scroll` writes
the current offset here during render so that the subsequent `_extract_layout` pass can read it
from `shadow.hooks.scroll_offset` when it encounters a scroll container. This is the same
pattern as `use_rects` / `hooks.dims`.

**File:** `src/counterweight/hooks/hooks.py`

Add `ScrollState` dataclass and `use_scroll` hook function.

`use_scroll` internally:
- Calls `use_state((0, 0))` for the scroll offset
- Writes the current offset to `current_hook_state.get().scroll_offset` (same frame, before layout)
- Calls `use_rects()` to get viewport dimensions (from previous frame, same as `use_hovered`)
- Returns `ScrollState` (computed from rects + offset), a `Style` with overflow and
  `flex_direction` set, and an `on_mouse` handler that handles scroll events and returns
  `StopPropagation()` when it acts

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

Add `ClipDict[T]` (a `MutableMapping[Position, T]`). Modify `paint_element` to create two
`ClipDict` instances from `resolved.clip_rect` — one for `P` (cell paint) and one for
`JoinedBorderParts` (border healing hints) — and merge the results of lru-cached functions
into them via `|=`. The cached functions (`fill_rect`, `paint_edge`, `_paint_text`,
`paint_border`) are unchanged and continue to return plain `dict`s.

Relax the return type of `paint_element` from `tuple[Paint, BorderHealingHints, int, int]`
to `tuple[Mapping[Position, P], Mapping[Position, JoinedBorderParts], int, int]`.
`paint_layout` continues to accumulate into plain `dict`s via `|=`.

### Step 4: `StopPropagation` control and consistent dispatch loops

**File:** `src/counterweight/controls.py`

Add `StopPropagation` to `_Control` subclasses and to the `AnyControl` union.

**File:** `src/counterweight/app.py`

Change `handle_control` to return `bool` (`True` = stop propagation). Update all element
dispatch loops to `break` when `handle_control` returns `True`:

```python
# on_key dispatch
for element, _ in reversed(elements_and_layouts):
    if element.on_key:
        if handle_control(element.on_key(event)):
            break

# on_mouse dispatch
for element, resolved in reversed(elements_and_layouts):
    if resolved.border.contains(mouse_pos) or resolved.border.contains(event_pos):
        if element.on_mouse:
            if handle_control(element.on_mouse(event)):
                break
```

Scroll events (`MouseScrolledDown` / `MouseScrolledUp`) flow through the same `on_mouse`
dispatch path — no special-casing needed. The `on_mouse` handler returned by `use_scroll`
checks whether the event position is within the container's border rect, updates the offset
(clamped to `[0, max_offset]`), and returns `StopPropagation()`.

Arrow key scroll (`on_key` handler from `use_scroll`) flows through the same `on_key` dispatch
path — no special-casing needed.

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

### Step 6: Hit-testing adjustment for scrolled content

**File:** `src/counterweight/app.py`

Mouse event dispatch currently checks `resolved.border.contains(pos)` for each element.
Since scroll-offset children have their `ResolvedLayout` rects already adjusted (Step 2),
hit-testing works automatically — a child scrolled off-screen has rects outside the viewport
and won't match.

However, we must also ensure that children scrolled outside the clip rect don't receive
mouse events. During mouse dispatch, skip elements where `resolved.clip_rect` is set and the
event position is not contained in it (i.e. `pos not in resolved.clip_rect`).

### Step 7: Tests

**File:** `tests/test_scrolling.py`

- Scroll container clips children outside viewport
- `use_scroll` returns correct `ScrollState` values
- Mouse scroll events update scroll offset
- Arrow key events update scroll offset (`on_key` handler)
- Scroll offset is clamped to `[0, max_offset]`
- Nested scroll containers clip to intersection
- Children scrolled off-screen don't receive mouse events
- `overflow_hidden` clips without enabling scrolling
- Horizontal scrolling works independently of vertical
- `on_key` handler respects `scroll_x`/`scroll_y` flags (e.g. left/right ignored when `scroll_x=False`)

---

## Files to Modify

| File | Change |
|---|---|
| `src/counterweight/hooks/hooks.py` | Add `ScrollState`, `use_scroll` |
| `src/counterweight/hooks/impls.py` | Add `scroll_offset` to `Hooks` |
| `src/counterweight/hooks/__init__.py` | Export new symbols |
| `src/counterweight/controls.py` | Add `StopPropagation` control |
| `src/counterweight/layout.py` | Scroll offset application, clip rect propagation, `ResolvedLayout` new fields |
| `src/counterweight/paint.py` | Add `ClipDict`, update `paint_element` |
| `src/counterweight/app.py` | `handle_control` returns `bool`; all dispatch loops break on `StopPropagation` |
| `codegen/generate_utilities.py` | Overflow utility generation |
| `src/counterweight/styles/utilities.py` | Generated overflow utilities (via codegen) |
| `tests/test_scrolling.py` | New test file |

---

## Future Work

- **Visual scrollbar rendering** — paint a scrollbar track/thumb in the gutter
- **Extended keyboard scrolling** — Page Up/Down, Home/End within focused scroll containers
- **Virtualized scrolling** — only render items near the viewport for large lists
- **`scroll_to` API** — `scroll_to(offset)` or `scroll_to_item(index)` for programmatic positioning;
  can be added to `ScrollState` or as an additional return value from `use_scroll` without changing the architecture
- **`overflow: auto`** — show scrollbar only when content exceeds viewport (requires scrollbar first)
- **Scroll snapping** — snap to item boundaries after scroll
- **Composing `on_mouse` handlers** — if a component wants both `use_scroll` and its own `on_mouse`
  on the same element, the two conflict since `on_mouse` is a single callable today; options include
  supporting a list of handlers or having `use_scroll` return a composable handler
- **Performance: large scroll containers** — a container with 10,000 items but a 20-row viewport
  should not lay out or paint all 10,000 items; requires virtualization (think React's `react-window`)
