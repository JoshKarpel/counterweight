# Plan: Replace Counterweight Layout Engine with Waxy/Taffy

## Overview

Replace counterweight's hand-rolled Python flexbox layout engine (`layout.py`) with
[waxy](https://github.com/JoshKarpel/waxy), a Python wrapper around the Rust
[taffy](https://github.com/DioxusLabs/taffy) layout library. This gives us a
correct, fast, and feature-complete CSS layout engine (flexbox, grid, block)
while counterweight continues to own visual styling (colors, borders, typography).

Since counterweight is pre-1.0, we're free to break the public API.

waxy 0.3.0 is already in `pyproject.toml` and installed.

---

## Key Design Decisions

### 1. Flatten Style and Embed `waxy.Style` Directly

**Current** `Style` (`styles/styles.py:678`) has nested `StyleFragment` subclasses:

```python
class Style(StyleFragment):         # line 678
    layout: Flex = Flex()           # Flex has direction, position, weight, z, align_self, justify/align_children, gap_children
    span: Span = Span()             # width/height: int | "auto"
    margin: Margin = Margin()       # top/bottom/left/right: int + color: Color
    border: Border | None = None    # kind, style (CellStyle), edges, contract
    padding: Padding = Padding()    # top/bottom/left/right: int + color: Color
    content: Content = Content()    # color: Color
    typography: Typography = Typography()  # style (CellStyle), justify, wrap
```

**New** `Style` flattens to two concerns:

```python
class Style(StyleFragment):
    # Layout — a waxy.Style, passed directly to taffy at layout time
    layout: waxy.Style = waxy.Style()

    # Visual — counterweight-only, not passed to taffy
    z: int = 0                                              # was layout.z
    margin_color: Color = Color.from_name("black")          # was margin.color
    padding_color: Color = Color.from_name("black")         # was padding.color
    content_color: Color = Color.from_name("black")         # was content.color

    # Border visual (flattened from Border)
    border_kind: BorderKind | None = None                   # was border.kind; None = no border
    border_style: CellStyle | None = None                   # was border.style (fg/bg colors)
    border_contract: int = 0                                # was border.contract
    # Note: border_edges removed — which edges are active is determined by which
    # waxy.Style.border_* fields are nonzero (read from ResolvedLayout at paint time)

    # Typography (flattened from Typography)
    text_style: CellStyle = CellStyle()                     # was typography.style
    text_justify: Literal["left", "center", "right"] = "left"  # was typography.justify
    text_wrap: Literal["none"] = "none"                     # was typography.wrap; "paragraphs" dropped
```

**`waxy.Style` is a Rust-backed Python class, not a pydantic model.** Pydantic cannot
generate a schema for it automatically, so `Style` must declare
`model_config: ClassVar[ConfigDict] = {"arbitrary_types_allowed": True}`.
Also, `waxy.Style()` instances are hashable but not equal by value
(`waxy.Style() == waxy.Style()` → `False`), so the parent `StyleFragment` cache
is bypassed — `Style.__or__` does not use `STYLE_MERGE_CACHE`.

**Merge behavior:** `waxy.Style` has its own `__or__` with bitmask-based field tracking.
The `Style.__or__` merges `layout` via `waxy.Style.__or__` and visual fields via
the existing `StyleFragment` logic. Since `waxy.Style()` (no fields set) is the
identity element for `|`, merging with a default is a no-op.

Key decision: `layout` is NOT a `StyleFragment` and doesn't participate in pydantic's
`model_fields_set`. The `__or__` method always merges `layout` via `waxy.Style.__or__`,
bypassing `mergeable_dump()` for that field. The visual fields continue using the
existing `StyleFragment` merge.

**Concrete `__or__` implementation:**

```python
def __or__(self: S, other: S | None) -> S:
    if other is None:
        return self
    # Merge layout via waxy's own merge (always, not gated by model_fields_set)
    merged_layout = self.layout | other.layout
    # Merge visual fields via existing StyleFragment logic
    merged = merge_style_fragments(self, other)
    # Patch in the waxy-merged layout (merge_style_fragments won't handle it correctly
    # since waxy.Style is not a StyleFragment)
    return merged.model_copy(update={"layout": merged_layout})
```

Note: `merge_style_fragments` calls `mergeable_dump()` which iterates `model_fields_set`.
Since `layout` is always in `model_fields_set` when explicitly set, and `waxy.Style`
is not a `StyleFragment`, the `mergeable_dump` method needs a branch for non-fragment,
non-primitive fields. Simplest: exclude `layout` from `mergeable_dump()` entirely and
handle it in `__or__` as shown above.

### 2. Tree Lifecycle: Rebuild Each Render

Build a fresh `waxy.TaffyTree` on every render cycle. Simple and correct.

### 3. Text Measurement via `measure` Callback

Text nodes are leaf nodes whose size depends on content and available space.

- Create text nodes with `tree.new_leaf_with_context(waxy_style, text_element)`.
- Pass a `measure` callback to `tree.compute_layout()` that uses `wrap_cells()` to
  compute text dimensions given available width.
- The callback receives `(known_size: waxy.KnownSize, available_size: waxy.AvailableSize, context: Text)`.

### 4. Border: Layout vs Visual Split

Both layout and visual border info are flattened onto `Style`:
- **Layout widths**: `border_top/left/right/bottom` fields on `waxy.Style` with `waxy.Length(1)` or `waxy.Length(0)`.
- **Visual rendering**: `border_kind`, `border_style`, `border_edges`, `border_contract` — flat fields on `Style`.

The `border_light`, `border_heavy`, etc. utility variables set both simultaneously.

### 5. Mapping Layout Results Back

After `tree.compute_layout()`, walk the tree top-down accumulating absolute positions.
`waxy.Layout` (from `tree.layout(node)`) provides:
- `location: waxy.Point` — position relative to parent (`.x`, `.y`)
- `size: waxy.Size` — outer box size (`.width`, `.height`)
- `content_box_width() / content_box_height()` — content area dimensions
- `padding: waxy.Rect` — padding widths (`.left`, `.right`, `.top`, `.bottom`)
- `border: waxy.Rect` — border widths
- `margin: waxy.Rect` — margin widths

Build a `ResolvedLayout` for each node with pre-computed absolute `waxy.Rect`s:

```python
@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: waxy.Rect   # absolute rect of content box
    padding: waxy.Rect   # absolute rect including padding
    border: waxy.Rect    # absolute rect including border
    margin: waxy.Rect    # absolute rect including margin
    order: int           # taffy's computed paint order (from Layout.order)
```

We use `waxy.Rect` (not counterweight's `Rect`) for all resolved layout rects.
`waxy.Rect` is constructed with `(left, right, top, bottom)` where all four edges are
**inclusive** — i.e. a rect covering columns 0–3 and rows 0–2 is
`waxy.Rect(left=0, right=3, top=0, bottom=2)`.

**`waxy.Rect.width` / `.height` semantics**: these return `right - left` and
`bottom - top` respectively, which is **one less than the pixel count**. For example,
a rect covering 4 columns has `width=3`. When you need the actual number of
columns/rows (e.g. for text wrapping), use `len(rect.top_edge())` or
`int(rect.width) + 1`.

**`waxy.Rect` API highlights** (all available for paint/hit-test code):
- `.left`, `.right`, `.top`, `.bottom` — inclusive edges
- `.top_left`, `.top_right`, `.bottom_left`, `.bottom_right` — `waxy.Point`
- `.left_edge()`, `.right_edge()`, `.top_edge()`, `.bottom_edge()` — iterators of `waxy.Point`
- `.points()` / `__iter__` — all points in the rect
- `.rows()`, `.columns()` — iterators of row/column iterators
- `.contains(waxy.Point)` — hit testing
- `.corners()` — four corner points
- `.size` — `waxy.Size(width, height)`

**Coordinate system** (confirmed empirically):
- `layout.location` is **relative to the parent's border box** (not content box, not absolute)
- `layout.location` points to the **node's border box** origin (not margin box)
- `layout.size` is the **border box size** (excludes margin); `size.width` is the pixel count (not off-by-one)

Each rect computed from `waxy.Layout` fields, starting from the border box.
Note: `layout.size.width/height` are pixel counts, so `right = left + size.width - 1`:
- Border: `Rect(left=abs_x, right=abs_x + size.width - 1, top=abs_y, bottom=abs_y + size.height - 1)`
- Margin: border rect expanded outward by `layout.margin` widths
- Padding: border rect shrunk inward by `layout.border` widths
- Content: padding rect shrunk inward by `layout.padding` widths

All values rounded to `int` (taffy returns floats; use `tree.layout(node)` which returns rounded values via `enable_rounding()`).

### 6. Fixed Positioning: Dropped

Taffy has `Position.Relative` and `Position.Absolute` but no `Fixed`.
Fixed positioning is not used anywhere outside `docs/examples/fixed_positioning.py`,
so we drop it entirely for now. The `Fixed` class, `fixed()` utility, and the
doc example are all deleted. Fixed positioning is listed as future work — when
needed, it can be implemented by reparenting fixed elements to the root taffy node
with `position: Absolute`.

Z-index (`style.z`) is purely a paint/render concern and stays on counterweight's `Style`.

---

## Implementation Steps

### Step 1: Restructure `Style` in `styles/styles.py` ✅ DONE

**Delete these classes** (all `StyleFragment` subclasses):
- `Flex` (line 654) — 10 fields → replaced by `waxy.Style` fields
- `Span` (line 601) — `width`/`height` → `waxy.Style.size_width`/`size_height`
- `Margin` (line 581) — `top/bottom/left/right` → `waxy.Style.margin_*`; `color` → `Style.margin_color`
- `Padding` (line 589) — same split as Margin
- `Content` (line 597) — `color` → `Style.content_color`
- `Typography` (line 606) — `style/justify/wrap` → `Style.text_style/text_justify/text_wrap`
- `Border` (line 574) — `kind/style/edges/contract` → `Style.border_kind/border_style/border_edges/border_contract`; border widths → `waxy.Style.border_*`
- `Relative` (line 612) — replaced by `waxy.Position.Relative` + `waxy.Style.inset_*`
- `Absolute` (line 629) — replaced by `waxy.Position.Absolute` + `waxy.Style.inset_*`
- `Fixed` (line 644) — dropped entirely (not used outside docs example)
- `Inset` (line 624) — replaced by `waxy.Style.inset_*`

**Keep these classes unchanged:**
- `Color` (line 95) — used everywhere for visual colors
- `CellStyle` (line 273) — used for text and border rendering (7 fields, too many to flatten further)
- `BorderKind` (line 295) — enum of border character sets
- `JoinedBorderKind` (line 509) — enum for border healing
- `StyleFragment` (line 46) — base class still needed for merge logic

**Delete** (in addition to the classes listed above):
- `BorderEdge` (line 567) — no longer needed; which edges are active is derived from
  `waxy.Style.border_*` widths at paint time

**Modify `Style`** (line 678):
Replace all 7 fields with the flattened structure shown in Design Decision §1.

**Modify `StyleFragment.mergeable_dump()`** (line 67):
Add handling for the `layout` field: skip it in `mergeable_dump()` since `waxy.Style`
is not a `StyleFragment`. The `__or__` method handles it separately.

**Modify `Style.__or__`**:
Override to merge `layout` via `waxy.Style.__or__` and visual fields via `StyleFragment` logic.

**Mapping of old field paths → new:**

| Old path | New location |
|----------|-------------|
| `style.layout.direction` | `style.layout` (`waxy.Style(flex_direction=...)`) |
| `style.layout.position` | `style.layout` (`waxy.Style(position=...)`) — Relative/Absolute only; Fixed dropped |
| `style.layout.weight` | `style.layout` (`waxy.Style(flex_grow=...)`) |
| `style.layout.z` | `style.z` |
| `style.layout.align_self` | `style.layout` (`waxy.Style(align_self=...)`) |
| `style.layout.justify_children` | `style.layout` (`waxy.Style(justify_content=...)`) |
| `style.layout.align_children` | `style.layout` (`waxy.Style(align_items=...)`) |
| `style.layout.gap_children` | `style.layout` (`waxy.Style(gap_width=..., gap_height=...)`) |
| `style.span.width` | `style.layout` (`waxy.Style(size_width=waxy.Length(n))` or `waxy.AUTO`) |
| `style.span.height` | `style.layout` (`waxy.Style(size_height=waxy.Length(n))` or `waxy.AUTO`) |
| `style.margin.top/bottom/left/right` | `style.layout` (`waxy.Style(margin_top=waxy.Length(n), ...)`) |
| `style.margin.color` | `style.margin_color` |
| `style.padding.top/bottom/left/right` | `style.layout` (`waxy.Style(padding_top=waxy.Length(n), ...)`) |
| `style.padding.color` | `style.padding_color` |
| `style.content.color` | `style.content_color` |
| `style.border` (None/Border) | `style.border_kind` (None/BorderKind) + layout border widths |
| `style.border.kind` | `style.border_kind` |
| `style.border.style` | `style.border_style` |
| `style.border.edges` | Dropped — derived from `waxy.Style.border_*` widths at paint time |
| `style.border.contract` | `style.border_contract` |
| `style.typography.style` | `style.text_style` |
| `style.typography.justify` | `style.text_justify` |
| `style.typography.wrap` | `style.text_wrap` |

**Counterweight `Flex` field → `waxy.Style` field mapping:**

| Counterweight `Flex` field | waxy.Style field | Conversion |
|---------------------------|-----------------|------------|
| `direction="row"` | `flex_direction=waxy.FlexDirection.Row` | Direct enum mapping |
| `direction="column"` | `flex_direction=waxy.FlexDirection.Column` | Direct enum mapping |
| `weight=N` (N>0) | `flex_grow=float(N), flex_basis=waxy.Length(0)` | `flex_basis=0` makes `flex_grow` distribute all space |
| `weight=None` (fixed) | `flex_grow=0.0` | Default: don't grow |
| `align_self="none"` | (don't set) | waxy default = no override |
| `align_self="start"` | `align_self=waxy.AlignItems.Start` | |
| `align_self="center"` | `align_self=waxy.AlignItems.Center` | |
| `align_self="end"` | `align_self=waxy.AlignItems.End` | |
| `align_self="stretch"` | `align_self=waxy.AlignItems.Stretch` | |
| `justify_children="start"` | `justify_content=waxy.AlignContent.Start` | |
| `justify_children="center"` | `justify_content=waxy.AlignContent.Center` | |
| `justify_children="end"` | `justify_content=waxy.AlignContent.End` | |
| `justify_children="space-between"` | `justify_content=waxy.AlignContent.SpaceBetween` | |
| `justify_children="space-around"` | `justify_content=waxy.AlignContent.SpaceAround` | |
| `justify_children="space-evenly"` | `justify_content=waxy.AlignContent.SpaceEvenly` | |
| `align_children="start"` | `align_items=waxy.AlignItems.Start` | |
| `align_children="center"` | `align_items=waxy.AlignItems.Center` | |
| `align_children="end"` | `align_items=waxy.AlignItems.End` | |
| `align_children="stretch"` | `align_items=waxy.AlignItems.Stretch` | |
| `gap_children=N` | `gap_width=waxy.Length(N), gap_height=waxy.Length(N)` | Now split into `gap_width_N`, `gap_height_N`, `gap_N` |
| `position=Relative(x, y)` | `position=waxy.Position.Relative, inset_left=waxy.Length(x), inset_top=waxy.Length(y)` | |
| `position=Absolute(x, y)` | `position=waxy.Position.Absolute, inset_left=waxy.Length(x), inset_top=waxy.Length(y)` | |
| `position=Fixed(x, y)` | **Dropped** — delete `Fixed` class, `fixed()` utility, and doc example | |

**New waxy.Style fields with no counterweight predecessor** (exposed via generated utilities or helpers):

| waxy.Style field | Utility / Helper | Notes |
|-----------------|-----------------|-------|
| `flex_shrink=float` | `shrink_0`, `shrink_1`, `shrink_2`, `shrink_3` | taffy default is 1.0 (CSS spec) |
| `flex_wrap=waxy.FlexWrap.*` | `flex_no_wrap`, `flex_wrap`, `flex_wrap_reverse` | Painting unaffected — taffy resolves positions |
| `display=waxy.Display.*` | `display_flex`, `display_block`, `display_grid`, `display_none` | `display_none` elements skipped in layout extraction |
| `min_size_width`, `min_size_height` | `min_width(n)`, `min_height(n)` | |
| `max_size_width`, `max_size_height` | `max_width(n)`, `max_height(n)` | |
| `aspect_ratio` | `aspect_ratio(ratio)` | |
| `gap_width` | `gap_width_N` | Per-axis gap (width direction) |
| `gap_height` | `gap_height_N` | Per-axis gap (height direction) |
| `justify_items` | `justify_items_start`, etc. | Used in grid layout |
| `justify_self` | `justify_self_start`, etc. | Used in grid layout |
| `grid_auto_flow` | `grid_auto_flow_row`, `_column`, `_row_dense`, `_column_dense` | |
| `grid_template_rows` | `grid_template_rows(*tracks)` | Helper function |
| `grid_template_columns` | `grid_template_columns(*tracks)` | Helper function |
| `grid_row`, `grid_column` | `grid_row(start, end)`, `grid_column(start, end)` | Helper functions |

### Step 2: Update `codegen/generate_utilities.py` and regenerate `styles/utilities.py` ✅ DONE

The utilities are generated by `codegen/generate_utilities.py`. The generator already
uses some introspection (`get_type_hints`/`get_args` via `literal_vals()`). It should
be enhanced to introspect the new `Style` class and waxy types rather than hardcoding
the old nested style constructors.

**Current generator structure** (`codegen/generate_utilities.py`):
- Imports: `Flex`, `Typography`, `BorderKind`, `BorderEdge` from counterweight styles
- `literal_vals(obj, field)`: introspects `Literal` type args from type hints
- `COLORS` dict: Tailwind color palette (22 families × 11 shades) — unchanged
- Generates lines between `# Start generated` / `# Stop generated` markers in `utilities.py`
- `utilities.py` also has a non-generated footer with `relative()`, `absolute()`,
  `fixed()`, `z()` helper functions

**Implementation note:** The generator stubs out `sys.modules["counterweight"]` before
importing `counterweight.styles.styles`. This avoids triggering `counterweight/__init__.py`
(which imports `app.py` → `layout.py` → deleted names) during the migration when other
files still have broken imports. The stub sets `__path__` to the real package directory so
submodule imports still resolve correctly.

**Changes to the generator:**

1. **Update imports** — remove `Flex`, `Typography`, `Border`, `Margin`, `Padding`,
   `Content`, `Absolute`, `Inset`. Add `import waxy`.

2. **Color utilities** — update the generation templates to use flattened Style fields:

   ```python
   # OLD:
   f"text_{color}_{shade} = Style(typography=Typography(style=CellStyle(foreground={color}_{shade})))"
   f"border_{color}_{shade} = Style(border=Border(style=CellStyle(foreground={color}_{shade})))"
   f"margin_{color}_{shade} = Style(margin=Margin(color={color}_{shade}))"
   f"padding_{color}_{shade} = Style(padding=Padding(color={color}_{shade}))"
   f"content_{color}_{shade} = Style(content=Content(color={color}_{shade}))"

   # NEW:
   f"text_{color}_{shade} = Style(text_style=CellStyle(foreground={color}_{shade}))"
   f"border_{color}_{shade} = Style(border_style=CellStyle(foreground={color}_{shade}))"
   f"margin_{color}_{shade} = Style(margin_color={color}_{shade})"
   f"padding_{color}_{shade} = Style(padding_color={color}_{shade})"
   f"content_{color}_{shade} = Style(content_color={color}_{shade})"
   ```

   Similarly for `text_white`/`text_black` and `text_bg_*`/`border_bg_*`.

3. **Direction utilities** — introspect `waxy.FlexDirection` enum members instead of
   `literal_vals(Flex, "direction")`:

   ```python
   # OLD:
   for d in literal_vals(Flex, "direction"):
       f'{d[:3]} = Style(layout=Flex(direction="{d}"))'

   # NEW:
   DIRECTION_ALIASES = {"Row": "row", "Column": "col"}
   for member in waxy.FlexDirection:
       alias = DIRECTION_ALIASES.get(member.name)
       if alias:
           f"{alias} = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.{member.name}))"
   ```

   Generate all four directions including reverse variants:
   ```python
   DIRECTION_ALIASES = {
       "Row": "row", "Column": "col",
       "RowReverse": "row_reverse", "ColumnReverse": "col_reverse",
   }
   ```

4. **Justify/align utilities** — introspect `waxy.AlignContent` and `waxy.AlignItems`
   enum members:

   ```python
   # OLD: iterated literal_vals(Flex, "justify_children") → "start", "center", etc.
   # NEW: iterate waxy.AlignContent members
   JUSTIFY_MAP = {
       "Start": "start", "Center": "center", "End": "end",
       "SpaceBetween": "space_between", "SpaceAround": "space_around",
       "SpaceEvenly": "space_evenly",
   }
   for member in waxy.AlignContent:
       name = JUSTIFY_MAP.get(member.name)
       if name:
           f"justify_children_{name} = Style(layout=waxy.Style(justify_content=waxy.AlignContent.{member.name}))"

   # Similarly for align_children (waxy.AlignItems) and align_self (waxy.AlignItems)
   # Also generate justify_items and justify_self (used in grid layout)
   ALIGN_MAP = {
       "Start": "start", "Center": "center", "End": "end", "Stretch": "stretch",
   }
   for member in waxy.AlignItems:
       name = ALIGN_MAP.get(member.name)
       if name:
           f"align_children_{name} = Style(layout=waxy.Style(align_items=waxy.AlignItems.{member.name}))"
           f"align_self_{name} = Style(layout=waxy.Style(align_self=waxy.AlignItems.{member.name}))"
           f"justify_items_{name} = Style(layout=waxy.Style(justify_items=waxy.AlignItems.{member.name}))"
           f"justify_self_{name} = Style(layout=waxy.Style(justify_self=waxy.AlignItems.{member.name}))"
   ```

   The `_MAP` dicts filter to only the members we want utilities for (waxy enums may have
   additional members like `FlexStart`/`FlexEnd`/`Baseline` that we don't need).

   Note: `justify_items` and `justify_self` use `AlignItems` (not `AlignContent`) — this
   matches the CSS spec where these properties accept alignment keywords, and waxy models
   them with the same `AlignItems` enum.

5. **Weight utilities**:

   ```python
   # OLD: weight_none = Style(layout=Flex(weight=None)); weight_N = Style(layout=Flex(weight=N))
   # NEW:
   f"weight_none = Style(layout=waxy.Style(flex_grow=0.0))"
   for n in range(1, 9):
       f"weight_{n} = Style(layout=waxy.Style(flex_grow={float(n)}, flex_basis=waxy.Length(0)))"
   ```

6. **Shrink utilities**:

   ```python
   # NEW (no counterweight equivalent existed):
   f"shrink_0 = Style(layout=waxy.Style(flex_shrink=0.0))"
   for n in range(1, 4):
       f"shrink_{n} = Style(layout=waxy.Style(flex_shrink={float(n)}))"
   ```

   Note: taffy's default `flex_shrink` is `1.0` (per CSS spec). This differs from the old
   engine which had no shrink concept. Users may need `shrink_0` to prevent items from
   shrinking below their basis.

7. **Flex wrap utilities**:

   ```python
   # NEW (no counterweight equivalent existed):
   WRAP_MAP = {
       "NoWrap": "no_wrap", "Wrap": "wrap", "WrapReverse": "wrap_reverse",
   }
   for member in waxy.FlexWrap:
       name = WRAP_MAP.get(member.name)
       if name:
           f"flex_{name} = Style(layout=waxy.Style(flex_wrap=waxy.FlexWrap.{member.name}))"
   ```

   Painting is unaffected by flex wrap — taffy resolves wrapped items to absolute positions
   and the paint code draws each element at its resolved rect regardless of flow.

8. **Display mode utilities**:

   ```python
   # NEW (no counterweight equivalent existed):
   f"display_flex = Style(layout=waxy.Style(display=waxy.Display.Flex))"
   f"display_block = Style(layout=waxy.Style(display=waxy.Display.Block))"
   f"display_grid = Style(layout=waxy.Style(display=waxy.Display.Grid))"
   f"display_none = Style(layout=waxy.Style(display=waxy.Display.Nil))"
   ```

9. **Grid auto-flow utilities**:

   ```python
   # NEW (no counterweight equivalent existed):
   GRID_FLOW_MAP = {
       "Row": "row", "Column": "column",
       "RowDense": "row_dense", "ColumnDense": "column_dense",
   }
   for member in waxy.GridAutoFlow:
       name = GRID_FLOW_MAP.get(member.name)
       if name:
           f"grid_auto_flow_{name} = Style(layout=waxy.Style(grid_auto_flow=waxy.GridAutoFlow.{member.name}))"
   ```

10. **Border kind utilities** — introspect `BorderKind` enum (unchanged source, new output):

   ```python
   # OLD: border_light = Style(border=Border(kind=BorderKind.Light))
   # NEW: set both layout widths AND visual kind (no border_edges needed)
   f"border_none = Style(border_kind=None)"
   for b in BorderKind:
       f"""border_{b.name.lower()} = Style(
       layout=waxy.Style(
           border_top=waxy.Length(1), border_bottom=waxy.Length(1),
           border_left=waxy.Length(1), border_right=waxy.Length(1),
       ),
       border_kind=BorderKind.{b.name},
   )"""
   ```

7. **Border edge selection utilities** — generate per-edge and combination utilities.
   No `BorderEdge` enum needed — just set the relevant `waxy.Style.border_*` widths:

   ```python
   # OLD: border_top = Style(border=Border(edges=frozenset({BorderEdge.Top})))
   # NEW: just set the waxy border widths for the selected edges
   EDGE_SIDES = ["top", "bottom", "left", "right"]
   for edges in flatten(combinations(EDGE_SIDES, r) for r in range(1, 4)):
       border_widths = ", ".join(
           f"border_{side}=waxy.Length(1)" for side in edges
       )
       f"border_{'_'.join(edges)} = Style("
       f"    layout=waxy.Style({border_widths}),"
       f")"
   ```

   Note: these edge selection utilities don't set `border_kind` — they're meant to be
   merged with a kind utility via `|`, e.g. `border_light | border_top`.

8. **Padding/margin utilities** — use `waxy.Style` fields:

   ```python
   # OLD: pad_top_1 = Style(padding=Padding(top=1))
   # NEW: pad_top_1 = Style(layout=waxy.Style(padding_top=waxy.Length(1)))
   for side in SIDES:
       for n in N:
           f"pad_{side}_{n} = Style(layout=waxy.Style(padding_{side}=waxy.Length({n})))"

   # pad_x_N, pad_y_N, pad_N similarly set multiple waxy.Style fields
   for n in N:
       f"pad_x_{n} = Style(layout=waxy.Style(padding_left=waxy.Length({n}), padding_right=waxy.Length({n})))"
       f"pad_y_{n} = Style(layout=waxy.Style(padding_top=waxy.Length({n}), padding_bottom=waxy.Length({n})))"
       f"pad_{n} = Style(layout=waxy.Style(padding_top=waxy.Length({n}), padding_bottom=waxy.Length({n}), padding_left=waxy.Length({n}), padding_right=waxy.Length({n})))"

   # Same pattern for margin_* → waxy.Style(margin_*)
   ```

9. **Gap utilities**:

   ```python
   # OLD: gap_children_N = Style(layout=Flex(gap_children=N))
   # NEW: use taffy/waxy field names
   for n in N:
       f"gap_width_{n} = Style(layout=waxy.Style(gap_width=waxy.Length({n})))"
       f"gap_height_{n} = Style(layout=waxy.Style(gap_height=waxy.Length({n})))"
       f"gap_{n} = Style(layout=waxy.Style(gap_width=waxy.Length({n}), gap_height=waxy.Length({n})))"
   ```

10. **Typography justify** — introspect from the new `Style.text_justify` field's `Literal` type:

    ```python
    # OLD: literal_vals(Typography, "justify")
    # NEW: literal_vals(Style, "text_justify")
    for j in literal_vals(Style, "text_justify"):
        f'text_justify_{j} = Style(text_justify="{j}")'
    ```

11. **Inset utilities** — these previously introspected `Inset.vertical`/`Inset.horizontal`.
    The approach with waxy is TBD (see Open Questions §2 about centered absolute positioning).
    For now, generate the non-center variants using `inset_*` fields:

    ```python
    VERTICAL = {"top": "inset_top=waxy.Length(0)", "bottom": "inset_bottom=waxy.Length(0)"}
    HORIZONTAL = {"left": "inset_left=waxy.Length(0)", "right": "inset_right=waxy.Length(0)"}
    # center variants need investigation — may use auto margins or align_self/justify_self
    ```

12. **Border contract**:

    ```python
    # OLD: border_contract_N = Style(border=Border(contract=N))
    # NEW:
    for n in N:
        f"border_contract_{n} = Style(border_contract={n})"
    ```

**Changes to `utilities.py` non-generated footer** (lines 2218-2231):

These are hand-written helpers for Style fields that take arbitrary values
(not enumerable, so can't be pre-generated). Together with the generated
utilities, they should cover the full commonly-used API surface.

```python
# --- Kept (updated for waxy) ---

def relative(x: int = 0, y: int = 0) -> Style:
    return Style(layout=waxy.Style(
        position=waxy.Position.Relative,
        inset_left=waxy.Length(x),
        inset_top=waxy.Length(y),
    ))

def absolute(x: int = 0, y: int = 0) -> Style:
    return Style(layout=waxy.Style(
        position=waxy.Position.Absolute,
        inset_left=waxy.Length(x),
        inset_top=waxy.Length(y),
    ))

def z(z: int = 0) -> Style:
    return Style(z=z)

# --- Deleted ---
# fixed() — Fixed positioning dropped for now

# --- New helpers (replacing Span and filling API gaps) ---

def width(n: int) -> Style:
    """Set explicit width. Replaces Span(width=N)."""
    return Style(layout=waxy.Style(size_width=waxy.Length(n)))

def height(n: int) -> Style:
    """Set explicit height. Replaces Span(height=N)."""
    return Style(layout=waxy.Style(size_height=waxy.Length(n)))

def size(w: int, h: int) -> Style:
    """Set explicit width and height. Replaces Span(width=W, height=H)."""
    return Style(layout=waxy.Style(size_width=waxy.Length(w), size_height=waxy.Length(h)))

def min_width(n: int) -> Style:
    return Style(layout=waxy.Style(min_size_width=waxy.Length(n)))

def min_height(n: int) -> Style:
    return Style(layout=waxy.Style(min_size_height=waxy.Length(n)))

def max_width(n: int) -> Style:
    return Style(layout=waxy.Style(max_size_width=waxy.Length(n)))

def max_height(n: int) -> Style:
    return Style(layout=waxy.Style(max_size_height=waxy.Length(n)))

def aspect_ratio(ratio: float) -> Style:
    return Style(layout=waxy.Style(aspect_ratio=ratio))

# --- Grid helpers ---

def grid_template_rows(*tracks: GridTrackValue) -> Style:
    return Style(layout=waxy.Style(grid_template_rows=list(tracks)))

def grid_template_columns(*tracks: GridTrackValue) -> Style:
    return Style(layout=waxy.Style(grid_template_columns=list(tracks)))

def grid_row(start: GridPlacementValue | None = None, end: GridPlacementValue | None = None) -> Style:
    return Style(layout=waxy.Style(grid_row=waxy.GridPlacement(start=start, end=end)))

def grid_column(start: GridPlacementValue | None = None, end: GridPlacementValue | None = None) -> Style:
    return Style(layout=waxy.Style(grid_column=waxy.GridPlacement(start=start, end=end)))
```

**Why these helpers are needed:**
- `width()`/`height()`/`size()` replace `Span(width=N, height=N)` which was the primary
  way to set explicit dimensions. Used in `app.py` (screen root), `examples/mouse.py`,
  and tests. Without these, users would write
  `Style(layout=waxy.Style(size_width=waxy.Length(20), size_height=waxy.Length(10)))`.
- `min_width()`/`max_width()`/`min_height()`/`max_height()` — constrained sizing is
  common enough to warrant helpers over raw `waxy.Style(min_size_width=waxy.Length(n))`.
- `grid_template_rows()`/`grid_template_columns()` — grid track definitions take lists
  of track values; a helper with `*tracks` varargs is much more ergonomic than building
  a `waxy.Style` with a list literal.
- `grid_row()`/`grid_column()` — wrap `waxy.GridPlacement` construction.
- `relative()`/`absolute()` take arbitrary x/y coordinates — can't be pre-generated.
- `z()` takes an arbitrary z-index value.

**Not adding helpers for** (can use `waxy.Style(...)` directly for these rare cases):
- `flex_grow()`/`flex_shrink()`/`flex_basis()` — the `weight_N`/`shrink_N` utilities cover
  most flex usage; power users can set `layout=waxy.Style(flex_grow=2.5)` directly.
- `overflow()` — not yet useful (see future work on scrolling).

**Update `utilities.py` imports** (non-generated header, lines 1-17):

```python
# OLD:
from counterweight.styles import (
    Absolute, Border, BorderEdge, BorderKind, CellStyle,
    Color, Content, Fixed, Flex, Inset, Margin, Padding,
    Relative, Style, Typography,
)

# NEW:
import waxy
from counterweight.styles import BorderKind, CellStyle, Color, Style
```

**Workflow:** After updating `codegen/generate_utilities.py`, run it to regenerate
`utilities.py`. The generator is idempotent — it replaces the block between
`# Start generated` / `# Stop generated` markers.

### Step 3: Update `styles/__init__.py` ✅ DONE (completed as part of Step 1)

Current exports (line 1-6):
```python
__all__ = [
    "Absolute", "Border", "BorderEdge", "BorderKind", "CellStyle",
    "Color", "Content", "Fixed", "Flex", "Inset", "Margin",
    "Padding", "Relative", "Span", "Style", "Typography",
]
```

**New exports** (remove deleted classes, add nothing new — `waxy` types imported directly):
```python
__all__ = [
    "BorderKind", "CellStyle", "Color", "Style",
]
```

### Step 4: Rewrite `layout.py` ✅ DONE

**Delete entirely:**
- `LayoutBox` class (line 63) and all methods (`walk_from_top`, `walk_from_bottom`,
  `walk_levels`, `compute_layout`, `first_pass`, `second_pass`)
- `LayoutBoxDimensions` class (line 24)
- `build_layout_tree_from_shadow()` (in `app.py:470`, but it's layout-related)

**Keep:**
- `wrap_cells()` function (line 436) — still needed for text measurement.
  Update signature to accept `width: int | None` (None = no constraint) and
  narrow `wrap` to `Literal["none"]` (the `"paragraphs"` variant was never implemented).
  Currently takes `width: int` and only implements `wrap="none"`.

**Add new types and functions:**

```python
import waxy
from counterweight.shadow import ShadowNode
from counterweight.elements import AnyElement, Text

@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: waxy.Rect
    padding: waxy.Rect
    border: waxy.Rect
    margin: waxy.Rect


def compute_layout(
    shadow: ShadowNode,
    available_width: int,
    available_height: int,
) -> list[tuple[AnyElement, ResolvedLayout]]:
    """
    Build a waxy tree from the shadow tree, compute layout, and return
    a flat list of (element, resolved_layout) pairs.
    """
    tree: waxy.TaffyTree[Text] = waxy.TaffyTree()
    node_map: dict[waxy.NodeId, ShadowNode] = {}

    # Phase 1: Build waxy tree bottom-up
    root_id = _build_node(tree, shadow, node_map)

    # Phase 2: Compute layout (enable rounding for integer terminal coordinates)
    tree.enable_rounding()
    available = waxy.AvailableSize(
        width=waxy.Definite(available_width),
        height=waxy.Definite(available_height),
    )
    tree.compute_layout(root_id, available, measure=_measure_text)

    # Phase 3: Extract results top-down
    results: list[tuple[AnyElement, ResolvedLayout]] = []
    _extract_layout(tree, root_id, node_map, abs_x=0.0, abs_y=0.0, results=results)

    return results


def _build_node(
    tree: waxy.TaffyTree[Text],
    shadow: ShadowNode,
    node_map: dict[waxy.NodeId, ShadowNode],
) -> waxy.NodeId:
    """Build a waxy node for this shadow node, recursively building children."""
    element = shadow.element

    match element:
        case Text():
            node_id = tree.new_leaf_with_context(element.style.layout, element)
        case Div():
            child_ids = [
                _build_node(tree, child_shadow, node_map)
                for child_shadow in shadow.children
            ]
            node_id = tree.new_with_children(element.style.layout, child_ids)
        case _:
            assert_never(element)

    node_map[node_id] = shadow
    return node_id


def _measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: Text,
) -> waxy.Size:
    """Measure callback for text leaf nodes.

    Note: taffy may call this with MinContent or MaxContent available space
    (not just Definite). For now we treat both as unconstrained (width=None).
    When we expand text wrapping options beyond "none", MinContent should
    return the width of the longest word and MaxContent the full unwrapped width.
    """
    width: float | None = known.width
    if width is None and isinstance(available.width, waxy.Definite):
        width = available.width.value

    lines = wrap_cells(
        context.cells,
        context.style.text_wrap,
        int(width) if width is not None else None,
    )

    return waxy.Size(
        width=known.width if known.width is not None else float(max((len(l) for l in lines), default=0)),
        height=known.height if known.height is not None else float(len(lines)),
    )


def _extract_layout(
    tree: waxy.TaffyTree[Text],
    node_id: waxy.NodeId,
    node_map: dict[waxy.NodeId, ShadowNode],
    abs_x: float,
    abs_y: float,
    results: list[tuple[AnyElement, ResolvedLayout]],
) -> None:
    """Walk tree top-down, accumulating absolute positions.

    abs_x/abs_y is the absolute position of the parent's border box origin.
    For the root node, this is (0, 0) — taffy places the root at the origin
    with location (0, 0) since there is no parent to position it relative to.
    """
    layout = tree.layout(node_id)  # returns rounded Layout
    shadow = node_map[node_id]

    # Skip elements with display: none — taffy excludes them from layout
    # and they should not be painted or hit-tested.
    if shadow.element.style.layout.display == waxy.Display.Nil:
        return

    # location is relative to parent's border box and points to this node's border box
    border_abs_x = abs_x + layout.location.x
    border_abs_y = abs_y + layout.location.y

    # Build rects starting from the border box (what location + size describe).
    # waxy.Rect uses inclusive (left, right, top, bottom).
    # layout.size is the border box pixel count, so right = left + width - 1.
    bx = int(border_abs_x)
    by = int(border_abs_y)
    bw = int(layout.size.width)
    bh = int(layout.size.height)

    border_rect = waxy.Rect(left=bx, right=bx + bw - 1, top=by, bottom=by + bh - 1)

    # Margin rect: border box expanded outward by margin widths
    margin_rect = waxy.Rect(
        left=bx - int(layout.margin.left),
        right=bx + bw - 1 + int(layout.margin.right),
        top=by - int(layout.margin.top),
        bottom=by + bh - 1 + int(layout.margin.bottom),
    )
    # Padding rect: border box shrunk inward by border widths
    pl = bx + int(layout.border.left)
    pt = by + int(layout.border.top)
    pr = bx + bw - 1 - int(layout.border.right)
    pb = by + bh - 1 - int(layout.border.bottom)
    padding_rect = waxy.Rect(left=pl, right=pr, top=pt, bottom=pb)

    # Content rect: padding box shrunk inward by padding widths
    content_rect = waxy.Rect(
        left=pl + int(layout.padding.left),
        right=pr - int(layout.padding.right),
        top=pt + int(layout.padding.top),
        bottom=pb - int(layout.padding.bottom),
    )

    resolved = ResolvedLayout(
        content=content_rect,
        padding=padding_rect,
        border=border_rect,
        margin=margin_rect,
        order=layout.order,
    )
    results.append((shadow.element, resolved))

    # Store dims for use_rects() hook
    shadow.hooks.dims = resolved  # type change: was LayoutBoxDimensions, now ResolvedLayout

    # Recurse into children — their locations are relative to this node's border box
    for child_node_id, child_shadow in zip(tree.children(node_id), shadow.children):
        _extract_layout(tree, child_node_id, node_map, border_abs_x, border_abs_y, results)
```

### Step 5: Adapt `paint.py` ✅ DONE

**`paint_layout`** (line 54):
Currently takes `LayoutBox` and walks the tree. Change to accept
`list[tuple[AnyElement, ResolvedLayout]]`:

```python
def paint_layout(
    elements: list[tuple[AnyElement, ResolvedLayout]],
) -> tuple[Paint, BorderHealingHints]:
    parts: list[tuple[Paint, BorderHealingHints, int, int]] = [
        paint_element(element, resolved) for element, resolved in elements
    ]
    # Sort by (z-index, taffy order): z is user-controlled priority,
    # order is taffy's computed topological paint sequence as tiebreaker
    parts.sort(key=lambda p: (p[2], p[3]))
    paint: Paint = {}
    bhh: BorderHealingHints = {}
    for p, b, _, _ in parts:
        paint |= p
        bhh |= b
    return paint, bhh
```

**`paint_element`** (line 72):
Currently: `paint_element(element: AnyElement, dims: LayoutBoxDimensions) -> tuple[Paint, BorderHealingHints, int]`

Change to: `paint_element(element: AnyElement, resolved: ResolvedLayout) -> tuple[Paint, BorderHealingHints, int, int]`

Returns `(paint, hints, z, order)` where `z` is `element.style.z` and `order` is `resolved.order`.

Replace:
- `dims.padding_border_margin_rects()` → `resolved.padding`, `resolved.border`, `resolved.margin`
- `dims.content` → `resolved.content`
- `element.style.margin` → need `element.style.margin_color` + compute margin edge from resolved rects
- `element.style.padding` → need `element.style.padding_color` + compute padding edge from resolved rects
- `element.style.border` → `element.style.border_kind is not None`
- `element.style.content.color` → `element.style.content_color`
- `element.style.layout.z` → `element.style.z`
- Rename `paint_bg()` → `fill_rect()` (better describes what it does: fills a rectangular area)

**`paint_edge`** (line 160):
Currently: `paint_edge(element, mp: Margin | Padding, edge: Edge, rect: Rect) -> Paint`

Simplify to: `paint_edge(outer: waxy.Rect, inner: waxy.Rect, color: Color, z: int) -> Paint`

Instead of using `Edge` thicknesses, compute the band between `outer` and `inner` rects directly.
Use `waxy.Rect` for each strip and iterate its `.points()`:
- Top strip: `Rect(left=outer.left, right=outer.right, top=outer.top, bottom=inner.top - 1)`
- Bottom strip: `Rect(left=outer.left, right=outer.right, top=inner.bottom + 1, bottom=outer.bottom)`
- Left strip: `Rect(left=outer.left, right=inner.left - 1, top=inner.top, bottom=inner.bottom)`
- Right strip: `Rect(left=inner.right + 1, right=outer.right, top=inner.top, bottom=inner.bottom)`
Skip any strip where the rect would be degenerate (e.g. `top > bottom`).

Caller passes:
- Margin band: `paint_edge(resolved.margin, resolved.border, element.style.margin_color, element.style.z)`
- Padding band: `paint_edge(resolved.border, resolved.content, element.style.padding_color, element.style.z)`

Wait — padding band should be between `resolved.padding` and `resolved.content`, not `resolved.border`
and `resolved.content`. And the border occupies the band between `resolved.border` and `resolved.padding`.
So:
- Margin band: `outer=resolved.margin, inner=resolved.border`
- Border: drawn on `resolved.border` rect (the 1-cell-wide edge of that rect)
- Padding band: `outer=resolved.padding, inner=resolved.content`

**`paint_border`** (line 188):
Currently: `paint_border(element, border: Border, rect: Rect) -> tuple[Paint, BorderHealingHints]`

Change to: `paint_border(style: Style, resolved: ResolvedLayout) -> tuple[Paint, BorderHealingHints]`

The `border_edges` field is removed. Instead, derive which edges to draw from the
resolved layout's border widths (which come from `waxy.Layout.border`):

```python
def paint_border(style: Style, resolved: ResolvedLayout) -> tuple[Paint, BorderHealingHints]:
    bk = style.border_kind
    if bk is None:
        return {}, {}

    cell_style = style.border_style
    bv = bk.value
    z = style.z
    contract = style.border_contract

    rect = resolved.border

    # Derive which edges to draw from the resolved layout border widths.
    # Compare border_rect vs padding_rect — a gap means a nonzero border width.
    draw_left = resolved.padding.left > resolved.border.left
    draw_right = resolved.border.right > resolved.padding.right
    draw_top = resolved.padding.top > resolved.border.top
    draw_bottom = resolved.border.bottom > resolved.padding.bottom

    # Contract: shorten border lines on open edges by N cells
    if contract:
        contract_top = contract if not draw_top else None
        contract_bottom = -contract if not draw_bottom else None
        contract_left = contract if not draw_left else None
        contract_right = -contract if not draw_right else None
    else:
        contract_top = contract_bottom = contract_left = contract_right = None

    # Note: waxy edge methods return Iterator[Point], not sequences, so they
    # don't support slice indexing. Use itertools.islice instead.
    chars = {}

    if draw_left:
        left_paint = P(char=bv.left, style=cell_style, z=z)
        for p in islice(rect.left_edge(), contract_top, contract_bottom):
            chars[p] = left_paint

    if draw_right:
        right_paint = P(char=bv.right, style=cell_style, z=z)
        for p in islice(rect.right_edge(), contract_top, contract_bottom):
            chars[p] = right_paint

    if draw_top:
        top_paint = P(char=bv.top, style=cell_style, z=z)
        for p in islice(rect.top_edge(), contract_left, contract_right):
            chars[p] = top_paint
        if draw_left:
            chars[Position.flyweight(x=rect.left, y=rect.top)] = P(char=bv.left_top, style=cell_style, z=z)
        if draw_right:
            chars[Position.flyweight(x=rect.right, y=rect.top)] = P(char=bv.right_top, style=cell_style, z=z)

    if draw_bottom:
        bottom_paint = P(char=bv.bottom, style=cell_style, z=z)
        for p in islice(rect.bottom_edge(), contract_left, contract_right):
            chars[p] = bottom_paint
        if draw_left:
            chars[Position.flyweight(x=rect.left, y=rect.bottom)] = P(char=bv.left_bottom, style=cell_style, z=z)
        if draw_right:
            chars[Position.flyweight(x=rect.right, y=rect.bottom)] = P(char=bv.right_bottom, style=cell_style, z=z)

    # Border healing hints
    try:
        jbv = JoinedBorderKind[bk.name].value
        bhh = {k: jbv for k in chars.keys()}
    except KeyError:
        bhh = {}

    return chars, bhh
```

The key insight: `draw_left = resolved.padding.x > resolved.border.x` is true exactly
when there's a nonzero border width on the left (i.e., `waxy.Style.border_left` was set
to `Length(1)`). This replaces the old `BorderEdge.Left in border.edges` check.

**`paint_text`** (line 128):
Currently: `paint_text(text: Text, rect: Rect) -> Paint`

Change to: `paint_text(text: Text, rect: waxy.Rect) -> Paint`

Note: `waxy.Rect.width` is `right - left` (one less than pixel count). For text
wrapping and slicing, use `int(rect.width) + 1` where the old code used `rect.width`,
and `int(rect.height) + 1` where the old code used `rect.height`. Use `rect.left` /
`rect.top` where the old code used `rect.x` / `rect.y`.

Replace:
- `text.style.typography.style` → `text.style.text_style`
- `text.style.typography.wrap` → `text.style.text_wrap`
- `text.style.typography.justify` → `text.style.text_justify`
- `text.style.layout.z` → `text.style.z`

**Delete from `geometry.py`:**
- `Edge` class (line 103) — no longer needed
- `Rect` class (line 37) — replaced by `waxy.Rect` everywhere

**Keep in `geometry.py`:**
- `Position` (line 12) — heavily used in painting. `waxy.Point` is unhashable and
  stores floats, so it can't be used as a dict key in `Paint`. Add a conversion method:
  ```python
  @classmethod
  def from_point(cls, point: waxy.Point) -> Position:
      return cls.flyweight(int(point.x), int(point.y))
  ```
  Use `Position.from_point(p)` when iterating `waxy.Rect` edge/point methods in paint code.

**Keep in `_utils.py`:**
- `halve_integer()` (line 27) — still used by `paint.py:justify_line`

### Step 6: Update `app.py` ✅ DONE

**Render pipeline** (lines 269-337):

Replace:
```python
# OLD (lines 278-279):
layout_tree = build_layout_tree_from_shadow(shadow)
layout_tree.compute_layout()
# ...
new_paint, border_healing_hints = paint_layout(layout_tree)

# NEW:
from counterweight.layout import compute_layout as compute_layout_new
elements_and_layouts = compute_layout_new(shadow, w, h)
new_paint, border_healing_hints = paint_layout(elements_and_layouts)
```

**Screen root wrapping** (lines 94-107):
Currently wraps root in a `Div` with `Style(layout=Flex(...), span=Span(width=w, height=h))`.

Change to:
```python
Style(
    layout=waxy.Style(
        display=waxy.Display.Flex,  # explicit (taffy default, but be clear)
        flex_direction=waxy.FlexDirection.Column,
        justify_content=waxy.AlignContent.Start,
        align_items=waxy.AlignItems.Stretch,
        size_width=waxy.Length(w),
        size_height=waxy.Length(h),
    ),
)
```

**Mouse hit-testing** (lines 376-396):
Currently walks `layout_tree.walk_from_bottom()` and tests against `border_rect` from
`dims.padding_border_margin_rects()`.

Change to iterate `elements_and_layouts` (in reverse for bottom-up hit priority) and test
against `resolved.border`:

```python
for element, resolved in reversed(elements_and_layouts):
    if resolved.border.contains(mouse_position) or resolved.border.contains(m.absolute):
        if element.on_mouse:
            handle_control(element.on_mouse(event))
```

**Hooks.dims** (`hooks/impls.py:42`):
Currently `dims: LayoutBoxDimensions`. Change type to `ResolvedLayout`.
`use_rects()` (`hooks/hooks.py:78-96`) currently calls `dims.padding_border_margin_rects()`
and constructs `Rects(content=dims.content, padding=p, border=b, margin=m)`.

Change to read directly from `ResolvedLayout`:
```python
def use_rects() -> Rects:
    dims = current_hook_state.get().dims
    return Rects(
        content=dims.content,
        padding=dims.padding,
        border=dims.border,
        margin=dims.margin,
    )
```

The `Rects` dataclass (`hooks/hooks.py:71-75`) changes its field types from
counterweight's `Rect` to `waxy.Rect`.

**Delete:**
- `build_layout_tree_from_shadow()` function (line 470 in app.py)

### Step 7: Update exports and examples

**`counterweight/__init__.py`** (currently exports only `app`): No change needed.

**Examples that use style types directly** (need updating):

| Example | Imports to update |
|---------|-------------------|
| `end_to_end.py` | `Border`, `BorderKind`, `Flex`, `Padding` — uses `Style(border=Border(...), padding=Padding(...), layout=Flex(...))` |
| `mouse.py` | `Span` — uses `Style(span=Span(width=20, height=10))` |
| `borders.py` | `Border`, `BorderEdge`, `BorderKind` — uses `Style(border=Border(kind=..., edges=...))`. Replace with `waxy.Style` border widths + `border_kind`. |
| `border_healing.py` | `Border`, `BorderEdge` — uses `Style(border=Border(edges=...))`. Replace with `waxy.Style` border widths. |

Conversions:
```python
# end_to_end.py
# OLD: Style(border=Border(kind=border), padding=Padding(top=1, bottom=1, left=1, right=1))
# NEW:
Style(
    layout=waxy.Style(
        padding_top=waxy.Length(1), padding_bottom=waxy.Length(1),
        padding_left=waxy.Length(1), padding_right=waxy.Length(1),
        border_top=waxy.Length(1), border_bottom=waxy.Length(1),
        border_left=waxy.Length(1), border_right=waxy.Length(1),
    ),
    border_kind=border,
)

# mouse.py
# OLD: Style(span=Span(width=20, height=10))
# NEW:
size(20, 10)

# borders.py — this example lets user pick edges dynamically.
# With border_edges removed, express this as waxy.Style border widths:
# OLD: Style(border=Border(kind=border_kind, edges=border_edges))
# NEW (border_edges is now a set of side name strings like {"top", "left"}):
Style(
    layout=waxy.Style(
        border_top=waxy.Length(1 if "top" in active_sides else 0),
        border_bottom=waxy.Length(1 if "bottom" in active_sides else 0),
        border_left=waxy.Length(1 if "left" in active_sides else 0),
        border_right=waxy.Length(1 if "right" in active_sides else 0),
    ),
    border_kind=border_kind,
)
```

### Step 8: Delete dead code

| What | Where |
|------|-------|
| `LayoutBox` class | `layout.py:63` |
| `LayoutBoxDimensions` class | `layout.py:24` |
| `first_pass()` method | `layout.py:107` |
| `second_pass()` method | `layout.py:189` |
| `compute_layout()` method | `layout.py:94` |
| `build_layout_tree_from_shadow()` | `app.py:470` |
| `partition_int()` | `_utils.py:33` |
| `Edge` class | `geometry.py:103` |
| `Rect` class | `geometry.py:37` (replaced by `waxy.Rect`) |
| `Flex` class | `styles/styles.py:654` |
| `Span` class | `styles/styles.py:601` |
| `Margin` class | `styles/styles.py:581` |
| `Padding` class | `styles/styles.py:589` |
| `Content` class | `styles/styles.py:597` |
| `Typography` class | `styles/styles.py:606` |
| `Border` class | `styles/styles.py:574` |
| `Relative` class | `styles/styles.py:612` |
| `Absolute` class | `styles/styles.py:629` |
| `Fixed` class | `styles/styles.py:644` |
| `BorderEdge` enum | `styles/styles.py:567` |
| `fixed()` utility function | `styles/utilities.py:2226` |
| `docs/examples/fixed_positioning.py` | entire file |
| `Inset` class | `styles/styles.py:624` |

### Step 9: Update tests

**Tests that need updating:**

| Test file | What changes |
|-----------|-------------|
| `tests/styles/test_merging.py` | All test cases reference deleted classes (`Flex`, `Span`, `Border`, `Relative`, `Absolute`). Rewrite every parametrized case to use new `Style` + `waxy.Style` fields. |
| `tests/styles/test_utilities.py` | References `Flex`, `Relative`, `Absolute`, `Fixed`. Rewrite assertions. |
| `tests/elements/test_text.py` | References `Style` — probably fine if `Style` import stays. Check for `typography` references. |
| `tests/inputs/test_on_mouse.py` | Imports `Border`, `BorderKind`, `Span`, `Style`. Rewrite to use flattened fields. |
| `tests/inputs/test_on_key.py` | Imports `Span`, `Style`. Rewrite `Span(width=..., height=...)` to `waxy.Style(size_width=..., size_height=...)`. |
| `tests/test_app.py` | Full app integration tests. Layout results may shift due to correct CSS flexbox. Regenerate snapshots. |
| `tests/utils/test_partition_int.py` | Delete entirely (function removed). |

**New tests to add:**
- `tests/test_layout.py` — test `compute_layout()` with simple trees (single div, nested divs, text measurement, fixed positioning)
- `tests/styles/test_merging.py` — new cases for `waxy.Style` merge via `__or__`

---

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Already done (waxy >= 0.3.0) |
| `src/counterweight/styles/styles.py` | Delete 10 classes, restructure `Style`, update `__or__` / `mergeable_dump` |
| `codegen/generate_utilities.py` | Update generator to use waxy types and flattened Style fields; introspect waxy enums |
| `src/counterweight/styles/utilities.py` | Regenerated by running `codegen/generate_utilities.py`; update non-generated header/footer |
| `src/counterweight/styles/__init__.py` | Update exports (remove 11 deleted classes) |
| `src/counterweight/layout.py` | Rewrite: new `ResolvedLayout` + `compute_layout()` using waxy. Delete old engine. Keep `wrap_cells()`. |
| `src/counterweight/paint.py` | Adapt to `ResolvedLayout`, flattened style field names, simplify `paint_edge` |
| `src/counterweight/app.py` | Use new layout function, update mouse hit-testing, delete `build_layout_tree_from_shadow` |
| `src/counterweight/geometry.py` | Delete `Edge` and `Rect` classes (replaced by `waxy.Rect`) |
| `src/counterweight/_utils.py` | Delete `partition_int` |
| `src/counterweight/hooks/impls.py` | Change `Hooks.dims` type from `LayoutBoxDimensions` to `ResolvedLayout` |
| `src/counterweight/hooks/hooks.py` | Simplify `use_rects()` to read directly from `ResolvedLayout` |
| `src/counterweight/elements.py` | Update `Text.cells` to read `text_style` instead of `typography.style` |
| `examples/*.py` | Update to new style API |
| `tests/styles/test_merging.py` | Rewrite all test cases |
| `tests/styles/test_utilities.py` | Rewrite assertions |
| `tests/inputs/test_on_mouse.py` | Update style construction |
| `tests/inputs/test_on_key.py` | Update style construction |
| `tests/utils/test_partition_int.py` | Delete |
| `tests/test_app.py` | Update/regenerate snapshots |

## Execution Order

The implementation order matters because of dependencies:

1. **Step 1**: `styles/styles.py` — foundation; everything else depends on the new `Style`
2. **Step 2**: `codegen/generate_utilities.py` → regenerate `styles/utilities.py` + `styles/__init__.py` — needed by all downstream code
3. **Step 3**: `layout.py` — new layout engine (can be done in parallel with paint if interfaces are agreed)
4. **Step 4**: `paint.py` + `geometry.py` — adapt to `ResolvedLayout`
5. **Step 5**: `hooks/impls.py` + `hooks/hooks.py` — type change for dims
6. **Step 6**: `app.py` — wire everything together
7. **Step 7**: `elements.py` — update `Text.cells` property
8. **Step 8**: Examples — update all example files
9. **Step 9**: Tests — update and regenerate
10. **Step 10**: Delete dead code + `_utils.py` cleanup

Steps 3-5 can potentially be done in parallel since they have clear interfaces.

## Open Questions (Resolved)

1. **`waxy.TaffyTree.children(node_id)`**: **Yes** — `def children(self, parent: NodeId) -> list[NodeId]`
   exists (stub line 960). Use option 3: call `tree.children(node_id)` in `_extract_layout`
   and zip with `shadow.children`. No reverse mapping needed.

2. **Inset positioning for `Absolute`**: **Centering works via auto insets.** Inset fields accept
   `Length | Percent | Auto`. For centering:
   `waxy.Style(position=waxy.Position.Absolute, inset_left=waxy.Auto(), inset_right=waxy.Auto())`
   for horizontal, and similarly `inset_top=waxy.Auto(), inset_bottom=waxy.Auto()` for vertical.
   `align_self`/`justify_self` with `AlignItems.Center` is also available as an alternative.

3. **Root node display mode**: The `display` field defaults to `None`, which uses taffy's default
   (`Display.Flex`). Set `display=waxy.Display.Flex` explicitly on the root wrapper for clarity.

4. **Rounding**: `tree.layout(node)` returns rounded values when rounding is enabled.
   `tree.enable_rounding()` / `tree.disable_rounding()` control it. Default state is not
   specified in the stub, so **call `tree.enable_rounding()` explicitly** before
   `compute_layout()` to guarantee integer-friendly values for terminal rendering.

## Migration Risk & Mitigations

- **API breakage**: All user code using `Flex(...)`, `Span(...)`, `Margin(...)`,
  etc. breaks. Mitigated by: pre-1.0 status, utilities hide most of this.
- **Layout differences**: Taffy implements CSS flexbox correctly; some layouts
  may shift. Mitigate by running all examples visually and updating tests.
- **Performance**: Building a fresh taffy tree each render adds Python overhead,
  but taffy's Rust layout is much faster than the Python implementation.
- **Float→int rounding**: Use rounded layout and test for off-by-one.
- **`flex_shrink` default**: Taffy defaults `flex_shrink` to `1.0` (CSS spec), meaning
  items shrink to fit. The old engine had no shrink concept. This may cause layouts to
  behave differently when children exceed parent size. Add `shrink_0` utility for cases
  where shrinking is undesirable.

## Out of Scope (Future Work)

- Fixed positioning (reparent to root node with `position: Absolute`; see §6)
- Tree reuse / incremental layout across renders
- Percent-based sizing
- Expanded text wrapping modes (word wrap, etc.) — when added, the `_measure_text`
  callback should also handle `MinContent` (longest word width) and `MaxContent`
  (full unwrapped width) available space variants correctly
- Overflow/scrolling — taffy supports `Overflow.Scroll` which affects layout sizing;
  counterweight should eventually support scrollable containers, but this requires
  mouse wheel and keyboard scroll support first. The `overflow` style field on
  `waxy.Style` is available when ready.
