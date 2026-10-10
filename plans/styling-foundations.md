# Plan: Styling Foundations

This plan covers the counterweight side of making styles predictable to compose and layout
easier to reason about and cheaper per frame:
a cell-grid region type, a gallery of layout examples, taking up the waxy `0.7.0` release,
one merge rule for every style field, borders stored once, utilities for the new sizing
keywords, ratatui-style constraint utilities, a guide to choosing between flexbox and grid,
reading layouts back in one call, memoizing text measurement, reusing the layout tree
across frames, and a last pass that makes the gallery read as one document.
It doesn't cover component memoization (`plans/component-memoization.md`) or paint performance,
except where layout work touches them.
It also doesn't cover exposing the grid features taffy 0.10 through 0.14 added
(grid template areas, `repeat()`) or the `CONTENT` flex basis as utilities;
nothing in counterweight or its examples needs them yet.

It builds on the waxy plan of the same name (`plans/styling-foundations.md` in the waxy
repository), released as waxy `0.6.0` ([waxy#49](https://github.com/JoshKarpel/waxy/pull/49)),
and on waxy `0.7.0` ([waxy#50](https://github.com/JoshKarpel/waxy/pull/50)),
which leaves hidden nodes out of `absolute_layouts`.

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
- **Docs teach a wrong default.** `docs/cookbook/layout-problems.md` says taffy doesn't
  stretch children on the cross axis, and tells users to add `align_children_stretch` to every
  container. Taffy does stretch by default: two `Style()` children of a 40-wide column both
  come out 40 wide. The advice has spread into `examples/`, where the utility does nothing.
- **Sizes follow content.** Ratatui splits an area along one axis by a list of constraints
  (`Length`, `Percentage`, `Ratio`, `Fill`, `Min`, `Max`), and a child's size never depends
  on what it draws. Flexbox sizes children from their content, and CSS's automatic minimum
  size keeps a flex item from shrinking below its min-content width, even when it has a
  `flex_basis`. In a 40-wide row, two `grow(1)` panes with 30 cells of unwrapped text come out
  30 and 30, and a pane with `flex_basis=Length(10), flex_shrink=0` and 50 cells of content
  comes out 50.
  Grid has the same floor: `1fr` columns overflow the same way, and `minmax(0, 1fr)` is needed.
  The cookbook's fix is `grow(1) | min_width(0)`, which works only in a `row`; a `col` needs
  `min_height(0)`, so the same component sized two ways needs two styles.
- **Sizing keywords out of reach.** waxy `0.6.0` lets `size_width` and `size_height` take
  `MIN_CONTENT`, `MAX_CONTENT`, `FIT_CONTENT`, `FitContent(limit)` and `STRETCH`, but the size
  utilities (`width`, `height`, `size`, `full_width`, `full_height`, `full`) only build
  `Length` and `Percent`, so sizing a box to its content means writing a raw `waxy.Style`.
- **Layout read back one node at a time.** `_extract_layout` (`layout.py:100`) recurses in
  Python, calling `unrounded_layout` and `children` on every node and snapping edges with its
  own floor arithmetic.
- **Text measured many times per frame.** Taffy calls the measure callback about 19 times per
  text leaf per layout, with about 13 distinct inputs, though `_measure_text` depends on only
  the text and one effective width.
- **Layout tree rebuilt every frame** (`layout.py:46`), which discards taffy's layout cache
  (#313).

## Steps

Each step leaves the test suite passing and is a separate PR.

### 1. Introduce `Region` for areas of the cell grid

**Status:** Done

This step runs against the current waxy, before the bump in step 3, so that the bump
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

### 2. Write a layout gallery

**Status:** Done

Document layout by the effect a user wants, with every technique that achieves it, each shown
as code beside its screenshot. The tooling exists: each file in `docs/examples/` is a headless
app whose `Screenshot` autopilot writes an SVG to `docs/assets/`, pages include the code
between `--8<--` markers, and the `generate-screenshots` pre-commit hook regenerates every
screenshot on every commit. What's missing is the examples.

This step comes before the waxy bump because the committed screenshots are also a visual
regression suite. Step 3 takes taffy from 0.9 to 0.14 and step 9 changes rounding, and both
can move computed layouts; with the gallery in place, every layout they move shows up as a
changed SVG in that PR. From here on, every step that adds or changes a layout utility updates
the gallery in the same PR: an unchanged screenshot shows that a rewrite (such as
`grow(1) | min_width(0)` to `fill(1)`) changed no layout, and a changed one shows the effect.

**Structure.** A "Layout" nav section, one page per kind of effect, absorbing
`styles/layout.md` and the positioning rework (#314). Each entry names the effect, shows each
technique as code and a screenshot, and says in one sentence what to notice. Where a technique
has a well-known failure, show the failure too, as a screenshot: an overflowing row teaches
more than a paragraph about automatic minimum sizes. Label boxes in-frame with the styles
that produced them, as `relative_positioning.py` does, so a screenshot reads on its own.

Pages and the effects each covers:

- **How layout sizes things:** layout follows CSS flexbox defaults (`flex_direction` row,
  `flex_grow` 0, `flex_shrink` 1, `align_items` stretch, border-box sizing), so children take
  their content size on the main axis and stretch on the cross axis; the automatic minimum
  size; why the root needs `full`; `Text` doesn't wrap unless `text_wrap` is set.
- **Splitting space:** equal shares, a fixed sidebar beside a filling pane, ratios, nested
  splits, each with flexbox and with grid tracks; the overflow when content is wider than a
  share; percentages plus `gap`.
- **Sizing one box:** fixed, fit to content, fill the parent, clamped with `min_*` and
  `max_*`, `aspect_ratio` (and why cells not being square matters there).
- **Alignment and distribution:** all six `justify_children_*` side by side, the four
  `align_children_*`, `align_self_*`, and centering a box three ways (flexbox, grid,
  absolute insets).
- **Spacing and borders:** `gap` against `margin` against `pad`; `border_collapse`;
  `border_contract`; borders on some sides only.
- **Layering:** relative and absolute positioning, insets, `z`, a dialog centered over the
  app, a badge pinned to a corner.
- **Grids and wrapping:** dashboard tiles, cells spanning tracks, auto flow, and `flex_wrap`
  as the flexbox alternative.
- **Text in layout:** wrapping inside a pane, justification needing a width wider than the
  text, long unwrapped text in a narrow pane.
- **App shells:** whole-screen compositions built from the pages above: header, body and
  footer; sidebar, main pane and status bar; three panes; a dialog over the app.

Fix what the gallery would otherwise repeat:

- Delete the cookbook's "children don't fill their container's width" entry, and rewrite the
  text-wrapping entry, which blames the same missing stretch. Fold the rest of
  `cookbook/layout-problems.md` into the gallery pages, as failures shown beside their fixes.
- Remove `align_children_stretch` where it restates the default (`examples/text_wrap.py`,
  `examples/suspend.py`, `examples/wordle.py`, `docs/examples/text_wrap.py`,
  `docs/styles/text-wrapping.md`). The regenerated screenshots must not change.

Tooling:

- Each example ends in about fifteen lines of `__main__` boilerplate that the gallery would
  copy dozens of times. Move it into a helper module in `docs/examples/` that takes the root
  component, the asset name and the dimensions. The examples run as scripts, so a sibling
  module imports without packaging.
- Size each screenshot to its effect rather than using 80×30 everywhere, so the images stay
  readable inline.
- The hook regenerates every screenshot on every commit. Time it before and after the gallery
  lands, and if it's slow, decide then whether to run it only when `src/` or
  `docs/examples/` changes.

### 3. Take up waxy `0.7.0`

- Raise the floor to `waxy>=0.7.0` and update `uv.lock`.
- Remove `compare=False, hash=False` and the comment from `Style.layout`, so layout takes part
  in equality and hashing.
  `waxy.Style` equality also compares which fields were explicitly set,
  so two counterweight `Style`s compare equal only if they also merge identically,
  which is what a cache keyed on styles needs.
- Key `STYLE_MERGE_CACHE` on `(self, other)` rather than their hashes. Step 4 rewrites
  merging, so this may be replaced there; it's here so the collision bug doesn't wait on
  step 4.
- With waxy's new `repr`, `Style.__repr__` shows the layout fields that were set, without
  any counterweight change.

The suite and mypy pass unchanged against the waxy `0.6.0` build
(`0.7.0` only changes `absolute_layouts`, which counterweight doesn't call until step 9),
so nothing in counterweight depends on the removed `Rect` and `Line` methods
or misspells a `waxy.Style` keyword (which now raises `TypeError`;
the utilities are module constants, so importing them constructs every one).
The bump also takes taffy from 0.9 to 0.14, which fixes layout bugs and can move computed
layouts. Regenerate the gallery screenshots from step 2 and review every SVG that changed,
and run the examples in `examples/` against the previous release before merging.

`Style.__hash__` now hashes the `waxy.Style` too. waxy caches that hash after the first call,
but counterweight's `Style` is a dataclass whose hash is recomputed over all its fields on
every call, and `Text` and `Div` are hashed for the `paint_text` cache.
Profile the canvas and dashboard workloads before and after. If hashing shows up, cache the
hash on `Style` the way `CellStyle` already does (`styles/styles.py:243-255`).

### 4. One merge rule: explicitly set wins

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

### 5. Store borders once

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
- Utilities: `border_<kind>` sets only `border_kind`, so a kind on its own draws all four
  sides. Two families then choose sides:
  - `border_off_<side>` (`border_off_top`, `border_off_bottom`, `border_off_left`,
    `border_off_right`) sets one side to `False` and leaves the others unset, so offs
    compose in any order: `border_light | border_off_left | border_off_right` draws top and
    bottom rules.
  - `border_only_<sides>` replaces the generated edge utilities (`border_top`,
    `border_top_left`, ...): each sets all four sides, meaning "exactly these sides".
    `only` says at the call site that the other sides go away, where `border_top` reads as
    "add the top side", which is the misreading that `border_light | border_top` drawing all
    four sides shows today. Onlys don't compose (`border_only_top | border_only_left` leaves
    just the left side), so keep generating every combination.
    Drop `border_all`, which only restates the default.
  - `border_sides(...)` stays as the function form of `border_only_<sides>`.

  Regenerate with `just codegen` after editing `codegen/generate_utilities.py`.
  Changelog entry under `Changed` for the renames and the removal of `border_all`.

`border_contract` and `border_collapse` don't change.

Tests: `border_light | border_none` reserves no space and draws nothing;
`border_light | border_only_top` reserves and draws only the top edge;
`border_light | border_off_left | border_off_right` and
`border_light | border_off_right | border_off_left` both draw only top and bottom;
`border_only_top | border_only_left` draws only the left edge;
setting `border_top` through `layout` raises.

Gallery: rewrite the "Borders on some sides" section of "Spacing and borders" around
`border_off_<side>` and `border_only_<sides>`, and drop its `border_light | border_top`
screenshot, which shows a pitfall this step removes. The `border_contract` example
(`layout_spacing.py:contract`) and `test_border_contract.py` build their sides with
`border_sides(frozenset({...}))`; move both to the new utilities, and check that every text
snapshot outside that section comes out unchanged.

### 6. Expose the sizing keywords

This comes after steps 4 and 5 so the new utilities are written once, under the new merge
rule, rather than migrated.

Add the keywords for both axes, hand-written beside `full_width` and `full_height`:

- `min_content_width`, `max_content_width`, `fit_content_width`, `stretch_width`, and the same
  four for height.
  The `_content_` names keep them apart from `min_width` and `max_width`, which already set
  `min_size_width` and `max_size_width`.
- Leave out `FitContent(limit)` until something needs it: it has to be a function, and its
  name would collide with the `fit_content_*` constants.
- `min_size_*` and `max_size_*` still take only `Length | Percent | Auto`, so `min_width`,
  `max_width` and their height counterparts don't change.

`full_width` is `Percent(1.0)`, which doesn't account for margins, while `STRETCH` fills the
space left after them.
Check whether `full_width | margin_x(1)` overflows its parent in a column layout (where shrink
doesn't apply to width). If it does, decide whether `full_width`, `full_height` and `full`
should switch to `STRETCH`; that would be a changelog entry under `Changed`.

Changelog entry under `Added`.

Tests: each utility sets only its own field (`layout.fields_set`); for a wrapping `Text`
of `"hello world"` in a 40-cell column, the four width keywords give widths of 5, 11, 11
and 40.

### 7. Add ratatui-style constraint utilities

Give users ratatui's way of splitting space, as composite utilities set on each child.
`flex_basis`, `flex_grow` and `flex_shrink` act along the parent's main axis, whichever axis
that is, so one utility works in both a `row` and a `col`, the way a ratatui constraint
applies along its `Layout`'s direction:

| ratatui         | utility            | `flex_basis`       | `flex_grow` | `flex_shrink` |
| --------------- | ------------------ | ------------------ | ----------- | ------------- |
| `Length(n)`     | `length(n)`        | `Length(n)`        | 0           | 0             |
| `Percentage(p)` | `percentage(p)`    | `Percent(p / 100)` | 0           | 0             |
| `Ratio(a, b)`   | `ratio(a, b)`      | `Percent(a / b)`   | 0           | 0             |
| `Fill(n)`       | `fill(n: int = 1)` | `Length(0)`        | `n`         | 1             |

Each also sets `overflow_x` and `overflow_y` to `Overflow.Hidden`, which makes the item a
scroll container, so its automatic minimum size is 0 and its content can't push it wider.
Probed against waxy `0.4.0`, a 40-wide row of `length(10)`, `fill(1)`, `fill(2)` children
with 50 cells of content each comes out 10, 10 and 20; the same three children in a 10-tall
column come out 2, 4 and 4.

Zeroing `min_size_width` and `min_size_height` gives the same split, but it takes the fields
users set for ratatui's `Min(n)`: `min_width(15) | fill(1)` would drop the minimum, while
`fill(1) | min_width(15)` would keep it. With `overflow`, both orders keep it.
The cost is that `Hidden` promises clipping. Paint doesn't clip today, so overflowing
content draws past the box as it does now; clipping arrives with the scrolling work, and
these utilities are where it starts to matter. `Overflow.Clip` doesn't help: taffy
doesn't treat it as a scroll container, so the automatic minimum stays.

`Min(n)` and `Max(n)` don't get utilities, because they constrain one axis and a child doesn't
know its parent's direction. Write `fill(1) | min_width(n)` or `max_height(n)` instead.

The composites are ordinary `Style`s, so they layer over the flexbox and grid primitives
rather than replacing them. Because explicitly set fields win when merging, a user can override one
field of a composite and keep the rest (`fill(1) | shrink(0)`, `length(20) | grow(1)`), and
anything ratatui can't express (wrapping, alignment, absolute positioning, content sizing,
two-dimensional grids) stays in the primitives.
That layering needs each primitive to set exactly one field.
`grow(n)` sets `flex_basis=Length(0)` beside `flex_grow`, so it's `fill(n)` without the
overflow. Make it set only `flex_grow`, like `shrink(n)`. Examples move from
`grow(1) | min_width(0)` (and bare `grow(1)`) to `fill(1)`. Changelog entry under `Changed`.

Add `fr(n)` for grid, the version where the parent holds the constraint list: it returns the
track value `Minmax(Length(0), Fraction(n))`, so `grid_template_columns(Length(10), fr(1),
fr(2))` splits space the way `length(10)`, `fill(1)` and `fill(2)` do in a row.
Bare `Fraction(n)` is `minmax(auto, n fr)`, which carries the same automatic-minimum floor:
in a 40-wide grid, columns `Length(10), Fraction(1), Fraction(1)` with content 5, 30 and 3
wide come out 10, 30 and 3, and the last column starts at 40, outside the grid.
Tracks of `Length(10)`, `Percent(0.25)` and `minmax(0, 1fr)` with 50 cells of content each
come out 10, 10 and 20.

Make the rest of a grid as short to write as `fr`:

- `grid_template_columns` and `grid_template_rows` accept a plain `int` as a track and convert it
  to `Length`, so a template reads `grid_template_columns(10, fr(1), fr(2))`, the way `width(10)`
  takes cells. waxy rejects a bare `int` track (`TypeError`), so every track is wrapped today.
  Don't add a `length()` track helper instead: `length(n)` is the flexbox `Style` above, and a
  track-valued name beside it would type-check in a template and fail at runtime.
- `grid_row` and `grid_column` accept a plain `int` as a grid line, and a new `span(n)` returns
  `GridSpan(n)`, so a placement reads `grid_row(1, span(3))` instead of
  `grid_row(waxy.GridLine(1), waxy.GridSpan(3))`.
- `Percent` tracks stay spelled out: a bare float is ambiguous between a fraction and a
  percentage, and percentage tracks are rare.

Also add `center_children` (`align_children_center | justify_children_center`), a pair the
examples and docs spell out eight times.

Changelog entry under `Added`.

Tests: the row and column splits above, with content larger than the container;
`min_width(15) | fill(1)` and `fill(1) | min_width(15)` give the same widths;
`percentage(25)` and `ratio(1, 4)` give the same width; each utility sets only its own
fields (`layout.fields_set`); `fill(1) | shrink(0)` keeps `fill`'s basis, grow and overflow
and changes only `flex_shrink`; a grid of `Length(10), fr(1), fr(2)` tracks gives the same
widths as the flexbox row; an `int` track gives the same widths as the `Length` it stands for;
`grid_row(1, span(3))` places a child the same as `grid_row(GridLine(1), GridSpan(3))`.

Gallery: rewrite the "Splitting space" page around these utilities. Each split shown with
`fill` and `length` should render the same as its `fr` grid version.
Then go back over the gallery and replace the raw waxy values the step 2 examples spell out
for lack of these utilities (`grep -rn "waxy\." docs/examples docs/layout`):

- `waxy.Length`, `waxy.Fraction` and `waxy.Minmax` tracks and `waxy.GridLine` and
  `waxy.GridSpan` placements in `layout_splitting.py` and `layout_grids.py` become ints,
  `fr` and `span`.
- `layout_grids.py` defines its own `fr = waxy.Fraction(1)`, which would shadow the new
  utility from `import *`; delete it.
- The "Content wider than its share" section of "Splitting space" explains
  `Minmax(Length(0), Fraction(1))` by hand; rewrite it around `fr` versus bare `Fraction`.
- The "Grids and wrapping" page introduces `fr = waxy.Fraction(1)` and the
  `waxy.GridSpan(n)` placement; update both to the utilities.
- The "Percentages and gaps" example in `layout_splitting.py` builds `half` from a raw
  `waxy.Style(flex_basis=waxy.Percent(0.5))`. `percentage(50)` replaces it, but also sets
  `flex_shrink` to 0, so the top row, which shows the default shrinking, becomes
  `percentage(50) | shrink(1)`, and the bottom row needs no `shrink(0)`.
- Once nothing in the examples needs `waxy`, drop `import waxy` (and the sentence about it)
  from the shared imports on the Layout index page.

The text snapshots should come out unchanged, which confirms the rewrite moved no layout.

### 8. Explain how to choose a layout model

The gallery shows _how_ to get each effect; this step adds the page that says _which_
technique to reach for, and how counterweight's model relates to ratatui's. It opens the
Layout section and links into the gallery pages for each case.

**Frame the choice as two independent questions.** "Grid is top-down, flexbox is bottom-up"
is close, but it mixes them:

1. _Where do the constraints live?_ On the parent, as a list (ratatui's `Layout`, grid's
   track templates), or on each child (flexbox's basis, grow and shrink).
2. _Can content push back?_ Never in ratatui: it doesn't measure widgets, it hands each one
   a rectangle to draw into. Flexbox and grid both let content raise sizes by default
   (content-sized items, `auto` and bare `Fraction` tracks), and both can turn that off
   (`fill` and `length`, or `Length`, `Percent` and `fr` tracks).

Ratatui is "parent holds the list, content never pushes back". Grid with `fr` tracks has the
same structure; flexbox with `fill` and `length` gives the same sizing with each child
holding its own constraint, the habit Tailwind teaches.
What counterweight adds over ratatui is the other half of question 2: a box can fit its
text, a wrapped paragraph can take exactly the rows it needs, and a list can grow with its
items, without the app measuring anything itself.

**Choosing between flexbox and grid.** Cover what each is good at and what it costs:

- **Grid** when the container owns the arrangement: a fixed set of slots known up front
  (app shells, dashboards), or columns that must line up across rows.
  It costs locality: a child's size lives on its parent, away from the component, and
  children fill tracks in order, so an extra child wraps into a new implicit row. In a
  10-tall grid with two columns and no row template, a third child starts a second row, and
  the two rows split the height 5 and 5.
- **Flexbox** when each child owns its size: a variable number of children (lists, toolbars,
  tags), content-sized items, wrapping, or a component that keeps its size wherever it's
  placed (a sidebar that's always `length(24)`).
  It costs alignment across rows: two rows' columns line up only if each child repeats the
  same size.

Build the same app shell three ways (flexbox with `fill` and `length`, grid with `fr`, and
flexbox sized by content) and show the screenshots together: the first two match, and the
third shows what content sizing does to the same tree.

**Where intuitions from ratatui break.** The page is about adjusting a mental model, not
translating code, so cover the places where thinking in ratatui terms predicts the wrong
layout:

- _Conflicts._ Ratatui resolves an over-constrained split by priority (`Min`, `Max`,
  `Length`, `Percentage`, `Ratio`, `Fill`, in that order). Flexbox starts from the basis,
  distributes free space by grow and shrink, then clamps to the min and max sizes, so
  `length(30)` twice in a 40-wide row overflows by 20.
  Show the same over-constrained split in both. Probe ratatui for its side (including
  whether it ever returns an area outside the parent) rather than describing it from its
  docs.
- _Percentages and gaps._ Two `percentage(50)` children in a row with `gap(1)` overflow by
  one cell, because CSS percentages don't subtract gaps; `fill(1)` gives equal shares.
- _Leftover space._ With nothing set to fill, ratatui's `Flex::Legacy` gives the excess to
  the last constraint of lowest priority, while flexbox leaves it empty at the end.
- _Alignment comes for free._ Ratatui's `Flex` modes appear in counterweight as the
  `justify_children_*` utilities of the same names, and stretch on the cross axis is the
  default rather than something to ask for.

The ratatui names come from ratatui `0.30.2`; check them against the current release when
writing the page.

### 9. Decide on rounding, and read layouts in one call

`_extract_layout` reads `unrounded_layout`, sums each node's position in Python, and floors
edges itself.
The comment there (`layout.py:124-129`) explains why, using fractional starts from
`justify_content: space_evenly`.
Taffy has rounding built in for exactly this problem, enabled by default on a `TaffyTree`:
it rounds absolute edges, so sizes come out as whole cells and siblings tile.

waxy's `TaffyTree.absolute_layouts(root)` returns every node in pre-order
with its absolute position and its `Layout`, honoring the tree's rounding setting.
It leaves out `display: Nil` nodes and their subtrees, matching what `_extract_layout` skips.
Don't sum the locations from `tree.layout()` instead:
taffy 0.14 rounds `location` relative to the parent but `size` against the absolute offset
([taffy#834](https://github.com/DioxusLabs/taffy/issues/834)),
so summed rounded locations can leave one-cell gaps or overlaps between siblings.
`absolute_layouts` rounds the summed unrounded position once, which matches the rounded sizes.

Experiment: leave rounding on, take each border box's edges from `absolute_layouts`
(position, and position plus size, both whole numbers with no floor),
and run `tests/test_layout.py` along with examples that use `space_evenly` and fractional
`grow`. `tree.format_tree(root)` dumps the computed tree as a string,
which shows where the two approaches differ, and the gallery screenshots show where any
difference reaches the screen.

- **If the results match,** switch to taffy's rounding and delete the custom floor
  arithmetic and its comment.
- **If they don't,** add the differing case as a test that explains why counterweight snaps
  cells itself, call `tree.disable_rounding()`, and keep flooring, but over the positions from
  `absolute_layouts`. Those are summed in `f32` (taffy's own precision) where the current code
  sums in Python floats, and the two differ by about `1e-7`
  (3.1000001 against 3.1000002 on a `space_evenly` row),
  which can flip a floor at an exact integer boundary such as the 12.667 + 7.333 case in the
  comment. Pin that boundary with a test before switching.

Either way:

- Reset `hooks.dims` to `INITIAL_RESOLVED_LAYOUT` for shadow nodes missing from the result.
  Today the early return for hidden nodes (`layout.py:118`) comes before `shadow.hooks.dims`
  is set, so a component that becomes hidden keeps the regions from the last frame it was
  visible, and `use_rects` and `use_hovered` go on reading them.
- Bind `layout.margin`, `layout.border` and `layout.padding` to locals before reading their
  sides, since each property access builds a new `Rect`.

Tests: the existing `tests/test_layout.py` expectations; a hidden subtree produces no
`ResolvedLayout`; a component hidden after a visible frame reports empty regions from
`use_rects`. Profile canvas and dashboard before and after.

### 10. Make per-frame layout cheaper

**Measure first.** Split the "Calculated layout" devlog timing (`app.py:307-311`) into
building the tree, `compute_layout` (including text-measure callbacks), and reading results
back, and record canvas and dashboard numbers in
`plans/performance-analysis-2026-03-07.md`.
That tells us how much of each frame the two changes below can recover.

**Memoize text measurement.**
waxy `0.6.0` already answers exact repeats of `(node, known_size, available_size)` within one
`compute_layout` call without calling back into Python, but taffy still asks each leaf about 13
distinct questions per layout, and most differ only in ways `_measure_text` ignores.
It depends only on the `Text` and one effective width
(`known.width`, else a definite available width, else none).
Split the wrapping work into a function of those two, returning the widest line and the line
count, behind a bounded `functools.lru_cache`, and apply `known.width` and `known.height`
outside it.
`Text` is an immutable, hashable value, so the cache needs no invalidation and is shared
across frames.
Return `waxy.Size(width, height)` positionally: pyo3 matches keyword arguments by name at
runtime, so the keyword form costs more on every call.

**Then reuse the tree** (#313):

- The app loop owns one `TaffyTree` for the lifetime of the app, and each `ShadowNode` keeps
  its `NodeId`.
- After `update_shadow`, reconcile: create nodes for new shadow nodes, `remove` nodes for
  unmounted ones, and call `set_children` where a node's child ids changed.
  Taffy's `remove` detaches a node's children rather than removing them, so remove every
  unmounted shadow node, not just the root of the unmounted subtree.
- Call `set_style` on every node every frame. waxy `0.6.0` makes that a no-op when the style's
  values are unchanged, so taffy keeps its cache for those nodes.
- Call `set_node_context` only when a `Text` element changed, since taffy always marks the
  node dirty on that call.

Tests: a frame with no changes leaves every node clean (`tree.dirty(node)` is false);
changing one `Text` dirties only that node and its ancestors; mounting and unmounting
components leaves no orphaned nodes (`total_node_count` matches the shadow tree);
a `Text` measured at an effective width it has already been measured at isn't wrapped again.
Compare canvas and dashboard profiles after each change.

### 11. Make one cohesive pass over the gallery

Steps 3 to 10 each update the gallery for their own change, a section at a time.
This step reads the whole Layout section start to finish, the way a new user would,
and makes it read as one document.

- **Use the current utilities everywhere.** Every example uses the shortest utility that now
  exists (`fill`, `length`, `fr`, `span`, `center_children`, the sizing keywords,
  `border_off_<side>` and `border_only_<sides>`), and no example spells out a raw `waxy` value
  that a utility covers. `grep -rn "waxy\." docs/examples docs/layout` should find only what
  the utilities deliberately leave out.
- **Revisit the workarounds.** The step 2 examples route around these behaviors rather than
  showing them. Check each against the current code; where it's fixed, simplify the example,
  and where it isn't, decide whether the gallery should show it as a failure:
  - A wrapping `Text` with its own border or padding is measured at its border-box width
    (taffy passes `_measure_text` a `known.width` that includes them), so it can lose its last
    line. The examples wrap text only in `Text`s without their own border or padding.
  - A wrapping `Text`'s minimum size is its unwrapped width, because `_measure_text` measures
    a min-content query as if the width were unlimited. "Text in layout" shows the
    `min_width(0)` fix.
  - Auto margins on an absolutely positioned box resolve against an area one cell too wide
    and tall, and the box's blank fill paints over its parent's border. The examples center
    with alignment instead of `margin: auto`.
  - `content_color` has no visible effect on a `Text`, whose text paints over it with the
    `text_style` background. The examples color `Text`s with `text_bg`.
- **Make the pages agree.** One name per concept across pages, cross-links between pages that
  discuss the same failure, and an order that builds from "How layout sizes things" up to
  "App shells", with step 8's page opening the section.
- **Tighten the screenshots.** Size each one to its effect, and label boxes consistently.

Tests: none new. Every changed text snapshot is reviewed in the diff, and an unchanged one is
expected wherever only the code changed.
