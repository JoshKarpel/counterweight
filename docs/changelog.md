# Changelog

## `0.1.0`

### Added

- Documented how Counterweight compares with Textual, Ink and Ratatui,
  and what it doesn't do, in [Ecosystem](ecosystem.md).

- Documented how components keep their state across renders,
  and how to use keys to move or reset that state.

- Documented that a component must call the same hooks in the same order on every render,
  and how to move a hook that is only sometimes needed into a child component.

- [#318](https://github.com/JoshKarpel/counterweight/pull/318)
  Added three text wrapping modes for `Text` elements: `text_wrap_stable` (greedy),
  `text_wrap_balance` (equalizes line lengths), and `text_wrap_pretty` (Knuth–Plass DP,
  minimizes ragged lines). The default remains `text_wrap_none` (no wrapping).
  Words longer than the available width are broken with a hyphen.
  A wrapping `Text`'s minimum size is its widest word, so wrapping `Text`s side by side
  in a row shrink to share it.

- [#315](https://github.com/JoshKarpel/counterweight/pull/315)
  Added `canvas(width, height, cells, default)` to `counterweight.utils` for rendering
  half-block pixel art in a terminal canvas using `▀` characters.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  Added `clamp(min_, val, max_)` to `counterweight.utils` for clamping numeric values to a range.


- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added `counterweight.styles.merge`, which merges any number of `Style`s left to right,
  as an alternative to chaining `|`: `merge(a, b, c)` is `a | b | c`.
  It skips `None` arguments wherever they appear.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added the sizing keyword utilities `min_content_width`, `max_content_width`,
  `fit_content_width` and `stretch_width`, and their `_height` counterparts,
  which size a box from its content or fill the space available after its margins.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added the constraint utilities `length(n)`, `percentage(p)`, `ratio(a, b)` and `fill(n)`,
  which split space along the parent's main axis the way ratatui's constraints of the same names do:
  a child takes its share whatever its content, in a `row` or a `col`.
  For grid, `fr(n)` is a track of `n` shares that content can't widen (`minmax(0, n fr)`),
  and `span(n)` places a child across `n` tracks.
  `grid_template_columns` and `grid_template_rows` accept a plain `int` as a track of that many cells,
  and `grid_row` and `grid_column` accept one as a grid line.
  `center_children` centers children on both axes.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added `Screenshot.to_stream`, which prints a screenshot as a text grid
  (with or without ANSI escape codes), useful for debugging layout and in tests.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added a Layout section to the documentation:
  a guide to choosing between flexbox and grid,
  and a gallery of layout effects, each shown as code beside its screenshot,
  with every screenshot also available as copyable text.
- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  New functional style utilities: `pad(n)`, `pad_x(n)`, `pad_y(n)`, `pad_top(n)`, etc.;
  `margin(n)`, `margin_x(n)`, `margin_y(n)`, `margin_top(n)`, etc.;
  `gap(n)`, `gap_width(n)`, `gap_height(n)`;
  `size(w, h)`, `grow(n)` (which sets only `flex_grow`);
  `inset_top(n)`, `inset_bottom(n)`, `inset_left(n)`, `inset_right(n)`;
  `full`, `full_width`, `full_height`, which fill the parent after the box's margins.
- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  New style utilities `position_absolute` and `position_relative` replace the old
  `absolute(x, y)`, `relative(x, y)`, and `fixed(x, y)` helpers.
  Offsets are now expressed with `inset_left(n)` / `inset_top(n)` (and friends) instead of `x`/`y` arguments.
- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  Color style utilities (e.g. `text("slate", 500)`, `border_bg("blue", 300)`,
  `content_color("green", 500)`, `margin_color("red", 600)`) now use functional helpers
  instead of per-shade constants, greatly reducing the size of the generated utilities module.
- [#123](https://github.com/JoshKarpel/counterweight/pull/123)
  Add styling for content area background color.

### Changed

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  The `*_center` and `*_end` alignment utilities
  (`justify_children_*`, `align_children_*`, `align_self_*`, `justify_items_*`, `justify_self_*`)
  use CSS's safe alignment: content too large for its container starts at the start edge
  instead of overflowing past it.
  Each has an `*_unsafe` counterpart, such as `justify_children_center_unsafe`,
  that centers or end-aligns overflowing content anyway.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** a `Screenshot` handler now receives a `counterweight.output.Frame`
  instead of an SVG `ElementTree`; call `frame.svg()` or `frame.text()` to encode it.
  `Screenshot.to_file` chooses the encoding from the path's suffix
  (`.svg` for SVG, `.txt` for text with ANSI escape codes),
  always indents SVGs, and no longer takes `indent`.
  Every `Screenshot` requested in the same render cycle now receives the same frame,
  where previously only the last one ran.

- The setter returned by `use_state` is the same object on every render of a component,
  so including it in an effect's `deps` no longer reruns the effect each render.

- Calling a `use_state` setter after its component has unmounted does nothing,
  instead of updating orphaned state and triggering a render that changes nothing.

- **Breaking:** A component that calls a different number of hooks than on its previous render
  raises `InconsistentHookExecution`.
  Skipping a trailing hook used to pass silently, and a skipped `use_effect` kept running.

- **Breaking:** Keyed sibling components that share a key raise `DuplicateKey`.

- **Breaking:** Component keys are strings only; `with_key` no longer accepts an `int`.
  Convert numeric ids with `str()`.

- [#318](https://github.com/JoshKarpel/counterweight/pull/318)
  **Breaking:** `Key.Space` now has the string value `" "` instead of `"space"`.
  Code that matched on the string value (e.g. `event.key == "space"`) must be updated;
  matching on the enum member (`Key.Space`) is unaffected.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** borders work as they do in Tailwind.
  A border side is drawn where its width in `Style.layout` is 1, and `border_kind` only chooses the characters.
  `border_kind` defaults to `BorderKind.Light`, so the new `border` utility alone draws a light border,
  and the `border_<kind>` utilities no longer reserve space or draw anything on their own:
  write `border | border_heavy` where you wrote `border_heavy`.
  `border_top`, `border_bottom`, `border_left` and `border_right` set one side, the new `border_x` and `border_y`
  set a pair, and each has a new `_0` form (`border_0`, `border_top_0`, ...) that clears its sides.
  A `border_kind` of `None` (`border_none`) removes the border along with the space reserved for it.
  A border width in `Style.layout` other than `Length(0)` or `Length(1)` raises `ValueError`.
  `border_all` and the edge combinations such as `border_top_left` are removed:
  use `border`, or compose sides as in `border_top | border_left`.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Every field of `Style` (except `layout`) and `CellStyle` starts out as the new
  `counterweight.styles.UNSET` sentinel rather than its default value,
  so reading a field of a style you built can return `UNSET`.
  The defaults live in `counterweight.styles.STYLE_DEFAULTS` and `counterweight.styles.CELL_STYLE_DEFAULTS`,
  and fill unset fields when an element is drawn.

- [#315](https://github.com/JoshKarpel/counterweight/pull/315)
  Core types (`Style`, `CellStyle`, `Div`, `Text`, `Chunk`, hook types) have been converted
  from Pydantic models to frozen `dataclass` instances, removing the runtime Pydantic dependency.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  The layout engine has been replaced with [waxy](https://github.com/JoshKarpel/waxy),
  a Python binding for the [taffy](https://github.com/DioxusLabs/taffy) flexbox/grid layout engine.
  This brings standard CSS flexbox semantics, improved correctness for complex layouts,
  and eliminates the hand-rolled layout engine.
- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  `use_rects` now returns `counterweight.geometry.Region` objects instead of the removed `counterweight.geometry.Rect`.
  A `Region`'s `right` and `bottom` are exclusive (the first column and row outside it),
  so `width` and `height` count cells, and its corner properties (e.g. `top_left`) are `Position`s.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** counterweight logs through the standard library's `logging`, and no longer depends on
  or configures structlog. While an app runs, every log record at every level, including an app's own
  (`logging.getLogger(__name__).debug("...", extra={...})`), is written to the devlog off the render loop
  by [without-logging](https://www.without.help/without-logging/).
  The devlog is a single JSON-lines file, which `counterweight devlog` renders for reading
  (`--json` prints the raw lines). Its messages no longer carry `elapsed_ns` timings:
  to see where a frame's time goes, profile the app with Python's sampling profiler
  (`python -m profiling.sampling run app.py`).
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Laying out a frame costs less. An app keeps one layout tree for its lifetime,
  so taffy reuses the layout of every element whose style, text and children are unchanged,
  and a `Text` is wrapped at most once per width it is measured at.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Painting a frame costs less. Elements paint straight into one screen-sized grid of cells,
  a row at a time, and an element's text and border are cached wherever it moves on the screen.
  Only the cells that changed since the last frame are written to the terminal,
  with one cursor move per run of changed cells and a style change only where the style changes.
  Building a `CellStyle` or cell equal to one built recently returns the cached instance.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Merging styles with `|` costs less: a `Style` computes its hash once, when it's built,
  and merges are cached with `functools.lru_cache`. counterweight no longer depends on cachetools.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** `Frame.paint` is a `counterweight.paint.Paint`, a screen-sized grid of cells,
  rather than a `dict` from `Position` to cell.
  Index it with a `Position` or an `(x, y)` pair, or read it a row at a time with `rows()`.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  The painted cell `counterweight.paint.P` is renamed `Cell`. It is a frozen dataclass of a character
  and its resolved style, and no longer carries its element's `z`.
  `counterweight.elements.CellPaint`, a character and its unresolved `CellStyle`, is renamed `StyledChar`.

### Fixed

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Merging styles with `|` now lets the right side override the left with a default value:
  `border_heavy | border_none` has no border kind, `text_justify_center | text_justify_left` justifies left,
  `z(5) | z(0)` has `z` 0, and `CellStyle(bold=True) | CellStyle(bold=False)` is not bold.
  Previously a field set to its default was treated as unset and ignored.
- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  An element with a `content_color` but no margin, border, padding or text now paints its background.
  Previously it painted nothing. An element with none of these and no `content_color` still paints nothing,
  so an undecorated container laid over other elements leaves them visible.

- A component replaced by a plain element at the same position is now unmounted:
  its effects are cancelled, and components nested under it start with fresh state.
  Previously the element inherited the component's hooks, so its effects
  (including `use_mouse` listeners) kept running.

- Effects that rerun or unmount in a render are cancelled concurrently,
  and all of them finish before any effect starts,
  so an effect's cleanup always finishes before its replacement or a sibling's setup begins.
  If several of those cleanups raise, all of their exceptions are reported together in one exception group.
  Previously a rerun effect's new task started before the old one was cancelled.

- Keyed sibling components are matched by key across renders rather than by position,
  so reordering, inserting, or removing keyed children keeps each one's state and effects.
  Unkeyed children still match the unkeyed child at the same index.

- [#125](https://github.com/JoshKarpel/counterweight/pull/125)
  Mouse wheel scroll events are now captured correctly
  (they were previously reported as mouse presses).
  The `check-input` CLI subcommand is also fixed
  (was broken by [#86](https://github.com/JoshKarpel/counterweight/pull/86)).

### Removed

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  The following style types have been removed; layout is now configured directly via
  `waxy.Style` on the `Style.layout` field or through the new utility helpers:
  `Border`, `BorderEdge`, `Margin`, `Padding`, `Content`, `Span`, `Typography`,
  `Relative`, `Absolute`, `Fixed`, `Flex`, `Inset`.
  The `Style` model is now flat: border, margin, padding, typography, and positioning
  properties are top-level fields rather than nested sub-models.
- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  `counterweight.geometry.Rect` and `counterweight.geometry.Edge` have been removed.
  Use `counterweight.geometry.Region` in place of `Rect`.
- [#165](https://github.com/JoshKarpel/counterweight/pull/165),
  [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Dropped support for Python `3.11` through `3.14`.
  Python `3.15` or later is now required.

## `0.0.9`

Released `2024-02-27`

### Fixed

- [#121](https://github.com/JoshKarpel/counterweight/pull/121)
  A change in effect reconciliation introduced in `0.0.8` caused a regression in the behavior of `use_effect`,
  where if the `setup` function `return`ed (i.e., stopped itself),
  Counterweight would crash when trying to cancel the effect.
  This now works again.

## `0.0.8`

Released `2024-02-17`

### Changed

- [#110](https://github.com/JoshKarpel/counterweight/pull/110)
  Calling a `use_state` setter with a `value` equal to the current value of the state
  no longer emits a `SetState` event, to avoid triggering unnecessary render cycles.
- [#111](https://github.com/JoshKarpel/counterweight/pull/111)
  Border healing is now more efficient, especially when there are many non-border characters in the UI.
- [#112](https://github.com/JoshKarpel/counterweight/pull/112)
  Major, backwards-incompatible changes to how Counterweight handles mouse interactions.
  The `on_mouse_down` and `on_mouse_up` event handlers have been removed;
  use the new combined `on_mouse` event handler instead, which receives all mouse events
  ([`MouseMoved`][counterweight.events.MouseMoved],
  [`MouseDown`][counterweight.events.MouseDown], and
  [`MouseUp`][counterweight.events.MouseUp]).
  The `on_hover` style attribute on elements has been removed;
  use the new
  [`use_mouse`](hooks/use_mouse.md),
  [`use_rects`](hooks/use_rects.md),
  and [`use_hovered`](hooks/use_hovered.md)
  hooks instead, and calculate the desired style in your component.
  The goal of these changes is to provide more flexibility and control over mouse interactions
  to application authors while minimizing the work that Counterweight needs to do while rendering,
  at the cost of more complex application code for simple cases like detecting hover state.

## `0.0.7`

Released `2024-02-02`

### Changed

- [#105](https://github.com/JoshKarpel/counterweight/pull/105)
  `Screenshot` and `Suspend` handlers can now be `async` functions.

## `0.0.6`

Released `2024-01-28`

### Added

- [#92](https://github.com/JoshKarpel/counterweight/pull/92)
  Added an `inset` attribute to `Absolute` that chooses which corner
  of the parent's context box to use as the origin for the absolute positioning.
- [#98](https://github.com/JoshKarpel/counterweight/pull/98)
  Added a `z` attribute to `Flex` that controls the stacking order of elements.

### Changed

- [#101](https://github.com/JoshKarpel/counterweight/pull/101)
  The `initial_value` of [`use_ref`][counterweight.hooks.use_ref] may now be a `Callable[[], T]` instead of just a `T`.

### Removed

- [#96](https://github.com/JoshKarpel/counterweight/pull/96)
  `Chunk`s can no longer be created with `CellPaint`s directly.

## `0.0.5`

Released `2024-01-06`

### Added

- [#86](https://github.com/JoshKarpel/counterweight/pull/86)
  Added a `Suspend` control which suspends the Counterweight application while a user-supplied callback function runs.
  Counterweight will stop controlling the terminal while the callback runs, and will resume when the callback returns.
  This can be used to run a subprocess that also wants control of the terminal (e.g., a text editor).
- [#88](https://github.com/JoshKarpel/counterweight/pull/88)
  [#90](https://github.com/JoshKarpel/counterweight/pull/90)
  Implemented `Absolute` and `Fixed`
  positioning, which allow for precise placement of elements outside the normal layout flow.

## `0.0.4`

Released `2023-12-31`

### Fixed

- [#83](https://github.com/JoshKarpel/counterweight/pull/83)
  Fixed virtual terminal escape code parsing for mouse tracking when the moues coordinates are large (>94 or so).
  Mouse tracking should now work for any terminal size.
  Various `Key` members that aren't currently parseable have been removed to avoid confusion.

## `0.0.3`

Released `2023-12-30`

### Changed

- [#71](https://github.com/JoshKarpel/counterweight/pull/71)
  Controls are now a union over different `@dataclass`es (instead of an `Enum`) to allow for more flexibility.
  The `Screenshot` control now takes a callback function which will be called with the SVG screenshot as an XML tree.
- [#81](https://github.com/JoshKarpel/counterweight/pull/81)
  The minimum Python version has been raised to `3.11.2` due to a [bug in CPython `3.11.1`](https://github.com/python/cpython/issues/100098)

## `0.0.2`

Released `2023-12-26`

### Added

- [#65](https://github.com/JoshKarpel/counterweight/pull/65)
  Added ability to take an SVG "screenshot" by returning `Control.Screenshot` from an event handler.
  The screenshot will be saved to the current working directory as `screenshot.svg`; more options will be added in the future.
- [#66](https://github.com/JoshKarpel/counterweight/pull/66)
  Added "border healing": when border elements for certain border types are adjacent to each other and appear as if they
  should "join up", but don't because they belong to different elements, they will now be joined up.

### Changed

- Various namespaces moved around to make more sense (especially in documentation)
  and separate concerns better as part of [#68](https://github.com/JoshKarpel/counterweight/pull/68).

## `0.0.1`

Released `2023-12-19`
