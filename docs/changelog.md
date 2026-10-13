# Changelog

## `0.1.0`

### Added

- [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  Added [scroll containers](layout/scrolling.md): a box whose overflow is `Scroll`,
  with the utilities `overflow_scroll`, `overflow_x_scroll` and `overflow_y_scroll`,
  shows the part of its content its offset scrolls into view.
  Counterweight holds each container's offset, and after every layout keeps the content in view where it was,
  as CSS's scroll anchoring does, and clamps the offset to how far the content reaches.
  The `overflow_anchor` style field, with `overflow_anchor_auto` and `overflow_anchor_none`, turns anchoring off,
  and the `stick_to_end_x` and `stick_to_end_y` style fields, with `stick_to_end` and `unstick` and their `_x` and `_y` forms,
  keep a container that's scrolled to its end there as its content grows, as a log or a chat transcript wants.
  The controls `ScrollTo` and `ScrollBy` scroll a container named by an `ElementHandle`,
  which an element takes as its `handle`, or by a receiver's `subtree`,
  and `ScrollIntoView` scrolls every container above an element until it's in view,
  as the web's `scrollIntoView` does.
  All three apply in order to the layout of the next render, so they scroll in the same frame as,
  and the content laid out by, any state change returned beside them.
  Moving focus scrolls the newly focused element into view.
  `counterweight.handlers` gains `scroll_on_wheel` and `scroll_on_keys`, which scroll for the wheel
  and for the arrow keys, PageUp, PageDown, Home and End,
  and pass the event on to the container outside once their own reaches an end,
  and `page_down` and `page_up`, which return the `ScrollBy` for a page of any fraction of the view.
  [`use_scroll`](hooks/use_scroll.md) returns how far the calling component's element,
  or the element with a given `ElementHandle`, is scrolled and how far it can be,
  and a `Receiver` carries the same as its `scroll`.

- [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  Added the overflow utilities `overflow_visible`, `overflow_hidden` and `overflow_clip`,
  with `overflow_x_*` and `overflow_y_*` forms that set one axis,
  and the `clip_to` style field, with `clip_to_padding`, `clip_to_border` and `clip_to_screen`,
  which lets a child such as a border title draw on its parent's border when its parent clips,
  or a popup such as a dropdown escape every clip above it.
  `Rects` gains `clip`, the region an element's ancestors let it draw in,
  and `visible`, the part of its border box inside that region.
  See [Clipping](layout/clipping.md), and the [autocomplete recipe](cookbook/autocomplete.md).

- [#330](https://github.com/JoshKarpel/counterweight/issues/330)
  Added [`markdown`](rich-text/markdown.md), which renders a Markdown document
  (GitHub Flavored Markdown, with its task lists, alerts, footnotes, bare URLs, and math, and YAML front matter)
  as a `Div` of elements, styled by a `MarkdownStyles` with a field for each kind of block and span.
  Links are hyperlinks, and fenced code blocks and front matter are highlighted.
  The [Markdown viewer](https://github.com/JoshKarpel/counterweight/blob/main/examples/markdown_viewer.py) example
  shows a directory's Markdown files beside a tree of them, and the
  [Markdown gallery](https://github.com/JoshKarpel/counterweight/blob/main/examples/markdown_gallery.py) example
  shows each kind of block and span beside its source.

- [#330](https://github.com/JoshKarpel/counterweight/issues/330)
  Added [syntax highlighting](rich-text/syntax-highlighting.md) with Pygments:
  `highlight` returns code as styled chunks, `code_style` its theme's background and text color,
  and `code_block` a `Text` of the highlighted code on that background.

- [#330](https://github.com/JoshKarpel/counterweight/issues/330)
  Added `link` to `CellStyle`, which makes any `Chunk` or `Text` a [hyperlink](rich-text/hyperlinks.md)
  that the terminal opens when it's clicked.

- [#411](https://github.com/JoshKarpel/counterweight/issues/411)
  Added the `SetTitle` control, which sets the title of the terminal window.
  The app saves the title it started with and restores it when it quits and while it's suspended,
  on terminals that support xterm's title stack,
  and the `RestoreTitle` control brings it back while the app runs.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added [`use_focus`](hooks/use_focus.md), which makes a component focusable, so that key presses go to it while it's focused.
  It takes `auto_focus`, to take focus on mount when nothing else has it;
  `handle`, a `FocusHandle` a parent creates to focus a child it renders;
  `is_focusable=False`, to disable it; and `in_focus_order=False`, to leave it out of Tab order.
  The controls `FocusNext`, `FocusPrevious`, `FocusOn(handle)` and `ClearFocus` move focus,
  and `FocusNext` and `FocusPrevious` take a `within` subtree to move only inside one element.
  `counterweight.handlers` gains `tab_focus`, `focus_receiver_on_press`, `focus_on_press` and `clear_focus`,
  which return them for Tab and for presses; nothing moves focus unless a handler does.
  A `Receiver` carries the element's `focus_handle`, whether it `is_focused`, and its `subtree`.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added `counterweight.handlers`, with `on_click(action)`, which calls `action` when a press on its element
  is released inside it, and `first` and `each`, which compose several handlers into the one an element takes.
  A handler can return a tuple of controls, applied in order and skipping any `None`,
  or `()` to stop an event with nothing more to do.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added `inset(n)`, `inset_x(n)` and `inset_y(n)`, which set all four, the left and right, or the top and bottom insets;
  `inset_sides`, `margin_sides` and `pad_sides`, which set each side separately in the order of CSS's four-value shorthands;
  and `auto` margins for every side and pair of sides, from `margin_auto` to `margin_right_auto`.
  `position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height`
  centers a box over its parent at its own size, as in CSS.

- [#400](https://github.com/JoshKarpel/counterweight/issues/400)
  Added [`use_clock`](hooks/use_clock.md), which gives a component the time
  (the wall-clock time, and how long since the app started and since the component mounted)
  while it stays pure: it re-runs when its next tick starts, ticks follow the wall clock,
  and components reading it in the same frame see the same time.
  `app` takes a `clock` to read the time from, such as a `frozen_clock` for tests and screenshots,
  and the `AdvanceClock` control moves it forward.
  The cookbook shows how to [animate a spinner](cookbook/spinners.md) with it.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Added `@component(memo=True)`, which skips re-running a component when its parent re-runs
  and passes it arguments equal to the previous render's,
  and `check_purity` on `app`, which runs every component again after each render
  and raises `ImpureComponent` when that builds something different,
  because a component depends on more than its arguments and hooks.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Added `use_memo`, which caches a value until its dependencies change,
  so a component can keep an expensive derived value, an unchanging part of its output,
  or a handler it passes to a `memo` component.
  With `check_purity` on, a cached value that a dependency missing from its list would change raises `StaleMemo`.

- Documented how to find where a frame's time goes, which components a frame re-runs,
  and how to skip the rest with `memo=True` and `use_memo`, with their failure modes,
  in [Performance](performance.md).

- Documented how Counterweight compares with Textual, Ink and Ratatui,
  and what it doesn't do, in [Ecosystem](ecosystem.md).

- Documented how components keep their state across renders,
  and how to use keys to move or reset that state.

- Documented that a component must call the same hooks in the same order on every render,
  and how to move a hook that is only sometimes needed into a child component.

- Documented what [`use_ref`](hooks/use_ref.md) is for,
  and why a component shouldn't read or write a ref while rendering.

- Documented how to make a component draggable and keep it inside its parent,
  in [Draggable Components](cookbook/draggable-components.md).

- Documented every style utility on the [utilities page](styles/utilities.md),
  grouped by family: what each constant sets, each function's signature,
  and the color palette.

- [#318](https://github.com/JoshKarpel/counterweight/pull/318)
  Added three text wrapping modes for `Text` elements: `text_wrap_stable` (greedy),
  `text_wrap_balance` (equalizes line lengths), and `text_wrap_pretty` (Knuth–Plass DP,
  minimizes ragged lines). The default remains `text_wrap_none` (no wrapping).
  Words longer than the available width are broken with a hyphen.
  A wrapping `Text`'s minimum size is its widest word, so wrapping `Text`s side by side
  in a row shrink to share it.

- [#315](https://github.com/JoshKarpel/counterweight/pull/315)
  Added `canvas(width, height, cells, default)` to `counterweight.utils` for rendering
  half-block pixel art in a terminal canvas using `▀` characters, as a tuple of chunks for a `Text`.

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

- [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  `Rects` is keyword-only, since it has more fields than are easy to keep in order.
  A scroll container's `padding` and `content` exclude the space its `scrollbar_width` reserves,
  as taffy lays its children out, where they included it.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  **Breaking:** a `Div`'s `children` is a tuple, and so is a `Text`'s `content` when it's chunks,
  so an element is a value that can be cached and shared without anything changing it afterwards.
  Pass `(a, b)` or `tuple(...)` where you passed a list.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  `Color.from_hex` accepts the CSS shorthand `#rgb` as well as `#rrggbb`,
  and raises `ValueError` for any other number of digits
  instead of dropping the extra digits of a color like `#rrggbbaa`.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  SVG screenshots draw text that is bold, dim, italic, underlined, or struck through,
  instead of drawing it plain.

- [#176](https://github.com/JoshKarpel/counterweight/issues/176)
  Each frame is written as one [synchronized update](https://github.com/contour-terminal/vt-extensions/blob/master/synchronized-output.md),
  so terminals that support it show the whole frame at once instead of tearing partway through drawing it,
  and redrawing the screen after a resize or a suspension no longer flashes it blank first.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** a key press goes to the focused element, or to the root component's element when nothing is focused,
  then bubbles through its ancestors until a handler returns something other than `None`.
  Previously every handler received every key press, whatever the others returned.
  A component that handles keys below the root calls `use_focus`, with `auto_focus=True` to have keys from the start,
  and puts its handler on the element it returns;
  one that should act on keys wherever focus is moves its handler to the root component's element.
  Tab has no built-in meaning: put `tab_focus` on the root for Tab navigation.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** a mouse event goes to one target, the element drawn on top at the pointer,
  then bubbles through its ancestors until a handler returns something other than `None`.
  A press runs from the first button going down to the last coming up,
  and is captured by the element whose handler stops its first `MouseDown`:
  its moves, and every button's presses and releases while it lasts, go to that element alone,
  wherever the pointer is, and reach no handler if nothing stopped the first `MouseDown`.
  Previously every element under the pointer's current or previous position received every mouse event,
  so a drag that outran a render lost its element.
  A handler that acts on a release or a drag returns `()` for the `MouseDown`,
  or uses `on_click`, and one that acts on any mouse event returns `()` to keep its ancestors from acting on it too.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  `z` follows CSS's stacking contexts.
  An element that sets `z`, `z(0)` included, paints with its descendants as one layer at its `z`,
  and its descendants' `z` orders them only among each other,
  while an element that sets no `z` leaves its descendants to be layered alongside it.
  Previously every element was sorted by `z` in one flat order,
  so an element with a higher `z` than its children painted over them,
  and an element with a negative `z` painted beneath every element, its own parent included;
  now children always paint over their parent, and a negative `z` paints beneath the rest of its stacking context
  but over the element that forms it.
  An app that sets `z` on nested elements may layer differently.
  `STYLE_DEFAULTS.z` is `None`, for an element that sets no `z`, rather than `0`.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  An element's margin is painted only where its style sets `margin_color`,
  and its `content_color` fills its border box rather than its margin box,
  so a margin leaves whatever lies beneath it visible, as on the web.
  Previously every margin painted black over what was beneath it,
  so an absolutely positioned box with large margins blanked out its parent.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** `Div` and `Text` take one `on_input` handler in place of `on_key` and `on_mouse`.
  It receives both key presses and mouse events, so one `match` case can handle `Down` and the scroll wheel alike,
  and a `Receiver` describing the element, whose `rects` and `relative` locate a mouse event inside it,
  and whose `is_target` tells the event's target from an ancestor it bubbled to.
  A handler that takes only the event, or annotates it as `KeyPressed` or `MouseEvent`, fails to type-check;
  annotate it as `InputEvent` and match on the event's class.
  `Rects` lives in `counterweight.geometry`, and `counterweight.hooks` still exports it.

- Cancelling the task running `app` raises `CancelledError` out of it once the terminal is restored,
  as asyncio expects, so `asyncio.timeout` and `wait_for` around an app can tell it was cancelled.
  Previously `app` returned as if the app had quit.
  Pressing ctrl+c still quits the app and `app` returns,
  so an app run with `asyncio.run` exits without a traceback.
  A second ctrl+c, before a stuck app has quit, goes to the interrupt handler `app` replaced,
  which for `asyncio.run` cancels the app and raises `KeyboardInterrupt`.

- [#271](https://github.com/JoshKarpel/counterweight/issues/271)
  `app` takes the root component already called, as `app(root())` rather than `app(root)`,
  so a root component can take arguments like any other: `app(root(Path(sys.argv[1])))`.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  An error raised while the app runs, in a component, a handler or an effect,
  propagates out of `app` as itself rather than wrapped in an `ExceptionGroup`,
  after the terminal is restored, so its traceback ends at the line that raised it
  and callers can catch it by its own type.
  Errors raised at the same moment from more than one effect are still grouped.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  A render calls only the components whose state changed and the components they return,
  instead of every component, and keeps the previous render's output for the rest.
  An effect with `deps=None` runs after every render of its own component,
  rather than after every render of the app.

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

- The `counterweight` CLI is built on [without-cli](https://www.without.help/without-cli/),
  so counterweight no longer depends on typer, click, rich or shellingham.
  `counterweight` with no command prints a short usage error instead of the full help,
  `counterweight --version` prints the version as `counterweight version` does,
  and shell completion (`--install-completion`) is gone.

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
  or configures structlog. While an app runs, its log records
  (`logging.getLogger(__name__).debug("...", extra={...})`) are written to the devlog off the render loop
  by [without-logging](https://www.without.help/without-logging/),
  by default, counterweight's and the app's own at every level (the app's being the top-level package
  of the module that defines its root component), and every other logger's from `INFO` up,
  so a library that logs at `DEBUG` on a hot path costs nothing unless an app asks for its records.
  `app`'s `log_levels` sets levels by logger name, as `logging.config` does, over those defaults.
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
  The painted cell `counterweight.paint.P` is renamed `Cell`, and its `char` is renamed `grapheme`.
  It is a frozen dataclass of a grapheme cluster and its resolved style, and no longer carries its element's `z`.
  `counterweight.elements.CellPaint`, a grapheme cluster and its unresolved `CellStyle`,
  is renamed `StyledGrapheme`, and its `char` is renamed `grapheme`.

### Fixed

- [#388](https://github.com/JoshKarpel/counterweight/issues/388)
  A box whose overflow is `Hidden`, `Clip` or `Scroll` clips its children to its padding box,
  on each axis that sets it, where they painted over its border and beyond it.
  The constraint utilities (`length`, `percentage`, `ratio` and `fill`) hide their box's overflow,
  so a border title in a constrained box needs `clip_to_border`.
  The mouse reaches an element only where it's painted:
  routing, `use_hovered` and `on_click` ignore the parts of an element its ancestors clip away.

- [#407](https://github.com/JoshKarpel/counterweight/issues/407)
  Terminal input is parsed incrementally, so typed and pasted text arrives intact:
  - Text beyond ASCII is decoded as UTF-8, one `KeyPressed` per grapheme cluster (`"é"`, `"日"`).
    Previously it was dropped, along with everything else read alongside it.
  - An escape sequence Counterweight doesn't recognize (such as Ctrl+digit in some terminals)
    is skipped. Previously it arrived as an Escape key press followed by its characters.
  - An escape sequence or UTF-8 character split between two reads is held over and completed by the next one,
    and a lone `ESC` is the Escape key once no more input follows for 50 milliseconds.
    Previously a split sequence turned into stray key presses, most often during a flood of mouse motion.
  - A carriage return is `Key.Enter`.

  `parsy` is no longer a dependency.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Scrolling the mouse wheel up is reported as `MouseScrolledUp` and down as `MouseScrolledDown`,
  as xterm defines them; previously the two were swapped.
  The mouse wheel scrolled with Shift, Alt or Control held is reported as a scroll,
  and the horizontal wheel as `MouseScrolledLeft` and `MouseScrolledRight`, new events.
  Previously all of these were reported as presses of buttons 1 to 3,
  so a sideways trackpad swipe clicked whatever was under the pointer.
  Buttons 8 to 11, such as back and forward, are reported by their own numbers
  rather than as buttons 1 to 4.
- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Home, Page Up and Page Down are reported, as the new `Key.Home`, `Key.PageUp` and `Key.PageDown`,
  and so is every key the `Key` enum names with Shift, Control, or both,
  such as `Key.ShiftHome`, `Key.ControlPageDown` and `Key.ControlF5`,
  with Shift and F1 to F12 reported as F13 to F24, as xterm does.
  Previously only the arrow keys were reported with modifiers.
  Control+Shift+Delete is reported as `Key.ControlShiftDelete` rather than `Key.ControlShiftInsert`.
  **Breaking:** `Key.ControlSpace` is `"ctrl+space"`, like every other key, rather than `"ctrl-space"`.
- [#392](https://github.com/JoshKarpel/counterweight/issues/392)
  Text is measured, wrapped and painted by grapheme cluster and its display width, as measured by
  [wcwidth](https://github.com/jquast/wcwidth), a new dependency,
  so CJK characters and emoji take two cells and no longer push the rest of their line out of place,
  combining marks and joined emoji (`👩‍💻`) stay whole,
  and zero-width characters such as zero-width spaces take no cells.
  `StyledGrapheme.width` is the number of cells a cluster takes.
  See [wide characters](elements/text.md#wide-characters).
- [#392](https://github.com/JoshKarpel/counterweight/issues/392)
  Control characters in text other than line breaks, such as tab and escape,
  are drawn as symbols (`␉`, `␛`) rather than written to the terminal, where they ran as commands.
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

- `app` stops reading keys from the terminal before it returns,
  so input typed afterward reaches whatever runs next.
  Previously its key-reading thread kept running and consumed that input.

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
