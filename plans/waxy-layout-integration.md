# Plan: Replace Counterweight Layout Engine with Waxy/Taffy

## Overview

Replace counterweight's hand-rolled Python flexbox layout engine (`layout.py`) with
[waxy](https://github.com/JoshKarpel/waxy), a Python wrapper around the Rust
[taffy](https://github.com/DioxusLabs/taffy) layout library. This gives us a
correct, fast, and feature-complete CSS layout engine (flexbox, grid, block)
while counterweight continues to own visual styling (colors, borders, typography).

Since counterweight is pre-1.0, we're free to break the public API.

## Key Design Decisions

### 1. Flatten Style and Embed `waxy.Style` Directly

The current counterweight `Style` has a nested structure:
```python
Style(layout=Flex(direction="row", weight=2), span=Span(width=20), margin=Margin(top=1, color=red), ...)
```

We flatten it to match waxy's flat approach, with the layout fields backed by an
actual `waxy.Style` stored inside. The counterweight `Style` becomes a thin
wrapper that holds:

- A `waxy.Style` for all layout properties (passed directly to taffy)
- Visual-only fields for colors, typography, border characters, z-index

This means **no translation layer** — the `waxy.Style` inside is the one that
gets used at layout time. The tailwind utilities hide the verbosity so users
rarely construct these by hand anyway.

**New `Style` structure (conceptual):**

```python
class Style(StyleFragment):
    # Layout — a waxy.Style, passed directly to taffy at layout time
    layout: waxy.Style = waxy.Style()

    # Visual — counterweight-only, not passed to taffy
    z: int = 0                                              # was layout.z
    margin_color: Color = Color.from_name("black")          # was margin.color
    padding_color: Color = Color.from_name("black")         # was padding.color
    content_color: Color = Color.from_name("black")         # was content.color

    # Border visual (flattened from Border) — not passed to taffy
    border_kind: BorderKind | None = None                   # was border.kind
    border_style: CellStyle | None = None                   # was border.style (fg/bg colors)
    border_edges: frozenset[BorderEdge] | None = None       # was border.edges
    border_contract: int = 0                                # was border.contract

    # Typography (flattened from Typography) — not passed to taffy
    text_style: CellStyle = CellStyle()                     # was typography.style
    text_justify: Literal["left", "center", "right"] = "left"  # was typography.justify
    text_wrap: Literal["none", "paragraphs"] = "none"       # was typography.wrap
```

**Merge behavior:** `waxy.Style` has its own `__or__` operator with bitmask-
based field tracking — fields explicitly set on the right side override, unset
fields preserve the left side's values. This is the same semantics as
counterweight's `StyleFragment.mergeable_dump()` / `model_fields_set` system.

The `Style.__or__` implementation merges the `layout` field using
`waxy.Style.__or__` and merges the visual fields using the existing
`StyleFragment` logic:

```python
def __or__(self, other: Style) -> Style:
    # Merge layout via waxy's own merge
    merged_layout = self.layout | other.layout
    # Merge visual fields via StyleFragment logic
    merged = merge_style_fragments(self, other)
    # Combine (need to handle layout specially since it's not a StyleFragment)
    ...
```

This means `layout` needs special handling in the `__or__` method since
`waxy.Style` is not a `StyleFragment` and doesn't participate in pydantic's
`model_fields_set`. The simplest approach: always merge `layout` via
`waxy.Style.__or__`, regardless of whether it appears in `model_fields_set`.
Since `waxy.Style()` (no fields set) is the identity element for `|`, this
is safe — merging with a default `waxy.Style()` is a no-op.

Notes:
- No need to mirror waxy's 30+ layout fields on the counterweight Style.
  The `waxy.Style` is the single source of truth for layout.
- At layout time, `style.layout` is passed directly to
  `tree.new_with_children()` / `tree.new_leaf_with_context()` — no
  `to_waxy_style()` translation needed.
- Border visual fields (`border_kind`, `border_style`, `border_edges`,
  `border_contract`) are the flattened contents of the old `Border` class.
  Whether a border is drawn at all is determined by `border_kind` being set.
  The border *widths* for layout are on `layout` (e.g.,
  `waxy.Style(border_top=waxy.Length(1))`).
- Typography fields (`text_style`, `text_justify`, `text_wrap`) are the
  flattened contents of the old `Typography` class.
- `CellStyle` stays as its own type since it's used in multiple places
  (text style, border style) and has 7 fields — flattening it further would
  create an explosion of fields with ambiguous names.

### 2. Tree Lifecycle: Rebuild Each Render

Build a fresh `waxy.TaffyTree` on every render cycle. Simple and correct.
Optimization (tree reuse, dirty tracking) deferred to future work.

### 3. Text Measurement via `measure` Callback

Text nodes are leaf nodes whose size depends on content and available space.

- Create text nodes with `tree.new_leaf_with_context(waxy_style, text_element)`.
- Pass a `measure` callback to `compute_layout()` that uses `wrap_cells()` to
  compute text dimensions given available width.
- The callback receives `(known_size, available_size, context)` where context
  is the `Text` element.

### 4. Border: Layout vs Visual Split

Currently `Border` is one object with both layout info (which edges are active →
determines 1-cell border widths) and visual info (characters, cell style,
contract).

Both are flattened onto `Style`:
- **Layout**: `border_top/left/right/bottom` fields with `waxy.Length(1)` or
  `waxy.Length(0)` depending on which edges are drawn.
- **Visual**: `border_kind`, `border_style`, `border_edges`, `border_contract`
  — all flat fields on Style.

The `border_light`, `border_heavy`, etc. utility variables set both:
```python
border_light = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1), border_bottom=waxy.Length(1),
        border_left=waxy.Length(1), border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.Light,
    border_edges=frozenset({BorderEdge.Top, BorderEdge.Bottom, BorderEdge.Left, BorderEdge.Right}),
)
```

Edge-specific utilities like `border_top` (only top edge) would set only that
border width to 1 and configure `border_edges` accordingly.

### 5. Mapping Layout Results Back

After `compute_layout()`, read `waxy.Layout` for each node to build
counterweight's `LayoutBoxDimensions`:

- `layout.location` → position (relative to parent, accumulated during walk)
- `layout.padding` / `layout.border` → edge thicknesses
- `layout.content_box_width()` / `content_box_height()` → content dimensions
- Margin read from the style we set (taffy may not expose computed margins)

### 6. Fixed Positioning & Z-Index

Taffy has `Relative` and `Absolute` but no `Fixed` (screen-relative).

Handle `Fixed` elements outside taffy: extract them during tree building,
compute their layout in a separate mini taffy tree with full screen as available
space, position at the fixed offset. Merge into paint output respecting z-index.

Z-index is purely a paint/render concern and stays on counterweight's `Style`.

---

## Implementation Steps

### Step 1: Add waxy dependency

Add `waxy` to `pyproject.toml`.

### Step 2: Restructure Style

Restructure `Style` in `styles/styles.py`:

- Replace `Flex`, `Span` with a single `layout: waxy.Style` field
- Split `Margin` → layout widths (on `waxy.Style`) + `margin_color`
- Split `Padding` → layout widths (on `waxy.Style`) + `padding_color`
- Flatten `Border` → layout widths (on `waxy.Style`) +
  visual fields (`border_kind`, `border_style`, `border_edges`, `border_contract`)
- Flatten `Content` → `content_color`
- Flatten `Typography` → `text_style`, `text_justify`, `text_wrap`
- Remove `Relative`, `Absolute`, `Fixed`, `Inset` classes — replaced by
  `waxy.Position` enum + `inset_*` on `waxy.Style`
- Customize `__or__` to merge `layout` via `waxy.Style.__or__`
- Keep `CellStyle` as its own type (used for both `text_style` and
  `border_style`, has 7 fields — flattening further would be unwieldy)

The `Fixed` position concept becomes a counterweight-specific field
(e.g., `fixed: bool` or a separate mechanism) since taffy doesn't have it.

### Step 3: Update style utilities

Rewrite `styles/utilities.py` to construct the new `Style` objects:

```python
# Before:
row = Style(layout=Flex(direction="row"))
col = Style(layout=Flex(direction="column"))
weight_2 = Style(layout=Flex(weight=2))
pad_1 = Style(padding=Padding(top=1, bottom=1, left=1, right=1))
gap_children_2 = Style(layout=Flex(gap_children=2))

# After — layout fields go into waxy.Style:
row = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Row))
col = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Column))
weight_2 = Style(layout=waxy.Style(flex_grow=2.0, flex_basis=waxy.Length(0)))
pad_1 = Style(layout=waxy.Style(
    padding_top=waxy.Length(1), padding_bottom=waxy.Length(1),
    padding_left=waxy.Length(1), padding_right=waxy.Length(1),
))
gap_children_2 = Style(layout=waxy.Style(gap_width=waxy.Length(2), gap_height=waxy.Length(2)))
```

The generated color/visual utilities use the flattened visual fields:
```python
# Before: margin_slate_50 = Style(margin=Margin(color=slate_50))
# After:  margin_slate_50 = Style(margin_color=slate_50)

# Before: text_justify_center = Style(typography=Typography(justify="center"))
# After:  text_justify_center = Style(text_justify="center")

# Before: border_slate_50 = Style(border=Border(style=CellStyle(foreground=slate_50)))
# After:  border_slate_50 = Style(border_style=CellStyle(foreground=slate_50))

# Before: text_bold = Style(typography=Typography(style=CellStyle(bold=True)))
# After:  text_bold = Style(text_style=CellStyle(bold=True))
```

### Step 4: Rewrite layout.py

Replace the layout engine with waxy tree building + result extraction:

1. Walk shadow tree bottom-up, creating waxy nodes
2. `Div` → `tree.new_with_children(style.layout, child_ids)`
3. `Text` → `tree.new_leaf_with_context(style.layout, text_element)`
4. Collect a mapping: `dict[waxy.NodeId, ShadowNode]`
5. Call `tree.compute_layout(root, available_size, measure=measure_text)`
6. Walk tree top-down, accumulating absolute positions from `layout.location`,
   building `LayoutBoxDimensions` for each node

Keep `LayoutBoxDimensions` and `wrap_cells()`. Delete `LayoutBox`,
`first_pass()`, `second_pass()`, `compute_layout()`.

### Step 5: Write text measure callback

```python
def measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: Text,
) -> waxy.Size:
    width = known.width
    if width is None and isinstance(available.width, waxy.Definite):
        width = available.width.value
    lines = wrap_cells(
        context.cells,
        context.style.typography.wrap,
        int(width) if width is not None else 10_000,
    )
    return waxy.Size(
        known.width if known.width is not None else max((len(l) for l in lines), default=0),
        known.height if known.height is not None else len(lines),
    )
```

### Step 6: Adapt paint.py

Change `paint_layout` to accept a flat list of `(element, dims)` pairs instead
of a `LayoutBox` tree. It already just walks the tree and paints each element
independently, sorted by z-index.

Update `paint_element` to read visual properties from the flattened `Style`:
- `element.style.margin_color` instead of `element.style.margin.color`
- `element.style.padding_color` instead of `element.style.padding.color`
- `element.style.content_color` instead of `element.style.content.color`
- `element.style.z` instead of `element.style.layout.z`
- `element.style.border_kind` instead of `element.style.border.kind`
- `element.style.border_style` instead of `element.style.border.style`
- `element.style.border_edges` instead of `element.style.border.edges`
- `element.style.border_contract` instead of `element.style.border.contract`
- `element.style.text_style` instead of `element.style.typography.style`
- `element.style.text_justify` instead of `element.style.typography.justify`
- `element.style.text_wrap` instead of `element.style.typography.wrap`

### Step 7: Update app.py

- Replace `build_layout_tree_from_shadow` + `layout_tree.compute_layout()` with
  the new waxy-based layout function
- Update mouse hit-testing to work with the flat `(element, dims)` list
- Update `Hooks.dims` assignment

### Step 8: Handle Fixed positioning

During tree building, detect elements with fixed positioning:
- Don't add them to the main taffy tree
- Compute their layout separately (mini taffy tree with screen-size available
  space)
- Position at the fixed offset
- Include in the flat element+dims list for painting and hit-testing

### Step 9: Update exports and examples

- Update `__init__.py` exports (remove `Flex`, `Span`, etc.; potentially
  re-export useful waxy types)
- Update all examples to use the new flattened style API
- Update docs

### Step 10: Delete dead code

- `LayoutBox` class (except `LayoutBoxDimensions`)
- `first_pass()`, `second_pass()`
- `partition_int()` from `_utils.py`
- `Flex`, `Span`, `Relative`, `Absolute`, `Fixed`, `Inset` style classes
- Old `Margin`, `Padding` classes (replaced by flat fields)
- Old `Content` class (replaced by `content_color` field)
- Old `Border` class (replaced by flat `border_*` fields)
- Old `Typography` class (replaced by flat `text_*` fields)

### Step 11: Update tests

Layout tests will need updating — taffy implements CSS flexbox correctly while
the old engine was an approximation. Regenerate snapshots, update assertions.

---

## Changes Needed in Waxy

Likely minimal:

1. **Layout.margin**: Verify waxy exposes `margin` on the `Layout` object (it
   does — `layout.margin` returns a `Rect`). If not, we can read from the style.

2. **Rounding**: Enable `tree.enable_rounding()` for integer cell coordinates.
   Verify rounding behavior is sensible for TUI.

3. **Gap semantics**: Verify behavior when setting both `gap_width` and
   `gap_height` (taffy applies them per-axis, so setting both should be fine).

---

## Files Changed (Counterweight)

| File | Change |
|------|--------|
| `pyproject.toml` | Add `waxy` dependency |
| `src/counterweight/styles/styles.py` | Restructure `Style`: `layout: waxy.Style` field, flatten visual fields, remove `Flex`/`Span`/`Border`/`Typography`/position classes, custom `__or__` |
| `src/counterweight/styles/utilities.py` | Rewrite all utilities to use flattened Style + waxy types |
| `src/counterweight/styles/__init__.py` | Update exports |
| `src/counterweight/layout.py` | Rewrite: waxy tree build + result extraction. Delete old layout engine. |
| `src/counterweight/app.py` | Use new layout function, update mouse hit-testing |
| `src/counterweight/paint.py` | Adapt to flat element+dims list and flattened style field names |
| `src/counterweight/_utils.py` | Remove `partition_int` if unused |
| `src/counterweight/elements.py` | Update `Div`/`Text` default style if needed |
| `src/counterweight/__init__.py` | Update public exports |
| `examples/` | Update to new style API |
| `tests/` | Update layout tests, regenerate snapshots |

## Files Changed (Waxy)

Likely none, but possibly:

| File | Change |
|------|--------|
| `src/layout.rs` | Expose `margin` on `Layout` if not already |

---

## Migration Risk & Mitigations

- **API breakage**: All user code using `Flex(...)`, `Span(...)`, `Margin(...)`,
  etc. breaks. Mitigated by: pre-1.0 status, utilities hide most of this,
  and the new API is arguably better (flatter, closer to CSS).
- **Layout differences**: Taffy implements CSS flexbox correctly; some layouts
  may shift. Mitigate by running all examples visually and updating tests.
- **Performance**: Building a fresh taffy tree each render adds Python overhead,
  but taffy's Rust layout is much faster than the Python implementation.
  Net effect should be positive or neutral.
- **Float→int rounding**: Use `enable_rounding()` and test carefully for
  off-by-one issues.

## Out of Scope (Future Work)

- Tree reuse / incremental layout across renders
- Exposing CSS Grid layout to counterweight users
- Flex wrap support
- `min_size` / `max_size` support
- Overflow/scrolling
- Percent-based sizing (would need parent-relative calculation)
