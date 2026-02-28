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
    border_edges: frozenset[BorderEdge] | None = None       # was border.edges
    border_contract: int = 0                                # was border.contract

    # Typography (flattened from Typography)
    text_style: CellStyle = CellStyle()                     # was typography.style
    text_justify: Literal["left", "center", "right"] = "left"  # was typography.justify
    text_wrap: Literal["none"] = "none"                     # was typography.wrap; "paragraphs" dropped
```

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

Build a `ResolvedLayout` for each node with pre-computed absolute rects:

```python
@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: Rect   # absolute position + size of content box
    padding: Rect   # absolute rect including padding
    border: Rect    # absolute rect including border
    margin: Rect    # absolute rect including margin
```

Each rect computed from `waxy.Layout` fields:
- Content: `(abs_x + margin.left + border.left + padding.left, abs_y + margin.top + border.top + padding.top, content_box_width(), content_box_height())`
- Padding: content expanded by padding widths
- Border: padding expanded by border widths
- Margin: border expanded by margin widths (= full outer box at `(abs_x, abs_y, size.width, size.height)`)

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

### Step 1: Restructure `Style` in `styles/styles.py`

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
- `BorderEdge` (line 567) — enum `{Top, Bottom, Left, Right}`
- `StyleFragment` (line 46) — base class still needed for merge logic

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
| `style.border.edges` | `style.border_edges` |
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
| `gap_children=N` | `gap_width=waxy.Length(N), gap_height=waxy.Length(N)` | Same gap in both directions |
| `position=Relative(x, y)` | `position=waxy.Position.Relative, inset_left=waxy.Length(x), inset_top=waxy.Length(y)` | |
| `position=Absolute(x, y)` | `position=waxy.Position.Absolute, inset_left=waxy.Length(x), inset_top=waxy.Length(y)` | |
| `position=Fixed(x, y)` | **Dropped** — delete `Fixed` class, `fixed()` utility, and doc example | |

### Step 2: Update `codegen/generate_utilities.py` and regenerate `styles/utilities.py`

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
   ALIGN_MAP = {
       "Start": "start", "Center": "center", "End": "end", "Stretch": "stretch",
   }
   for member in waxy.AlignItems:
       name = ALIGN_MAP.get(member.name)
       if name:
           f"align_children_{name} = Style(layout=waxy.Style(align_items=waxy.AlignItems.{member.name}))"
           f"align_self_{name} = Style(layout=waxy.Style(align_self=waxy.AlignItems.{member.name}))"
   ```

   The `_MAP` dicts filter to only the members we want utilities for (waxy enums may have
   additional members like `FlexStart`/`FlexEnd`/`Baseline` that we don't need).

5. **Weight utilities**:

   ```python
   # OLD: weight_none = Style(layout=Flex(weight=None)); weight_N = Style(layout=Flex(weight=N))
   # NEW:
   f"weight_none = Style(layout=waxy.Style(flex_grow=0.0))"
   for n in range(1, 9):
       f"weight_{n} = Style(layout=waxy.Style(flex_grow={float(n)}, flex_basis=waxy.Length(0)))"
   ```

6. **Border kind utilities** — introspect `BorderKind` enum (unchanged source, new output):

   ```python
   # OLD: border_light = Style(border=Border(kind=BorderKind.Light))
   # NEW: set both layout widths AND visual fields
   ALL_EDGES = "frozenset({BorderEdge.Top, BorderEdge.Bottom, BorderEdge.Left, BorderEdge.Right})"
   f"border_none = Style(border_kind=None)"
   for b in BorderKind:
       f"""border_{b.name.lower()} = Style(
       layout=waxy.Style(
           border_top=waxy.Length(1), border_bottom=waxy.Length(1),
           border_left=waxy.Length(1), border_right=waxy.Length(1),
       ),
       border_kind=BorderKind.{b.name},
       border_edges={ALL_EDGES},
   )"""
   ```

7. **Border edge selection utilities** — introspect `BorderEdge` (unchanged source, new output):

   ```python
   # OLD: border_top = Style(border=Border(edges=frozenset({BorderEdge.Top})))
   # NEW: set the specific waxy border widths for selected edges
   for edges in flatten(combinations(BorderEdge, r) for r in range(1, 4)):
       edge_set = ", ".join(f"BorderEdge.{e.name}" for e in edges)
       border_widths = ", ".join(
           f"border_{e.name.lower()}=waxy.Length(1)" for e in edges
       )
       f"border_{'_'.join(e.name.lower() for e in edges)} = Style("
       f"    layout=waxy.Style({border_widths}),"
       f"    border_edges=frozenset({{{edge_set}}}),"
       f")"
   ```

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
   # NEW:
   for n in N:
       f"gap_children_{n} = Style(layout=waxy.Style(gap_width=waxy.Length({n}), gap_height=waxy.Length({n})))"
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
```

**Why these helpers are needed:**
- `width()`/`height()`/`size()` replace `Span(width=N, height=N)` which was the primary
  way to set explicit dimensions. Used in `app.py` (screen root), `examples/mouse.py`,
  and tests. Without these, users would write
  `Style(layout=waxy.Style(size_width=waxy.Length(20), size_height=waxy.Length(10)))`.
- `relative()`/`absolute()` take arbitrary x/y coordinates — can't be pre-generated.
- `z()` takes an arbitrary z-index value.

**Not adding helpers for** (can use `waxy.Style(...)` directly for these rare cases):
- `flex_grow()`/`flex_shrink()`/`flex_basis()` — the `weight_N` utilities cover 95% of
  flex usage; power users can set `layout=waxy.Style(flex_grow=2.5)` directly.
- `min_width()`/`max_width()`/`min_height()`/`max_height()` — out of scope for now
  (listed in future work).
- `aspect_ratio()` — niche, use `waxy.Style(aspect_ratio=1.5)` directly.
- `overflow()` — out of scope.

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
from counterweight.styles import BorderEdge, BorderKind, CellStyle, Color, Style
```

**Workflow:** After updating `codegen/generate_utilities.py`, run it to regenerate
`utilities.py`. The generator is idempotent — it replaces the block between
`# Start generated` / `# Stop generated` markers.

### Step 3: Update `styles/__init__.py`

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
    "BorderEdge", "BorderKind", "CellStyle", "Color", "Style",
]
```

### Step 4: Rewrite `layout.py`

**Delete entirely:**
- `LayoutBox` class (line 63) and all methods (`walk_from_top`, `walk_from_bottom`,
  `walk_levels`, `compute_layout`, `first_pass`, `second_pass`)
- `LayoutBoxDimensions` class (line 24)
- `build_layout_tree_from_shadow()` (in `app.py:470`, but it's layout-related)

**Keep:**
- `wrap_cells()` function (line 436) — still needed for text measurement.
  Update signature to accept `width: int | None` (None = no constraint).
  Currently takes `width: int` and only implements `wrap="none"`.

**Add new types and functions:**

```python
import waxy
from counterweight.geometry import Rect
from counterweight.shadow import ShadowNode
from counterweight.elements import AnyElement, Text

