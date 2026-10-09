# Plan: Styling Foundations

This plan covers the counterweight side of making styles predictable to compose and layout
easier to reason about:
a cell-grid region type, taking up the waxy `0.6.0` release, one merge rule for every style
field, borders stored once, documented layout defaults, and reusing the layout tree across
frames.
It doesn't cover component memoization (`plans/component-memoization.md`) or paint performance,
except where reusing the layout tree touches them.

It depends on the waxy plan of the same name (`plans/styling-foundations.md` in the waxy
repository), which ships first as waxy `0.6.0`.

## Problems

- **Two merge rules in one `Style`.** The `waxy.Style` in `Style.layout` merges by
  "explicitly set wins". Counterweight's own fields go through `merge_style_fragments`
  (`styles/styles.py:20`), where the right side wins only if it differs from the field's
  default, so no field can be overridden back to its default:

  ```text
  text_justify_center | Style(text_justify="left")  -> text_justify "center"
  z(5) | z(0)                                        -> z 5
  border_light | border_none                         -> BorderKind.Light, border_top Length(1)
  ```

  `CellStyle` has the same problem: `CellStyle(bold=False)` can't turn bold off.
- **Borders stored twice.** `border_kind` (what gets drawn) lives on `Style`, while the border
  widths (the space reserved) live in `Style.layout`.
  `paint_border` draws an edge only where layout reserved space for it (`paint.py:186-189`).
  A border kind without widths draws nothing, and widths without a kind leave a blank gap.
  The `border_<kind>` utilities set both, but the edge utilities (`border_top`,
  `border_sides`, ...) set widths only.
- **`waxy.Rect` used as an inclusive cell box.** `ResolvedLayout` stores the index of the
  last cell in `right` and `bottom`, so an empty box is `right=-1` (`layout.py:27`) and
  widths need `+ 1` (`paint.py:142`). waxy `0.6.0` removes the geometry methods counterweight
  relies on.
- **`Style.layout` excluded from equality and hashing** (`styles/styles.py:547-549`),
  so styles with different layouts compare equal. The comment there says `waxy.Style` has
  no value equality; it has had it since waxy #38.
- **`STYLE_MERGE_CACHE` keyed on `(hash(self), hash(other))`** (`styles/styles.py:43`), so a
  hash collision silently returns the wrong merged style.
- **Undocumented CSS defaults.** Before the switch to waxy, `Flex.weight` defaulted to 1 and
  children grew to fill their parent. Taffy uses CSS defaults (`flex_grow=0`, `flex_shrink=1`,
  row direction, cross-axis stretch, border-box sizing), so children shrink to their content
  unless told otherwise.