@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: Rect
    padding: Rect
    border: Rect
    margin: Rect


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

    # Phase 2: Compute layout
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

    node_map[node_id] = shadow
    return node_id


def _measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: Text,
) -> waxy.Size:
    """Measure callback for text leaf nodes."""
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
    """Walk tree top-down, accumulating absolute positions."""
    layout = tree.layout(node_id)  # returns rounded Layout
    shadow = node_map[node_id]

    # Accumulate absolute position
    node_abs_x = abs_x + layout.location.x
    node_abs_y = abs_y + layout.location.y

    # Build rects from waxy.Layout
    # margin rect = outermost (location is already inside parent's content area,
    # but waxy's location IS the top-left of the margin box)
    margin_rect = Rect(
        x=int(node_abs_x),
        y=int(node_abs_y),
        width=int(layout.size.width),
        height=int(layout.size.height),
    )
    border_rect = Rect(
        x=int(node_abs_x + layout.margin.left),
        y=int(node_abs_y + layout.margin.top),
        width=int(layout.size.width - layout.margin.left - layout.margin.right),
        height=int(layout.size.height - layout.margin.top - layout.margin.bottom),
    )
    padding_rect = Rect(
        x=int(border_rect.x + layout.border.left),
        y=int(border_rect.y + layout.border.top),
        width=int(border_rect.width - layout.border.left - layout.border.right),
        height=int(border_rect.height - layout.border.top - layout.border.bottom),
    )
    content_rect = Rect(
        x=int(padding_rect.x + layout.padding.left),
        y=int(padding_rect.y + layout.padding.top),
        width=int(layout.content_box_width()),
        height=int(layout.content_box_height()),
    )

    resolved = ResolvedLayout(
        content=content_rect,
        padding=padding_rect,
        border=border_rect,
        margin=margin_rect,
    )
    results.append((shadow.element, resolved))

    # Store dims for use_rects() hook
    shadow.hooks.dims = resolved  # type change: was LayoutBoxDimensions, now ResolvedLayout

    # Recurse into children
    for child_shadow in shadow.children:
        child_node_id = ...  # need to maintain shadow→node_id mapping
        _extract_layout(tree, child_node_id, node_map, node_abs_x, node_abs_y, results)
```

**Note on shadow→node_id mapping:** `_build_node` stores `node_id → ShadowNode` in `node_map`.
For `_extract_layout` we also need `ShadowNode → node_id`. Options:
1. Return the node_id from `_build_node` and store it on the ShadowNode temporarily.
2. Build a reverse mapping.
3. Use `tree.children(node_id)` to get child node IDs and iterate them alongside `shadow.children`.

Option 3 is cleanest: in `_extract_layout`, call `tree.children(node_id)` (if waxy supports it)
or zip `shadow.children` (filtered for non-fixed) with the children order from tree construction.

**Verify:** Does `waxy.TaffyTree` expose a `children(node_id)` method? Check the `.pyi` stub.
If not, maintain a `dict[ShadowNode, waxy.NodeId]` alongside `node_map`.

### Step 5: Adapt `paint.py`

**`paint_layout`** (line 54):
Currently takes `LayoutBox` and walks the tree. Change to accept
`list[tuple[AnyElement, ResolvedLayout]]`:

```python
def paint_layout(
    elements: list[tuple[AnyElement, ResolvedLayout]],
) -> tuple[Paint, BorderHealingHints]:
    parts: list[tuple[Paint, BorderHealingHints, int]] = [
        paint_element(element, resolved) for element, resolved in elements
    ]
    # Sort by z-index, merge paints
    parts.sort(key=lambda p: p[2])
    paint: Paint = {}
    bhh: BorderHealingHints = {}
    for p, b, _ in parts:
        paint |= p
        bhh |= b
    return paint, bhh
```

**`paint_element`** (line 72):
Currently: `paint_element(element: AnyElement, dims: LayoutBoxDimensions) -> tuple[Paint, BorderHealingHints, int]`

Change to: `paint_element(element: AnyElement, resolved: ResolvedLayout) -> tuple[Paint, BorderHealingHints, int]`

Replace:
- `dims.padding_border_margin_rects()` → `resolved.padding`, `resolved.border`, `resolved.margin`
- `dims.content` → `resolved.content`
- `element.style.margin` → need `element.style.margin_color` + compute margin edge from resolved rects
- `element.style.padding` → need `element.style.padding_color` + compute padding edge from resolved rects
- `element.style.border` → `element.style.border_kind is not None`
- `element.style.content.color` → `element.style.content_color`
- `element.style.layout.z` → `element.style.z`

**`paint_edge`** (line 160):
Currently: `paint_edge(element, mp: Margin | Padding, edge: Edge, rect: Rect) -> Paint`

Simplify to: `paint_edge(outer: Rect, inner: Rect, color: Color, z: int) -> Paint`

Instead of using `Edge` thicknesses, compute the band between `outer` and `inner` rects directly:
- Top strip: `y ∈ [outer.top, inner.top)`, `x ∈ outer.x_range()`
- Bottom strip: `y ∈ (inner.bottom, outer.bottom]`, `x ∈ outer.x_range()`
- Left strip: `y ∈ [inner.top, inner.bottom]`, `x ∈ [outer.left, inner.left)`
- Right strip: `y ∈ [inner.top, inner.bottom]`, `x ∈ (inner.right, outer.right]`

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

Change to: `paint_border(style: Style, rect: Rect) -> tuple[Paint, BorderHealingHints]`

Replace:
- `border.style` → `style.border_style`
- `border.kind` → `style.border_kind`
- `border.edges` → `style.border_edges`
- `border.contract` → `style.border_contract`
- `element.style.layout.z` → `style.z`

**`paint_text`** (line 128):
Currently: `paint_text(text: Text, rect: Rect) -> Paint`

Replace:
- `text.style.typography.style` → `text.style.text_style`
- `text.style.typography.wrap` → `text.style.text_wrap`
- `text.style.typography.justify` → `text.style.text_justify`
- `text.style.layout.z` → `text.style.z`

**Delete from `geometry.py`:**
- `Edge` class (line 103) — no longer needed. Only consumers were `paint_edge` (now uses rect pairs)
  and `LayoutBoxDimensions.expand_by` (replaced by `ResolvedLayout`).

**Keep in `geometry.py`:**
- `Position` (line 12) — heavily used in painting
- `Rect` (line 37) — used for resolved layout rects. `expand_by(edge)` method can stay or be removed
  (it's only used in `LayoutBoxDimensions.padding_border_margin_rects()` which is deleted).

### Step 6: Update `app.py`

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
    if mouse_position in resolved.border or m.absolute in resolved.border:
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

The `Rects` dataclass (`hooks/hooks.py:71-75`) stays unchanged — it already has the
right shape (`content`, `padding`, `border`, `margin` all as `Rect`).

**Delete:**
- `build_layout_tree_from_shadow()` function (line 470 in app.py)

### Step 7: Update exports and examples

**`counterweight/__init__.py`** (currently exports only `app`): No change needed.

**Examples that use style types directly** (need updating):

| Example | Imports to update |
|---------|-------------------|
| `end_to_end.py` | `Border`, `BorderKind`, `Flex`, `Padding` — uses `Style(border=Border(...), padding=Padding(...), layout=Flex(...))` |
| `mouse.py` | `Span` — uses `Style(span=Span(width=20, height=10))` |
| `borders.py` | `Border`, `BorderEdge`, `BorderKind` — uses `Style(border=Border(kind=..., edges=...))` |
| `border_healing.py` | `Border`, `BorderEdge` — uses `Style(border=Border(edges=...))` |

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
    border_edges=frozenset({BorderEdge.Top, BorderEdge.Bottom, BorderEdge.Left, BorderEdge.Right}),
)

# mouse.py
# OLD: Style(span=Span(width=20, height=10))
# NEW:
size(20, 10)

# borders.py
# OLD: Style(border=Border(kind=border_kind, edges=border_edges))
# NEW:
Style(
    layout=waxy.Style(
        border_top=waxy.Length(1 if BorderEdge.Top in border_edges else 0),
        border_bottom=waxy.Length(1 if BorderEdge.Bottom in border_edges else 0),
        border_left=waxy.Length(1 if BorderEdge.Left in border_edges else 0),
        border_right=waxy.Length(1 if BorderEdge.Right in border_edges else 0),
    ),
    border_kind=border_kind,
    border_edges=border_edges,
)
```