- **Layout tree rebuilt every frame** (`layout.py:46`), which discards taffy's layout cache
  (#313).

## Steps

Each step leaves the test suite passing and is a separate PR.

### 1. Introduce `Region` for areas of the cell grid

**Status:** Done

This step runs against the current waxy, before the bump in step 2, so that the bump
doesn't also have to carry the geometry migration.

Add `Region` to `counterweight/geometry.py`: a frozen, slotted dataclass of integer
`left`, `top`, `right`, `bottom`, half-open (`right` and `bottom` are the first column and
row *outside* the region).

- `width` and `height` are `right - left` and `bottom - top`, so they count cells, and an
  empty region has width or height 0.
- `contains(position: Position) -> bool`.
- `positions() -> Iterator[Position]`, row-major.
- `top_edge()`, `bottom_edge()`, `left_edge()`, `right_edge()`, each `-> Iterator[Position]`,
  for border painting.
- `intersection(other: Region) -> Region | None`, which the scrolling branch uses for clipping
  (`paint.py:165` on `claude/plan-scrolling-support-ShDz7`).

Iteration yields `Position` directly, which removes the float `waxy.Point` →
`Position.from_point` conversion on the paint path (`from_point` showed up at about 1–1.5% of
CPU in the dashboard profiles).

Migrate:

- `ResolvedLayout` fields become `Region`. In `_extract_layout`, compute `right` as
  `floor(border_abs_x + layout.size.width)` with no `- 1`, and the same for `bottom`.
  The padding and content insets keep reading per-side thicknesses from `Layout.border` and
  `Layout.padding`, which stay `waxy.Rect`.
- `paint.py`: `fill_rect` (renamed `fill_region`), `paint_edge`, `paint_border` and
  `paint_text` take `Region`.
  Remove the `+ 1` at `paint.py:142`.
- Hit-testing in `app.py:405-409` and `use_hovered` (`hooks/hooks.py:157-160`) compare against
  a `Position` instead of building `waxy.Point`s.
- `Rects` (`hooks/hooks.py:70`), returned by `use_rects`, holds `Region`s. This changes the
  public API: `rects.content.top_left` becomes a `Position`, so `examples/mouse.py` drops its
  `Position.from_point(...)` calls. Changelog entry under `Changed`.
- Delete `Position.from_point` once nothing uses it.

Tests: unit tests for `Region` (empty regions, single cells, edge iteration, intersection
of disjoint, touching and overlapping regions); convert the expectations in
`tests/test_layout.py` from inclusive to half-open. That conversion is mechanical
(`right + 1`, `bottom + 1`), so break the `_extract_layout` arithmetic on purpose once and
confirm the converted tests fail.

### 2. Take up waxy `0.6.0`

- Raise the floor to `waxy>=0.6.0` and update `uv.lock`.
- Remove `compare=False, hash=False` and the comment from `Style.layout`, so layout takes part
  in equality and hashing.
- Key `STYLE_MERGE_CACHE` on `(self, other)` rather than their hashes. Step 3 rewrites
  merging, so this may be replaced there; it's here so the collision bug doesn't wait on
  step 3.
- With waxy's new `repr`, `Style.__repr__` shows the layout fields that were set, without
  any counterweight change.

`Style.__hash__` now hashes the `waxy.Style` too, and waxy recomputes that hash on every call.
`Text` and `Div` are hashed for the `paint_text` cache. Profile the canvas and dashboard
workloads before and after. If hashing shows up, cache the hash on `Style` the way `CellStyle`
already does (`styles/styles.py:243-255`).

### 3. One merge rule: explicitly set wins

Give counterweight's own fields the rule waxy uses.

- **Authoring types.** Every field of `Style` and `CellStyle` (except `layout`) defaults to
  `UNSET`, the only member of a single-member `Unset` enum, so mypy can narrow it. Fields are
  typed `T | Unset`. `|` takes the right side's value wherever it isn't `UNSET`, recursing into
  nested fragments (`border_style`, `text_style`). No field's default takes part in merging.
- **Resolved types.** Paint and output need concrete values. Add `ResolvedStyle` and
  `ResolvedCellStyle`, frozen dataclasses with concrete types and no defaults, each built by a
  `resolve` function that fills unset fields from one table of defaults.
  This follows the role split in parse-don't-validate: the type users write carries defaults,
  and the type the renderer reads proves every field is present.
- **Where resolution happens.** `paint_element` resolves an element's `Style` once, cached
  on the style, since styles are hashable. Text cells resolve
  `text_style | cell_style` (`paint.py:156`) into a `ResolvedCellStyle`, and `CellPaint.style`
  becomes `ResolvedCellStyle`, so `sgr_from_cell_style` (`output.py:65`) and paint diffing only
  see concrete values.

The cost is two types per style, plus a resolve step that has to stay cached to stay off the
hot path. Profile canvas and dashboard before and after, and give `ResolvedCellStyle` the same
`@flyweight` and cached hash `CellStyle` has today.

Behavior change for users: setting a field to its default value now overrides it
(`border_none`, `text_justify_left`, `z(0)`, `CellStyle(bold=False)`). Combinations that only
set non-default values behave as before. Changelog entry under `Fixed`.

Tests (parametrized over every field of `Style` and `CellStyle`): an explicit default
overrides a non-default value; an unset field keeps the left side's value; resolving an empty
style gives the documented defaults.

### 4. Store borders once

- Replace the border-width bookkeeping with `border_kind: BorderKind | None` and
  `border_sides: BorderSides`, where `BorderSides` is a fragment of four `bool | Unset`
  fields (`top`, `bottom`, `left`, `right`, all resolving to `True`). Because it merges per
  field, `Style(border_sides=BorderSides(top=False))` turns off only the top edge.
- When building the layout tree, derive the waxy border widths from those two fields:
  1 for each side that's on when `border_kind` isn't `None`, else 0.
  Apply them as `style.layout | waxy.Style(border_top=..., ...)` so the derived widths always
  win, caching the result per style.
- Raise `ValueError` if `style.layout.fields_set` contains any `border_*` field, so border
  widths can't be set through `layout` and drift from `border_kind` again.
- Utilities: `border_<kind>` sets only `border_kind`. The edge utilities (`border_top`,
  `border_top_left`, ..., `border_all`) and `border_sides(...)` set all four sides, meaning
  "exactly these sides", which matches the generated combinations. Regenerate with
  `just codegen` after editing `codegen/generate_utilities.py`.

`border_contract` and `border_collapse` don't change.

Tests: `border_light | border_none` reserves no space and draws nothing;
`border_light | border_top` reserves and draws only the top edge;
setting `border_top` through `layout` raises.

### 5. Document the layout defaults

Fold this into the positioning docs rework (#314): layout follows CSS flexbox defaults
(`flex_direction` row, `flex_grow` 0, `flex_shrink` 1, `align_items` stretch, border-box
sizing), so children take their content size unless given `grow(1)`, and `Text` doesn't wrap
unless `text_wrap` is set. Show the common terminal patterns (fill the screen, split into
columns, a sidebar of fixed width) as cookbook examples.

### 6. Decide on rounding

`_extract_layout` reads `unrounded_layout` and floors edges itself.
The comment there (`layout.py:124-130`) explains why, using fractional starts from
`justify_content: space_evenly`.
Taffy has rounding built in for exactly this problem: it rounds absolute edges, so sizes come
out as whole cells and siblings tile.

Experiment: enable rounding, read `tree.layout()`, and run `tests/test_layout.py` along with
examples that use `space_evenly` and fractional `grow`.
If the results match, switch to taffy's rounding and delete the custom floor arithmetic.
If they don't, add the differing case as a test that explains why counterweight snaps
cells itself, and keep the current code.

### 7. Reuse the layout tree across frames

**Measure first.** Split the "Calculated layout" devlog timing (`app.py:307-311`) into
building the tree, `compute_layout` (including text-measure callbacks), and reading results
back, and record canvas and dashboard numbers in
`plans/performance-analysis-2026-03-07.md`. That split decides whether waxy's bulk layout
readout (waxy plan, item 5b) is worth building.

**Then reuse the tree** (#313):

- The app loop owns one `TaffyTree` for the lifetime of the app, and each `ShadowNode` keeps
  its `NodeId`.
- After `update_shadow`, reconcile: create nodes for new shadow nodes, `remove` nodes for
  unmounted ones, and call `set_children` where a node's child ids changed.
- Call `set_style` on every node every frame. waxy `0.6.0` makes that a no-op for unchanged
  styles, so taffy keeps its cache for those nodes.
- Call `set_node_context` only when a `Text` element changed, since taffy always marks the
  node dirty on that call.

Tests: a frame with no changes leaves every node clean (`tree.dirty(node)` is false);
changing one `Text` dirties only that node and its ancestors; mounting and unmounting
components leaves no orphaned nodes (`total_node_count` matches the shadow tree).
Compare canvas and dashboard profiles before and after.