Consider adding a helper function for the border boilerplate:
```python
def make_border_style(kind: BorderKind, edges: frozenset[BorderEdge]) -> Style:
    return Style(
        layout=waxy.Style(
            border_top=waxy.Length(1 if BorderEdge.Top in edges else 0),
            border_bottom=waxy.Length(1 if BorderEdge.Bottom in edges else 0),
            border_left=waxy.Length(1 if BorderEdge.Left in edges else 0),
            border_right=waxy.Length(1 if BorderEdge.Right in edges else 0),
        ),
        border_kind=kind,
        border_edges=edges,
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
| `src/counterweight/geometry.py` | Delete `Edge` class |
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

## Open Questions

1. **`waxy.TaffyTree.children(node_id)`**: Does waxy expose a method to get children of a node?
   This determines how `_extract_layout` traverses. Check the `.pyi` stub. If not available,
   maintain a `dict[ShadowNode, NodeId]` reverse mapping.

2. **Inset positioning for `Absolute`**: The old `Absolute` had `inset: Inset(vertical, horizontal)`
   with values like `"center"`. Taffy's `Absolute` uses `inset_*` values. How to replicate
   centering? Likely via `inset_left=Auto, inset_right=Auto` for horizontal centering, or
   via `align_self`/`justify_self` on the absolute child.

3. **Root node display mode**: Should the root wrapper `Div` use `display=waxy.Display.Flex`
   explicitly? `waxy.Style()` defaults should be checked — taffy defaults to `Display.Flex`
   for `Style()` but verify.

4. **Rounding**: `tree.layout(node)` returns rounded values (vs `tree.unrounded_layout(node)`).
   Verify that rounding is enabled by default and produces correct integer dimensions for
   terminal rendering. Watch for off-by-one issues at boundaries.

## Migration Risk & Mitigations

- **API breakage**: All user code using `Flex(...)`, `Span(...)`, `Margin(...)`,
  etc. breaks. Mitigated by: pre-1.0 status, utilities hide most of this.
- **Layout differences**: Taffy implements CSS flexbox correctly; some layouts
  may shift. Mitigate by running all examples visually and updating tests.
- **Performance**: Building a fresh taffy tree each render adds Python overhead,
  but taffy's Rust layout is much faster than the Python implementation.
- **Float→int rounding**: Use rounded layout and test for off-by-one.

## Out of Scope (Future Work)

- Fixed positioning (reparent to root node with `position: Absolute`; see §6)
- Tree reuse / incremental layout across renders
- Exposing CSS Grid layout to counterweight users
- Flex wrap support
- `min_size` / `max_size` support
- Overflow/scrolling
- Percent-based sizing
