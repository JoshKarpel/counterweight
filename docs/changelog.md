# Changelog

## Next

### Added

- [#393](https://github.com/JoshKarpel/counterweight/issues/393)
  Added inline apps: `app(viewport=Inline())` draws in a region below the prompt, as tall as the root's content,
  rather than on the alternate screen, and leaves its last frame in the terminal when it stops
  (see [Inline Apps](inline.md)).
  `app`'s `viewport` is `FullScreen()` by default, whose `mouse=False` leaves the mouse to the terminal.
  `Inline(mouse=True)` tracks the mouse over the region, asking the terminal where the region is.

- [#393](https://github.com/JoshKarpel/counterweight/issues/393)
  Added `Print`, a control that renders a component or an element once and prints it to `app`'s `stdout` or `stderr`:
  above an inline app's region when the stream is the app's terminal, when a full-screen app hands the screen back,
  and to the stream as it is otherwise, as plain text if it isn't a terminal.
  While an app that isn't headless runs, `sys.stdout` and `sys.stderr` print each line written to them the same way,
  unless `app` is given `capture_output=False`.

- [#393](https://github.com/JoshKarpel/counterweight/issues/393)
  `Screenshot(include_scrollback=True)` takes everything an inline app's terminal holds,
  what it printed included, which is how a test reads it headless.
  `Emulator.history` returns the rows above an emulator's screen as it holds them now, rewrapped by resizes.

### Changed

- [#393](https://github.com/JoshKarpel/counterweight/issues/393)
  `Quit` renders once more before the app stops, without starting effects,
  so the last frame shows what the last handlers set.

## `0.1.1`

Released `2026-10-22`

Counterweight `0.1.1` fixes what the first apps to move onto `0.1.0` ran into:
empty frames in recordings, an autopilot that could stall on an app that never goes quiet,
and text that ignored its own `content_color`.
It also exports the names those apps had to import from private modules,
and adds `text_overflow` and handlers for copies.

### Added

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  Added `text_overflow`, with the `text_overflow_clip` and `text_overflow_ellipsis` utilities,
  which ends a line too wide for its `Text`'s content box with `…` in the box's last cell,
  as CSS's `text-overflow: ellipsis` does
  (see [Ending a line with an ellipsis](styles/text-wrapping.md#ending-a-line-with-an-ellipsis)).
  It changes only what's painted, never an element's size.

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  Added a `handler` to `CopyToClipboard` and a `clipboard_handler` to `app`,
  which take a copy's text in place of the terminal's clipboard, headless or not,
  so a test can check what an app copies (see [Copying to the clipboard](input-handling/controls.md#copying-to-the-clipboard)).

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  `Subtree()` makes a subtree that names nothing mounted, as a fresh `FocusHandle` does,
  so a test can build a `Receiver` to call a handler with, without reaching into the hooks.

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  Exported names that apps were importing from private modules, and the ones beside them:
  `counterweight.text`, a new module of `graphemes`, `grapheme_width` and `visible`,
  for an app that cuts or pads text itself to match how counterweight measures it;
  `ramp`, `Ramp`, `field_indices` and `Indices` from `counterweight.gradients`, to read a gradient's colors;
  `ResolvedCellStyle`, `resolve_cell_style`, `is_solid_cell_style`, `as_solid`, `with_colors`, `is_solid_color`,
  `rgb_of` and `palette` from `counterweight.styles`;
  `styled_grapheme`, `SCREENSHOT_FOREGROUND` and `SCREENSHOT_BACKGROUND` from `counterweight.paint`,
  the last two the colors an SVG screenshot draws the terminal's defaults in, for an asciicast `Theme` to match;
  `outcome_text` from `counterweight.commands`;
  and `SETTLE_LIMIT` from `counterweight.autopilot`.

### Fixed

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  A `Screenshot` handler that sets state no longer renders the app twice:
  the render that follows the handler shows the new state, and nothing renders again for it.

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  A render that changes no cell writes nothing to the terminal, so a recording has no empty frames,
  such as the ones a clock-driven component's ticks made once its animation stopped changing anything.

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  The autopilot holds a step back for an app that hasn't settled for at most `SETTLE_LIMIT` (50) passes
  of the render loop, then takes it anyway and logs a warning, so an app that never goes quiet,
  such as one showing a program that prints without pause, no longer stalls it.
  A `WaitFor` is checked on every pass, settled or not, so it times out on time.

- [#448](https://github.com/JoshKarpel/counterweight/pull/448)
  A `Text`'s characters are drawn on its own `content_color` where its `text_style` sets no background,
  as a `Canvas`'s painter's cells already were, so a box filled with a color shows it under its own text
  (see [Text in a filled box](styles/index.md#text-in-a-filled-box)).
  They still don't take the color of a box they lie in.

## `0.1.0`

Released `2026-10-21`

Counterweight `0.1.0` rebuilds most of the framework, and adds a great deal on top of it.
Layout is [taffy](https://github.com/DioxusLabs/taffy)'s flexbox and grid, through [waxy](https://github.com/JoshKarpel/waxy).
A render re-runs only the components whose state changed.
Input goes to the focused element and bubbles, as in the DOM, and boxes clip and scroll.
New on top of that are headless components and the widgets built on them, Markdown and syntax highlighting,
the `Canvas` element and embedded terminals, animation, gradients, and recordings,
and the [examples](examples.md) ship with the library, runnable from the `counterweight` CLI.

Most apps written for `0.0.9` need changes: every change that breaks one is marked **Breaking:** below.
Counterweight requires Python `3.15`.

### Added

#### Components and hooks

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Added `@component(memo=True)`, which skips re-running a component when its parent re-runs
  and passes it arguments equal to the previous render's,
  and `check_purity` on `app`, which runs every component again after each render
  and raises `counterweight.components.ImpureComponent` when that builds something different,
  because a component depends on more than its arguments and hooks.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Added [`use_memo`](hooks/use_memo.md), which caches a value until its dependencies change,
  so a component can keep an expensive derived value, an unchanging part of its output,
  or a handler it passes to a `memo` component.
  With `check_purity` on, a cached value that a dependency missing from its list would change
  raises `counterweight.hooks.StaleMemo`.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added `counterweight.hooks.toggle`, which flips a flag through a `use_state` setter (`set_open(toggle)`),
  so toggles that land before the next render each flip the latest value,
  and a type checker rejects it for state that isn't a `bool`.
  The [`use_state`](hooks/use_state.md#updating-state-from-its-previous-value) docs show how setting state
  from a value computed from the state a render saw loses updates, and when to pass a function instead.

- [#400](https://github.com/JoshKarpel/counterweight/issues/400),
  [#404](https://github.com/JoshKarpel/counterweight/pull/404)
  Added [`use_clock`](hooks/use_clock.md), which gives a component the time
  (the wall-clock time, and how long since the app started and since the component mounted)
  while it stays pure: it re-runs when its next tick starts, ticks follow the wall clock,
  and components reading it in the same frame see the same time.
  `app` takes a `clock` to read the time from: a `SystemClock`, in UTC unless it's given a timezone,
  or a `FrozenClock` for tests and screenshots, which only an autopilot moves,
  and the `AdvanceClock` control moves either forward.
  An `interval` of `None` [pauses](hooks/use_clock.md#pausing) it, as a `null` delay pauses React's `useInterval`:
  the component keeps its last reading and the clock never re-runs it,
  and the render that gives it an interval again takes a fresh reading.
  The cookbook shows how to [animate a spinner](cookbook/spinners.md) with it.

- [#444](https://github.com/JoshKarpel/counterweight/pull/444)
  Added [animation](hooks/animation.md): `use_progress(duration, deps)`, which rises from 0 to 1 over `duration`
  and holds there, starting again whenever its `deps` change, as a CSS animation that plays once,
  and `use_loop(period, deps)`, which repeats every `period` and pauses with `is_playing=False`,
  as one whose iteration count is `infinite`.
  Both read the clock every `FRAME_INTERVAL` (20 frames a second) while they move, unless given an `interval`,
  and stop reading it while they don't, so a paused animation never re-runs its component,
  and a finished one only once more.
  `counterweight.animation` holds CSS's easing functions, to shape how an animation moves:
  `linear` and `piecewise_linear` (CSS's `linear()`), `cubic_bezier` and the curves CSS names
  (`ease`, `ease_in`, `ease_out`, `ease_in_out`), and `steps`, `step_start` and `step_end`,
  and `between`, which picks one phase out of an animation's progress, as a keyframe does.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Added [`use_controls`](hooks/use_controls.md), which gives a component a sender that hands the app a control
  from outside an input handler, such as an effect that quits when a program exits.
  The app handles a sent control as it handles one a handler returns, after the events already waiting.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  Added `counterweight.geometry.clamp(min_, val, max_)`, which clamps a number to a range.

#### Input, focus and the terminal

- [#402](https://github.com/JoshKarpel/counterweight/pull/402),
  [#429](https://github.com/JoshKarpel/counterweight/pull/429),
  [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  Added [`use_focus`](hooks/use_focus.md), which makes a component focusable, so that key presses go to it while it's focused.
  It takes `auto_focus`, to take focus on mount when nothing else has it,
  or when what has it is out of Tab order and the component mounts inside it, as `autofocus` takes focus from a page's body;
  `handle`, a `FocusHandle` a parent creates to focus a child it renders;
  `is_focusable=False`, to disable it; and `in_focus_order=False`, to leave it out of Tab order.
  The controls `FocusNext`, `FocusPrevious`, `FocusOn(handle)` and `ClearFocus` move focus,
  and `FocusNext` and `FocusPrevious` take a `within` subtree, or an element's handle, to move only inside one element.
  [`FocusOn`](hooks/use_focus.md#focusing-a-component-as-it-mounts) also focuses a component that mounts
  in the render its handler causes, before that frame is drawn, unless another control moves focus first.
  `counterweight.handlers` has `tab_focus`, `focus_receiver_on_press`, `focus_on_press` and `clear_focus`,
  which return them for Tab and for presses; nothing moves focus unless a handler does.
  A `Receiver` carries the element's `focus_handle`, whether it `is_focused`, and its `subtree`.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added [`counterweight.handlers`](input-handling/handlers.md), with `on_click(action)`, which calls `action`
  when a press on its element is released inside it,
  and `first` and `each`, which compose several handlers into the one an element takes.
  A handler can return a tuple of controls, applied in order and skipping any `None`,
  or `()` to stop an event with nothing more to do.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Mouse events say which modifier keys were held, in `is_shift_held`, `is_alt_held` and `is_control_held`,
  as the DOM's `MouseEvent` does, so a handler can match a Ctrl+click or a Shift+wheel.
  Some terminals keep Shift with the wheel for their own scrollback and never report it.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Added `Key.ControlBackslash`, `Key.ControlRightBracket`, `Key.ControlCaret` and `Key.ControlUnderscore`,
  and their Ctrl+Alt forms, so every control byte a terminal sends is a key.

- [#411](https://github.com/JoshKarpel/counterweight/issues/411),
  [#412](https://github.com/JoshKarpel/counterweight/pull/412),
  [#422](https://github.com/JoshKarpel/counterweight/pull/422)
  Added the `SetTitle` control, which sets the title of the terminal window,
  and the `title` argument to `app`, which sets it when the app starts.
  The app saves the title it started with and restores it when it quits and while it's suspended,
  on terminals that support xterm's title stack,
  and the `RestoreTitle` control brings it back while the app runs.

- [#445](https://github.com/JoshKarpel/counterweight/pull/445)
  Added the `CopyToClipboard` control, which copies text to the system clipboard,
  as a browser's `navigator.clipboard.writeText` does, by asking the terminal to with OSC 52.
  It works only where the terminal supports OSC 52, and in tmux only with `set -g set-clipboard on`.

#### Layout and scrolling

- [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  Added [scroll containers](layout/scrolling.md): a box whose overflow is `Scroll`
  (set by `overflow_scroll`, `overflow_x_scroll` or `overflow_y_scroll`)
  shows the part of its content its offset scrolls into view.
  Counterweight holds each container's offset, and after every layout keeps the content in view where it was,
  as CSS's scroll anchoring does, and clamps the offset to how far the content reaches.
  The `overflow_anchor` style field, with `overflow_anchor_auto` and `overflow_anchor_none`, turns anchoring off,
  and the `stick_to_end_x` and `stick_to_end_y` style fields, with `stick_to_end` and `unstick` and their `_x` and `_y` forms,
  keep a container that's scrolled to its end there as its content grows, as a log or a chat transcript wants.
  The controls `ScrollTo` and `ScrollBy` scroll a container named by an `ElementHandle`,
  which an element takes as its `handle`, or by a receiver's `subtree`,
  and `ScrollIntoView` scrolls every container above an element until it's in view,
  as the web's `scrollIntoView` does, aligning it as its `block` and `inline` say.
  All three apply in order to the layout of the next render,
  so they scroll the content laid out by any state change returned beside them, in the same frame.
  Moving focus scrolls the newly focused element into view.
  `counterweight.handlers` has `scroll_on_wheel` and `scroll_on_keys`, which make handlers that scroll for the wheel
  and for the arrow keys, PageUp, PageDown, Home and End,
  and pass the event on to the container outside once their own reaches an end,
  and `page_down` and `page_up`, which return the `ScrollBy` for a page of any fraction of the view.
  [`scroll_on_wheel`](input-handling/handlers.md#scrolling) scrolls sideways for the vertical wheel with Shift held,
  as browsers on Windows and Linux do.
  [`use_scroll`](hooks/use_scroll.md) returns how far the calling component's element,
  or the element with a given `ElementHandle`, is scrolled and how far it can be, as a `Scroll`,
  and a `Receiver` carries the same as its `scroll`.

- [#388](https://github.com/JoshKarpel/counterweight/issues/388),
  [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  Added the overflow utilities `overflow_visible`, `overflow_hidden` and `overflow_clip`,
  with `overflow_x_*` and `overflow_y_*` forms that set one axis.
  A box whose overflow is `Hidden`, `Clip` or `Scroll` clips its children to its padding box
  on each axis that sets it, and the mouse reaches an element only where it's painted:
  routing, `use_hovered` and `on_click` ignore the parts of an element its ancestors clip away.
  The `clip_to` style field chooses what clips an element: its parent's padding box (`clip_to_padding`, the default),
  its parent's border box (`clip_to_border`), so a child such as a border title can draw on the border of a parent that clips,
  or only the screen (`clip_to_screen`), so a popup such as a dropdown escapes every clip above it.
  `Rects` has `clip`, the region an element's ancestors let it draw in,
  and `visible`, the part of its border box inside that region.
  See [Clipping](layout/clipping.md), and the [autocomplete recipe](cookbook/autocomplete.md).

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  Added the layout utilities that taffy's flexbox and grid offer:
  sizes (`width(n)`, `height(n)`, `size(w, h)`, their `min_` and `max_` forms, and `aspect_ratio`),
  flexing (`grow(n)`, `shrink(n)`, `row_reverse`, `col_reverse`, `flex_wrap`, `flex_no_wrap` and `flex_wrap_reverse`),
  `display_flex`, `display_grid`, `display_block` and `display_none`,
  grid (`grid_template_columns`, `grid_template_rows`, `grid_row`, `grid_column`,
  and the `grid_auto_flow_*`, `justify_items_*` and `justify_self_*` utilities),
  box sizing (`border_box` and `content_box`),
  and `full`, `full_width` and `full_height`, which fill the parent after the box's margins.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added the sizing keyword utilities `min_content_width`, `max_content_width`,
  `fit_content_width` and `stretch_width`, and their `_height` counterparts,
  which size a box from its content or fill the space available after its margins.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385),
  [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  Added the constraint utilities `length(n)`, `percentage(p)`, `ratio(a, b)` and `fill(n)`,
  which split space along the parent's main axis the way ratatui's constraints of the same names do:
  a child takes its share whatever its content, in a `row` or a `col`, hiding its overflow.
  For grid, `fr(n)` is a track of `n` shares that content can't widen (`minmax(0, n fr)`),
  and `span(n)` places a child across `n` tracks.
  `grid_template_columns` and `grid_template_rows` accept a plain `int` as a track of that many cells,
  and `grid_row` and `grid_column` accept one as a grid line.
  `center_children` centers children on both axes.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added `inset(n)`, `inset_x(n)` and `inset_y(n)`, which set all four, the left and right, or the top and bottom insets;
  `inset_sides`, `margin_sides` and `pad_sides`, which set each side separately in the order of CSS's four-value shorthands;
  and `auto` margins for every side and pair of sides, from `margin_auto` to `margin_right_auto`.
  `position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height`
  centers a box over its parent at its own size, as in CSS.

#### Styles

- [#443](https://github.com/JoshKarpel/counterweight/pull/443)
  Added [attribute utilities](styles/utilities.md#attributes) that draw the text or the border characters
  bold, dim, italic, underlined or struck through (`text_bold`, `border_italic`, ...),
  each with a `not_` form (`text_not_bold`) that turns it off when merged over a style that turns it on.
  A `Chunk`'s style can be a `Style`, of which the chunk takes the `text_style`,
  so the utilities that style a `Text`, such as `text_bold | text_color("sky", 300)`,
  [style a chunk](elements/text.md#styling-parts-of-the-text) too.

- [#123](https://github.com/JoshKarpel/counterweight/pull/123),
  [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Added `content_color`, an element's background, which fills its border box beneath its padding, border and text,
  even when the element has nothing else to draw.
  An element with no margin, border, padding, text or `content_color` paints nothing,
  so an undecorated container laid over other elements leaves them visible.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Added colors the terminal decides, which follow the user's theme:
  `IndexedColor(n)`, entry `n` of the terminal's 256-color palette,
  and `TERMINAL_DEFAULT`, the terminal's default foreground where it colors text and default background where it fills one.
  Every style field that took a `Color` takes either (`AnyColor`),
  and the `*_indexed(n)` and `*_terminal_default` utilities set them wherever the color utilities do.
  Screenshots draw palette entries in `DEFAULT_PALETTE` and the defaults as white on black.
  See [Terminal colors](styles/utilities.md#terminal-colors).

- [#430](https://github.com/JoshKarpel/counterweight/pull/430)
  Added [gradients](styles/gradients.md): linear, radial and conic, with CSS's geometry, stops, hints and repeating,
  built by `linear_gradient`, `radial_gradient` and `conic_gradient` in `counterweight.gradients`.
  Any color a style holds can be a gradient: `margin_color`, `padding_color`, `content_color`,
  and the foreground and background of `border_style`, `text_style` and a chunk's style,
  each mapping it over the box it paints unless the gradient's `box` names another,
  and the `*_gradient` utilities put one in each of those places.
  Colors mix in Oklab by default, or in another of CSS's color spaces, with its hue methods for the polar ones.
  Angles and circles are in visual units, where a row is `app`'s `cell_aspect_ratio` columns tall (2 by default),
  and a gradient spans its box's corner cells' centers, so they take its end colors.
  Paint keeps each element's gradient cells from frame to frame, so a gradient that doesn't change isn't computed again.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added `counterweight.styles.merge`, which merges any number of `Style`s left to right,
  as an alternative to chaining `|`: `merge(a, b, c)` is `a | b | c`.
  It skips `None` arguments wherever they appear.

#### Text and rich text

- [#318](https://github.com/JoshKarpel/counterweight/pull/318)
  Added [text wrapping](styles/text-wrapping.md) for `Text` elements: `text_wrap_stable` (greedy),
  `text_wrap_balance` (equalizes line lengths), and `text_wrap_pretty` (Knuth–Plass, minimizes ragged lines).
  `text_wrap_none`, the default, doesn't wrap.
  Words longer than the available width are broken with a hyphen.
  A wrapping `Text`'s minimum size is its widest word, so wrapping `Text`s side by side
  in a row shrink to share it.

- [#330](https://github.com/JoshKarpel/counterweight/issues/330),
  [#414](https://github.com/JoshKarpel/counterweight/pull/414),
  [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added [`markdown_document`](rich-text/markdown.md), a component that renders a Markdown document
  (GitHub Flavored Markdown with its task lists, alerts, footnotes, bare URLs and math, and YAML front matter),
  styled by a `MarkdownStyles` with a field for each kind of block and span.
  It's a `memo` component, which parses its document again only when its arguments change,
  and `markdown`, the function it calls, returns the document as a `Div` of elements.
  Links are hyperlinks, and fenced code blocks and front matter are highlighted.
  Code blocks and tables too wide for the space they're given
  [scroll sideways](rich-text/markdown.md#wide-code-and-tables) with the wheel, as GitHub's styles scroll them,
  and a table wraps its cells as narrow as their words allow before it scrolls.
  `keeps_line_breaks=True` keeps each line break inside a paragraph, as GitHub's comments and chat apps do.

- [#330](https://github.com/JoshKarpel/counterweight/issues/330),
  [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  Added [syntax highlighting](rich-text/syntax-highlighting.md) with Pygments:
  `highlight` returns code as styled chunks, `code_style` its theme's background and text color,
  and `code_block` a `Text` of the highlighted code on that background.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414),
  [#443](https://github.com/JoshKarpel/counterweight/pull/443)
  Added [hyperlinks](rich-text/hyperlinks.md): `CellStyle`'s `link` makes a `Chunk` or `Text` a hyperlink
  that the terminal opens when it's clicked, and the `text_link(uri)` utility sets it, or with `None` unsets it.
  A link must be printable ASCII, or `CellStyle` raises `ValueError`.

#### Headless components and widgets

- [#391](https://github.com/JoshKarpel/counterweight/issues/391),
  [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added [headless components](headless/index.md) in `counterweight.headless`,
  hooks that give a component a common control's behavior and leave drawing it to the component,
  starting with [`use_text_input`](headless/use_text_input.md), which edits one line of text.
  The caller owns the value and passes its setter; the hook owns the cursor and makes the component focusable.
  It returns the value split around the cursor, an `on_input` handler for Readline's editing keys and pastes,
  an `on_press` handler that puts the cursor where a press lands and focuses the field,
  as a click in a browser's `<input>` does,
  and a `cursor_cell` element handle that its handler scrolls into view with each edit,
  so a value wider than its box scrolls to keep the cursor in view.
  `counterweight.widgets.text_input` is a bordered box built on it, with a placeholder.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added [`use_text_area`](headless/use_text_area.md), which edits text that wraps onto rows.
  It wraps the value itself, at the width the caller gives it,
  and returns the rows split around the cursor, so Up and Down move between the rows on screen, keeping their column,
  and Home, End, Ctrl+U and Ctrl+K act on the cursor's row.
  Ctrl+J and Alt+Enter insert a line break, and so does Enter with `enter_inserts_newline=True`;
  otherwise Enter bubbles, as for a form or a chat that submits on it.
  Its `on_press` handler puts the cursor where a press lands, as for `use_text_input`,
  and its `cursor_row` element handle, which its handler scrolls into view with each edit,
  keeps the cursor in view in a scroll container.
  `counterweight.widgets.text_area` is a bordered box built on it, which wraps at its own width
  and grows to fit its rows up to a `max_height` in its style, past which it scrolls.
  Both hooks take Readline's Alt+B, Alt+F, Alt+D and Alt+Backspace,
  with Alt+Left, Alt+Right and Alt+Delete, to move and delete by word.
  The [chat](https://github.com/JoshKarpel/counterweight/blob/main/src/counterweight/examples/apps/chat.py) example
  sends Markdown messages from a `text_area` to a transcript that sticks to its end as replies stream in.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added [`use_scroll_area`](headless/use_scroll_area.md), which scrolls a box with the keys, the wheel and controls,
  as Radix UI's ScrollArea does for React.
  It makes the component focusable, as browsers make a scroll container focusable, so Tab reaches it,
  and its handler scrolls for the arrows, PageUp, PageDown, Space, Home and End, and for the wheel,
  passing an event on once the area reaches an end,
  and focuses the area for a press nothing inside it claims.
  It returns the style that makes the element that scrolls a scroll container on its `axis` (`"x"`, `"y"` or `"both"`),
  clipping the other axis and sticking to the end with `stick_to_end`, to merge after any constraint utility,
  a `viewport` element handle that a parent can pass in to scroll the area from outside,
  its `scroll`, `is_at_start` and `is_at_end`, and `to_start` and `to_end` controls, as for a "jump to latest" button.
  The element that scrolls can be inside the one that's focused, with a title or a button beside it.
  `counterweight.widgets.scroll_area` is a bordered box built on it, whose border shows focus,
  styled by a `ScrollAreaStyles`.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  Added `counterweight.widgets.TextFieldStyles`, which the `text_input` and `text_area` widgets take as `styles`,
  for their box while unfocused, focused and unfocusable, their cursor, and their placeholder.
  A widget's `style` merges under the focused and unfocusable styles, so a custom border color doesn't hide which field is focused.

#### Canvas and terminals

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Added the [`Canvas`](elements/canvas.md) element, a leaf whose content box its painter draws cell by cell,
  sized as an `<img>` is, from its painter's natural size and aspect ratio.
  A painter is any object with a `natural_size`, `keeps_aspect_ratio` and `draw(width, height)`,
  which returns rows of styled graphemes whose unset styles come from the canvas;
  a canvas draws again only when its painter isn't equal to the last one or its box changes size.
  `counterweight.painters` holds `Pixels`, a picture as RGBA bytes,
  which `Pixels.from_image` makes from an image decoded by [Pillow](https://pillow.readthedocs.io/),
  and `HalfBlocks`, a painter that draws a `Pixels` two pixels to a cell with `▀`,
  scaling and placing it as CSS's `object-fit` and `object-position` do,
  and whose `pixels_at` finds the pixels a cell shows, for mouse input.

- [#430](https://github.com/JoshKarpel/counterweight/pull/430)
  Added `HalfBlockGradient`, a canvas painter that fills its canvas with a gradient two pixels to a cell,
  and `Pixels.from_gradient`, a picture of one.

- [#444](https://github.com/JoshKarpel/counterweight/pull/444)
  Added [`Paint.as_painter`](elements/canvas.md#drawing-a-screenshot), a `Canvas` painter, a `PaintView`,
  that draws a region of a paint, such as a screenshot's frame, as it was when it was made.
  `Paint.cells_in` takes a region's cells row by row, as a value, to rearrange or mix with another picture's,
  and `counterweight.paint.rows_of` turns cells back into a painter's rows,
  drawing either half of a wide character whose other half isn't beside it as a space, as a terminal does.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Added `counterweight.emulator`, a terminal emulator
  ([libghostty-vt](https://ghostty.org), through [pyghostty](https://github.com/AnswerDotAI/pyghostty))
  that turns the bytes a program writes into what its terminal shows.
  An `Emulator` is fed bytes, answers the program's queries through `on_reply`, keeps a `scrollback`,
  and snapshots into immutable `Screen` values:
  rows of styled graphemes, the cursor, the title, and the modes that change how the program's input is encoded.
  `counterweight.painters.ScreenView` is the `Canvas` painter that draws a `Screen`.
  A program's palette colors stay palette entries, so they follow the user's theme.
  Counterweight imports libghostty's bindings only when an app emulates a terminal,
  so an app that doesn't starts without them.
  See [Emulators and Pseudo-Terminals](terminals/emulators.md).

- [#429](https://github.com/JoshKarpel/counterweight/pull/429),
  [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  Added `counterweight.pseudoterminal`, which runs a program on a pseudo-terminal, as a terminal window does,
  and hands back the bytes it writes, standard output and standard error together.
  `run_pty` runs one until it exits, returning `Exited` with its status, `FailedToStart` with the reason,
  or `TimedOut` if it outran its `timeout`, and hands out a `PtyConnection` that writes to the program and resizes its terminal.
  `use_pty` runs one while its component is mounted, starting it once its size is positive,
  so a terminal sized from `use_rects` starts at its real size,
  and starting it again when its `argv`, `env` or `cwd` change.
  Once the program exits, or it's cancelled, its whole process group is hung up as closing a terminal window does,
  with `SIGHUP`, then `SIGTERM` and `SIGKILL` a `hangup_grace` apart,
  so nothing it started outlives it; `use_pty` does this in the background, so it doesn't hold up rendering.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429),
  [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  Added [one-shot commands](terminals/commands.md) in `counterweight.commands`:
  running a program that's expected to exit, and showing everything it printed, colors and all,
  as a terminal would have shown it.
  `use_command` returns a `Command`, whose `run(argv)` starts a program on a pseudo-terminal `columns` wide
  (waiting until that's positive, so it can come from `use_rects`) and `rows` tall, in `cwd`,
  with standard input on `/dev/null` and `PAGER` and `GIT_PAGER` set to `cat`,
  whose `cancel` hangs it up, and whose `latest` is a `CommandRun` value
  whose output updates at most once a frame while the program runs,
  and whose outcome is `Starting`, `Running`, `Exited`, `FailedToStart`, `Cancelled` or `TimedOut`.
  A run's output is a `counterweight.painters.Transcript`, a `Canvas` painter as wide as the run's terminal
  and as tall as the lines it printed, keeping the last `max_lines`,
  and `Transcript.of` builds one from output recorded ahead of time.
  `command_output` shows a run in a `scroll_area` that follows its end, with its outcome beneath.
  The [slides](https://github.com/JoshKarpel/counterweight/blob/main/src/counterweight/examples/apps/slides.py) example
  runs a command on each slide when it's shown.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429),
  [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  Added [embedded terminals](terminals/embedding.md): running an interactive program, such as a shell or an editor,
  in a box that shows its screen and sends it the input the box receives, as a multiplexer's pane does.
  `counterweight.headless.use_terminal` runs one on a pseudo-terminal while its component is mounted,
  emulates its terminal, snapshotting it at most once a frame, and makes the component focusable,
  returning an `EmbeddedTerminal`: the `Screen`, a `ScreenView` painter that draws the cursor while focused,
  the program's status, a `write` that sends it bytes,
  and an `on_input` handler for the `Canvas` the component draws it in.
  While focused, the handler sends the program every key press and paste, Ctrl+C and Ctrl+Z included,
  and the mouse events it asked for,
  and a program that asked gets focus events as the component gains and loses focus.
  A handler put before it with `first` takes keys first, as a prefix key does,
  and `skips` names keys the program isn't sent, which bubble up to the app's handlers instead.
  `counterweight.widgets.terminal` is a bordered box built on it, sized by its `style`,
  whose `intercept` handler sees each event before the program does.
  The [multiplexer](https://github.com/JoshKarpel/counterweight/blob/main/src/counterweight/examples/apps/multiplexer.py) example
  runs shells side by side with direct hotkeys, as zellij does, showing them along the bottom,
  and closes a pane when its shell exits.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Added [running programs on the app's terminal](terminals/programs.md), as `git commit` runs an editor.
  `Suspend.to_program` suspends the app, runs a program on the app's `input_stream` and `output_stream`
  until it exits, with the app's environment and `env` (or only `env` with `clear_env`) in `cwd`,
  and calls `on_exit` with `Exited` or `FailedToStart`.
  While it runs, the app swallows `SIGINT` and `SIGQUIT`, as POSIX's `system()` does,
  so Ctrl+C in a pager reaches the pager without quitting the app.
  `Suspend.to_edit_file` opens a file in the user's editor, `$VISUAL`, then `$EDITOR`, then `vi`,
  and calls `on_exit` with how the editor exited.
  `Suspend.to_edit_text` edits a string the same way, through a file whose name sets the editor's highlighting,
  and calls `on_edit` with `Edited(text)`, or with how the editor failed, so vim's `:cq` abandons the edit.
  `counterweight.programs` holds the functions they run,
  `run_program`, `edit_file`, `edit_text` and `preferred_editor`.

#### Testing and recording

- [#436](https://github.com/JoshKarpel/counterweight/pull/436),
  [#431](https://github.com/JoshKarpel/counterweight/pull/431),
  [#444](https://github.com/JoshKarpel/counterweight/pull/444)
  Added the autopilot steps [`Wait`](autopilot.md#waiting-for-real-work), which holds the autopilot back
  for a duration of real time, and `WaitFor`, which holds it back until a condition is true of the frame on screen,
  raising `AutopilotTimedOut` after its timeout,
  while the app keeps handling events and rendering, so it can wait on work like a subprocess.
  A `FrozenClock` runs in real time while the autopilot waits,
  so a recording can show real work at its real pace between steps that `AdvanceClock` paces.
  `typed(text)` gives the key presses that type some text, one per grapheme cluster,
  `showing(text)` waits until some text is on screen,
  `advance(by)` moves the clock on a frame of the animation hooks at a time, so an animation plays out,
  and `paced(steps, pause)` puts a step before each of some steps, such as an `AdvanceClock` to pace a recording.
  They give plain lists of steps, to combine with each other and with `itertools` and `more-itertools`.

- [#436](https://github.com/JoshKarpel/counterweight/pull/436)
  Added [recording](autopilot.md#recording): `app` takes a `Recording`, and writes what the app draws,
  with its timing, to an [asciicast v3](https://docs.asciinema.org/manual/asciicast/v3/) file
  that asciinema-player and `asciinema play` play back, whether it's headless or on a terminal.
  Each frame is recorded as the cells it changed, timed by the app's clock,
  so with a `FrozenClock` an autopilot's `AdvanceClock`s are the recording's timing,
  and it comes out the same on every run.
  It records the screen's size when it changes, and how the app exited,
  and cuts the time the app spends suspended out, with a `suspended` marker where the cut is.
  A `Recording` also takes a `title`, an `idle_time_limit`, and a `Theme` for the colors the app leaves to the terminal.
  `Recording(input=True)` records the input the app handles too; it's off by default, since it records everything typed.
  The [`Marker`](input-handling/controls.md) control marks a point in the recording that players show as a chapter.

#### Examples and documentation

- [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  Counterweight ships with its [examples](examples.md): a few complete apps, such as a chat, a Markdown viewer,
  a terminal multiplexer and Wordle, and the snippets the docs show, each of which runs on its own.
  `counterweight examples list` lists them, `run` runs one, `show` prints its source, highlighted on a terminal,
  and `copy` writes a file of your own that runs it, to start from.
  `counterweight examples gallery` browses them all, with each one's description and source,
  and runs the one selected in place.
  `counterweight.examples` is importable, but not part of the public API.

- Showed every hook, element, input handling page, style page and terminal feature
  with runnable examples, screenshots and recordings, each screenshot with a copyable plain-text twin,
  and added a quick start and a showcase of the example apps to the [home page](index.md).

- Documented [`app`](app.md) and what each of its parameters is for on a page of its own,
  and gave every public name a docstring and a place in the API reference of the page that covers it.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  Added a [Layout](layout/index.md) section to the documentation:
  a guide to choosing between flexbox and grid,
  and pages on sizing, splitting space, alignment, spacing and borders, layering, clipping and scrolling.

- [#395](https://github.com/JoshKarpel/counterweight/pull/395)
  Documented every style utility on the [utilities page](styles/utilities.md),
  grouped by family: what each constant sets, each function's signature,
  and the color palette.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  Documented how to find where a frame's time goes, which components a frame re-runs,
  and how to skip the rest with `memo=True` and `use_memo`, with their failure modes,
  in [Performance](performance.md).

- [#394](https://github.com/JoshKarpel/counterweight/pull/394),
  [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  Documented how Counterweight compares with Textual, Ink, OpenTUI, Bubble Tea, Ratatui and iocraft,
  and what it doesn't do, in [Ecosystem](ecosystem.md).

- [#436](https://github.com/JoshKarpel/counterweight/pull/436)
  Documented driving an app with an autopilot and recording it, in [Autopilot and Recording](autopilot.md).

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  Documented how components keep their state across renders, how to use keys to move or reset that state,
  and that a component must call the same hooks in the same order on every render,
  with how to move a hook that is only sometimes needed into a child component.

- Documented what [`use_ref`](hooks/use_ref.md) is for,
  and why a component shouldn't read or write a ref while rendering.

- Added cookbook recipes for [draggable components](cookbook/draggable-components.md) that stay inside their parent,
  a tmux-style [prefix key](cookbook/prefix-keys.md), [spinners](cookbook/spinners.md),
  [sortable tables](cookbook/sortable-tables.md), and [autocomplete](cookbook/autocomplete.md).

### Changed

#### Modules

- **Breaking:** the framework's internal modules start with an underscore,
  such as `counterweight._app`, `counterweight._layout`, `counterweight.hooks._hooks` and `counterweight.styles._styles`,
  and every public module lists its public names in `__all__`, so each public name has exactly one place to import it from.
  Import `app` from `counterweight` (`from counterweight import app`), where `DEFAULT_UNCLAIMED_KEYS` and `__version__` are too,
  and import hooks and styles from their packages, such as `from counterweight.styles import Style`.
  `counterweight.hooks` no longer re-exports `Rects`, which is in `counterweight.geometry`.

#### App and components

- [#271](https://github.com/JoshKarpel/counterweight/issues/271),
  [#401](https://github.com/JoshKarpel/counterweight/pull/401)
  **Breaking:** `app` takes the root component already called, as `app(root())` rather than `app(root)`,
  so a root component can take arguments like any other: `app(root(Path(sys.argv[1])))`.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  **Breaking:** a render calls only the components whose state changed and the components they return,
  instead of every component, and keeps the previous render's output for the rest,
  so a component whose output depends on anything but its arguments and hooks goes stale.
  `check_purity` catches such a component in tests.
  An effect with `deps=None` runs after every render of its own component,
  rather than after every render of the app.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394)
  **Breaking:** an error raised while the app runs, in a component, a handler or an effect,
  propagates out of `app` as itself rather than wrapped in an `ExceptionGroup`,
  after the terminal is restored, so its traceback ends at the line that raised it
  and callers can catch it by its own type.
  Errors raised at the same moment from more than one effect are raised together in an `ExceptionGroup`.

- [#408](https://github.com/JoshKarpel/counterweight/pull/408)
  Cancelling the task running `app` raises `CancelledError` out of it once the terminal is restored,
  as asyncio expects, so `asyncio.timeout` and `wait_for` around an app can tell it was cancelled.
  Previously `app` returned as if the app had quit.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  **Breaking:** a component that calls a different number of hooks than on its previous render
  raises `counterweight.hooks.InconsistentHookExecution`.
  Previously calling more or fewer hooks passed silently, and a skipped `use_effect` kept running.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  **Breaking:** component keys are strings only, so `with_key` no longer accepts an `int`:
  convert numeric ids with `str()`.
  Keyed sibling components that share a key raise `counterweight.components.DuplicateKey`.

- [#315](https://github.com/JoshKarpel/counterweight/pull/315)
  **Breaking:** `Style`, `CellStyle`, `Div`, `Text`, `Chunk` and the hooks' types are frozen dataclasses
  rather than Pydantic models (`Ref` is a mutable one), so they don't validate their fields at runtime
  and have none of Pydantic's methods, such as `model_copy`.
  `Div` and `Text` no longer have a `type` field, and `counterweight.types` is removed.

- [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  **Breaking:** a `Suspend` handler takes one argument, the terminal the app handed back, as `TerminalStreams`,
  so it can run a program on the terminal the app draws on even when that isn't standard output.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  The setter returned by `use_state` is the same object on every render of a component,
  so including it in an effect's `deps` doesn't rerun the effect each render.

- [#394](https://github.com/JoshKarpel/counterweight/pull/394),
  [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  [`use_rects`](hooks/use_rects.md) takes an optional `ElementHandle`, and reports the rectangles of the element
  with that handle rather than the calling component's own, as a React component measures an element through a ref,
  so a component can measure an element a child component draws.
  A component that calls it renders again as soon as any of the rectangles it read move.
  Previously it rendered again only once something else started a render,
  so a component that mounted after the first frame read empty rectangles until then.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385),
  [#414](https://github.com/JoshKarpel/counterweight/pull/414),
  [#444](https://github.com/JoshKarpel/counterweight/pull/444)
  **Breaking:** counterweight logs through the standard library's `logging`, and doesn't configure structlog.
  While an app runs, its log records
  (`logging.getLogger(__name__).debug("...", extra={...})`) are written to the devlog off the render loop
  by [without-logging](https://www.without.help/without-logging/):
  by default, counterweight's and the app's own at every level (the app's being the top-level package
  of the module that defines its root component), and every other logger's from `INFO` up,
  so a library that logs at `DEBUG` on a hot path costs nothing unless an app asks for its records.
  `app`'s `log_levels` sets levels by logger name, as `logging.config` does, over those defaults.
  The devlog is a single JSON-lines file, which `counterweight devlog` renders for reading
  (`--json` prints the raw lines, and `--last N` the last `N` messages).
  An app that runs while another has the devlog open, such as one run headless in another's handler,
  writes into that devlog, at the levels the other app set, rather than truncating it.
  Its messages don't carry `elapsed_ns` timings:
  to see where a frame's time goes, profile the app with Python's sampling profiler
  (`python -m profiling.sampling run app.py`).

- [#406](https://github.com/JoshKarpel/counterweight/pull/406)
  **Breaking:** the `counterweight` CLI is built on [without-cli](https://www.without.help/without-cli/),
  and shell completion (`--install-completion`) is gone.
  `counterweight` with no command prints a short usage error instead of the full help,
  and `counterweight --version` prints the version as `counterweight version` does.

#### Input and focus

- [#416](https://github.com/JoshKarpel/counterweight/pull/416),
  [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  **Breaking:** the app reads the terminal raw, as tmux does,
  so Ctrl+C, Ctrl+Z, Ctrl+\\, Ctrl+S and Ctrl+Q reach it as key presses rather than the terminal acting on them,
  and Enter, a carriage return, is `Key.Enter` while Ctrl+J, a line feed, is `Key.ControlJ`, where both were `Key.Enter`.
  `app` takes `unclaimed_keys`, what a key press does when no handler on its path claims it,
  as a browser takes a key's default action unless a listener prevents it.
  `DEFAULT_UNCLAIMED_KEYS` gives Ctrl+C `Quit` and Ctrl+Z `Suspend.to_shell()`,
  which suspends the app as a shell job until the shell resumes it with `fg`,
  stopping its whole process group as the terminal's Ctrl+Z does, so `uv run` and the like stop with it.
  Pass `{}` for no defaults, or merge onto them to change some.
  A handler that claims Ctrl+C keeps it, such as to cancel a command.
  See [Keys the terminal would act on](input-handling/events.md#keys-the-terminal-would-act-on).
  Previously Ctrl+Z and Ctrl+\\ stopped and killed the app without handing the terminal back,
  and Ctrl+S froze its output until Ctrl+Q.
  An interrupt sent from outside, with `kill -INT`, quits the app and `app` returns;
  a second, before a stuck app has quit, goes to the interrupt handler `app` replaced,
  which for `asyncio.run` raises `KeyboardInterrupt`.
  An app whose render loop is stuck can't be quit with Ctrl+C, since nothing reads it.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** a key press goes to the focused element, or to the root component's element when nothing is focused,
  then bubbles through its ancestors until a handler returns something other than `None`,
  and a key press nothing claims gets its `unclaimed_keys` default.
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

- [#402](https://github.com/JoshKarpel/counterweight/pull/402),
  [#415](https://github.com/JoshKarpel/counterweight/pull/415)
  **Breaking:** `Div` and `Text` take one `on_input` handler in place of `on_key` and `on_mouse`.
  It receives key presses, pastes and mouse events, so one `match` case can handle `Down` and the scroll wheel alike,
  and a `Receiver` describing the element, whose `rects` and `relative` locate a mouse event inside it,
  and whose `is_target` tells the event's target from an ancestor it bubbled to.
  A handler that takes only the event, or annotates it as `KeyPressed` or `MouseEvent`, fails to type-check;
  annotate it as `InputEvent` and match on the event's class.
  `Rects` lives in `counterweight.geometry`, and `counterweight.hooks` still exports it;
  it's keyword-only, and has `clip` and `visible` fields.

- [#391](https://github.com/JoshKarpel/counterweight/issues/391),
  [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  **Breaking:** the app turns on the terminal's bracketed paste mode,
  so pasted text arrives as one [`Pasted`](input-handling/events.md#handling-pastes) event holding all of it,
  routed to the focused element like a key press, with its line breaks as `"\n"`.
  Previously it arrived as key presses, and its line breaks as Enter.
  `counterweight check-input` shows pastes too.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  **Breaking:** keys pressed with Alt arrive as one key press:
  `Key.AltEnter`, `Key.AltBackspace`, `Key.ControlAltA` and the other Ctrl+Alt letters,
  `Key.AltUp` and the other navigation keys, `Key.AltF1` through `Key.AltF12`,
  and `"alt+"` before the text for text, such as `"alt+b"`.
  Previously Alt with text, Enter or Backspace arrived as Escape and then the key,
  and Alt with an arrow, navigation or function key was dropped.

- [#318](https://github.com/JoshKarpel/counterweight/pull/318),
  [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** `Key.Space` is `" "` rather than `"space"`,
  and `Key.ControlSpace` is `"ctrl+space"`, like every other key, rather than `"ctrl-space"`.
  Code that matched on the string value must be updated;
  matching on the enum member (`Key.Space`) is unaffected.

#### Layout

- [#305](https://github.com/JoshKarpel/counterweight/pull/305),
  [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** layout is [taffy](https://github.com/DioxusLabs/taffy)'s flexbox and grid,
  through [waxy](https://github.com/JoshKarpel/waxy), with CSS's semantics.
  `Style.layout` is a `waxy.Style`, which the layout utilities set.
  Elements size to their content and don't grow to fill their parent unless given `grow(n)`,
  where in `0.0.9` every element took a share of its parent's spare space, with a `weight` of 1.
  An app keeps one layout tree for its lifetime, so taffy reuses the layout of every element
  whose style, text and children are unchanged, and a `Text` is wrapped at most once per width it is measured at.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  **Breaking:** the spacing utilities are functions rather than one constant per size:
  `pad(n)`, `pad_x(n)`, `pad_y(n)`, `pad_top(n)` and the other sides,
  `margin(n)`, `margin_x(n)`, `margin_y(n)`, `margin_top(n)` and the other sides,
  `gap(n)`, `gap_width(n)` and `gap_height(n)` for `gap_children_N`,
  `grow(n)` for `weight_N`, and `border_contract(n)` for `border_contract_N`.
  Write `pad(1)` where you wrote `pad_1`.
  `weight_none` and `align_self_none` are removed.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  **Breaking:** `absolute(x, y)` and `relative(x, y)` are `position_absolute` and `position_relative`,
  with offsets set by `inset_left(n)`, `inset_top(n)`, `inset_right(n)` and `inset_bottom(n)`.
  `fixed(x, y)` is removed, since taffy has no fixed positioning.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** borders work as they do in Tailwind.
  A border side is drawn where its width in `Style.layout` is 1, and `border_kind` only chooses the characters.
  `border_kind` defaults to `BorderKind.Light`, so the new `border` utility alone draws a light border,
  and the `border_<kind>` utilities don't reserve space or draw anything on their own:
  write `border | border_heavy` where you wrote `border_heavy`.
  `border_top`, `border_bottom`, `border_left` and `border_right` set one side, the new `border_x` and `border_y`
  set a pair, and each has a new `_0` form (`border_0`, `border_top_0`, ...) that clears its sides,
  so sides compose: `border_top | border_left` draws both.
  A `border_kind` of `None` (`border_none`) removes the border along with the space reserved for it.
  A border width in `Style.layout` other than `Length(0)` or `Length(1)` raises `ValueError`.
  The edge combinations such as `border_top_left` and `border_top_bottom` are removed:
  use `border`, or compose sides as in `border_top | border_left`.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  The `*_center` and `*_end` alignment utilities
  (`justify_children_*`, `align_children_*`, `align_self_*`, `justify_items_*`, `justify_self_*`)
  use CSS's safe alignment: content too large for its container starts at the start edge
  instead of overflowing past it.
  Each has an `*_unsafe` counterpart, such as `justify_children_center_unsafe`,
  that centers or end-aligns overflowing content anyway.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305),
  [#315](https://github.com/JoshKarpel/counterweight/pull/315)
  **Breaking:** `counterweight.geometry.Rect` and `Edge` are removed, and `Rects` holds `Region`s.
  A `Region` is keyword-only (`left`, `top`, `right`, `bottom`), its `right` and `bottom` are exclusive
  (the first column and row outside it), so `width` and `height` count cells,
  and its corner properties (such as `top_left`) are `Position`s.
  A `Position` is a frozen dataclass rather than a `NamedTuple`, so it doesn't unpack or index like a tuple.

- [#416](https://github.com/JoshKarpel/counterweight/pull/416)
  **Breaking:** a `Text` overflows its box, as CSS's text does:
  a line wider than its content box runs past it, and rows beyond its height draw below it,
  until an ancestor whose overflow is `Hidden`, `Clip` or `Scroll` cuts them off.
  Previously a `Text` cut its lines off at its content box.
  A `Text` that should cut its text off takes `overflow_hidden`, which cuts at its padding box,
  as the constraint utilities set.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** `z` follows CSS's stacking contexts.
  An element that sets `z`, `z(0)` included, paints with its descendants as one layer at its `z`,
  and its descendants' `z` orders them only among each other,
  while an element that sets no `z` leaves its descendants to be layered alongside it.
  Children always paint over their parent, and a negative `z` paints beneath the rest of its stacking context
  but over the element that forms it.
  Previously every element was sorted by `z` in one flat order, where an element that set none had `z` 0,
  so an element with a higher `z` than its children painted over them,
  and an element with a negative `z` painted beneath every element, its own parent included.

#### Styles

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** every field of a `CellStyle`, and of a `Style` except `layout`, `border_style` and `text_style`,
  starts out as the `counterweight.styles.UNSET` sentinel rather than its default value,
  so reading a field of a style you built can return `UNSET`;
  `border_style` and `text_style` start out as empty `CellStyle`s.
  Merging with `|` takes the right side's value wherever it's set, even to the default,
  and unset fields take their values from `counterweight.styles.STYLE_DEFAULTS` and `CELL_STYLE_DEFAULTS`.

- [#305](https://github.com/JoshKarpel/counterweight/pull/305),
  [#443](https://github.com/JoshKarpel/counterweight/pull/443)
  **Breaking:** the color utilities are functions rather than one constant per color and shade:
  `text_color`, `text_bg`, `border_color`, `border_bg`, `margin_color` and `padding_color`, and the new `content_color`.
  Write `text_color("slate", 500)` where you wrote `text_slate_500`, and `border_color("slate", 500)` for `border_slate_500`.
  Each takes a palette name and shade, or any color:
  a `Color`, such as `rose_200` or `Color.from_hex("#fbbf24")`, an `IndexedColor`, `TERMINAL_DEFAULT`, or a gradient.

- [#443](https://github.com/JoshKarpel/counterweight/pull/443)
  **Breaking:** `from counterweight.styles.utilities import *` brings in only the utilities, the palette's colors,
  and the `ColorName`, `Shade` and `Side` types, not the names the module imports,
  such as `Style`, `Color`, `CellStyle` and `BorderKind`.
  Import those from `counterweight.styles` instead.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  **Breaking:** an element's margin is painted only where its style sets `margin_color`,
  so a margin leaves whatever lies beneath it visible, as on the web.
  Previously every element that painted anything filled its whole margin box black,
  so an absolutely positioned box with large margins blanked out its parent.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  `Color.from_hex` accepts the CSS shorthand `#rgb` as well as `#rrggbb`,
  and raises `ValueError` for any other number of digits
  instead of dropping the extra digits of a color like `#rrggbbaa`.

#### Elements, painting and output

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  **Breaking:** a `Div`'s `children` is a tuple, and so is a `Text`'s `content` when it's chunks,
  so an element is a value that can be cached and shared without anything changing it afterwards.
  Pass `(a, b)` or `tuple(...)` where you passed a list.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** a `Screenshot` handler receives a `counterweight.paint.Frame`
  instead of an SVG `ElementTree`; call `frame.svg()` or `frame.text()` to encode it.
  A frame's `paint` is a `counterweight.paint.Paint`, a screen-sized grid of cells:
  index it with a `Position` or an `(x, y)` pair, or read it a row at a time with `rows()`.
  `Screenshot.to_file` chooses the encoding from the path's suffix
  (`.svg` for SVG, `.txt` for text with ANSI escape codes, and `ValueError` for any other),
  always indents SVGs, and doesn't take `indent`.
  `Screenshot.to_stream` prints a screenshot as a text grid
  (with or without ANSI escape codes), useful for debugging layout and in tests.
  Every `Screenshot` requested in the same render cycle receives the same frame,
  where previously only the last one ran.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385),
  [#398](https://github.com/JoshKarpel/counterweight/pull/398)
  **Breaking:** the painted cell `counterweight.paint.P` is renamed `Cell`, and its `char` is renamed `grapheme`.
  It is a frozen dataclass of a grapheme cluster and its resolved style, and doesn't carry its element's `z`.
  A cluster two cells wide is followed by a continuation `Cell` whose `grapheme` is `""`.
  `counterweight.elements.CellPaint`, a grapheme cluster and its unresolved `CellStyle`,
  is renamed `StyledGrapheme`, its `char` is renamed `grapheme`,
  and its `width` is the number of cells the cluster takes.

- [#176](https://github.com/JoshKarpel/counterweight/issues/176),
  [#410](https://github.com/JoshKarpel/counterweight/pull/410)
  Each frame is written as one [synchronized update](https://github.com/contour-terminal/vt-extensions/blob/master/synchronized-output.md),
  so terminals that support it show the whole frame at once instead of tearing partway through drawing it,
  and redrawing the screen after a resize or a suspension doesn't flash it blank first.

- [#385](https://github.com/JoshKarpel/counterweight/pull/385),
  [#425](https://github.com/JoshKarpel/counterweight/pull/425),
  [#430](https://github.com/JoshKarpel/counterweight/pull/430)
  Painting and writing a frame costs less.
  Elements paint straight into one screen-sized grid of cells, a row at a time,
  an element's text and border are cached wherever it moves on the screen,
  and a long `Text` paints only the rows inside its clip.
  The changed cells are written with one cursor move per run of them,
  and a style change only where the style changes, sending only the colors when nothing else changes.

#### Dependencies

- [#305](https://github.com/JoshKarpel/counterweight/pull/305),
  [#315](https://github.com/JoshKarpel/counterweight/pull/315),
  [#385](https://github.com/JoshKarpel/counterweight/pull/385),
  [#398](https://github.com/JoshKarpel/counterweight/pull/398),
  [#406](https://github.com/JoshKarpel/counterweight/pull/406),
  [#409](https://github.com/JoshKarpel/counterweight/pull/409),
  [#414](https://github.com/JoshKarpel/counterweight/pull/414),
  [#429](https://github.com/JoshKarpel/counterweight/pull/429)
  Counterweight depends on [waxy](https://github.com/JoshKarpel/waxy) for layout,
  [wcwidth](https://github.com/jquast/wcwidth) for text width,
  markdown-it-py, mdit-py-plugins and Pygments for rich text,
  [pyghostty](https://github.com/AnswerDotAI/pyghostty) for terminal emulation,
  [Pillow](https://pillow.readthedocs.io/) for images,
  and without-cli, without-logging and without-streams for the CLI and the devlog.
  It no longer depends on typer (nor, through it, click, rich and shellingham), pydantic, structlog, parsy or cachetools.

### Fixed

- [#431](https://github.com/JoshKarpel/counterweight/pull/431)
  An autopilot hands the app each step once the renders the last one caused are painted,
  and the effects they started have run up to where each first waits on something, as a person's next key press would.
  Previously effects didn't start until the autopilot ran out of steps, so `use_mouse` and `use_hovered`
  never saw its mouse events.

- [#444](https://github.com/JoshKarpel/counterweight/pull/444)
  An app run inside another, such as one rendered headless in another's `Screenshot` handler,
  doesn't leave the other's state setters sending their updates to it,
  where they were lost, so the other app never re-rendered for them.

- [#407](https://github.com/JoshKarpel/counterweight/issues/407),
  [#409](https://github.com/JoshKarpel/counterweight/pull/409)
  Terminal input is parsed incrementally, so typed text arrives intact:

  - Text beyond ASCII is decoded as UTF-8, one `KeyPressed` per grapheme cluster (`"é"`, `"日"`).
    Previously it was dropped, along with everything else read alongside it.
  - An escape sequence Counterweight doesn't recognize (such as Ctrl+digit in some terminals) is skipped.
    Previously it arrived as an Escape key press followed by its characters,
    or was dropped with the rest of the read.
  - An escape sequence or UTF-8 character split between two reads is held over and completed by the next one,
    and a lone `ESC` is the Escape key once no more input follows for 50 milliseconds.
    Previously a split sequence turned into stray key presses, most often during a flood of mouse motion.

- [#125](https://github.com/JoshKarpel/counterweight/pull/125),
  [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  The mouse wheel is reported as the new `MouseScrolledUp` and `MouseScrolledDown` events, as xterm defines them,
  with Shift, Alt or Control held too, and the horizontal wheel as `MouseScrolledLeft` and `MouseScrolledRight`.
  Previously all of these were reported as presses of buttons 1 to 4,
  so scrolling, or a sideways trackpad swipe, clicked whatever was under the pointer.
  Buttons 8 to 11, such as back and forward, are reported by their own numbers
  rather than as buttons 1 to 4.

- [#125](https://github.com/JoshKarpel/counterweight/pull/125)
  `counterweight check-input` works. Previously its input thread crashed at startup.

- [#402](https://github.com/JoshKarpel/counterweight/pull/402)
  Home, Page Up and Page Down are reported, as the new `Key.Home`, `Key.PageUp` and `Key.PageDown`,
  and so is every key the `Key` enum names with Shift, Control, or both,
  such as `Key.ShiftHome`, `Key.ControlPageDown` and `Key.ControlF5`,
  with Shift and F1 to F12 reported as F13 to F24, as xterm does.
  Previously only the arrow keys and Delete were reported with modifiers.
  Control+Shift+Delete is reported as `Key.ControlShiftDelete` rather than `Key.ControlShiftInsert`.

- [#392](https://github.com/JoshKarpel/counterweight/issues/392),
  [#398](https://github.com/JoshKarpel/counterweight/pull/398)
  Text is measured, wrapped and painted by grapheme cluster and its display width, as measured by wcwidth,
  so CJK characters and emoji take two cells and don't push the rest of their line out of place,
  combining marks and joined emoji (`👩‍💻`) stay whole,
  and zero-width characters such as zero-width spaces take no cells.
  See [wide characters](elements/text.md#wide-characters).

- [#392](https://github.com/JoshKarpel/counterweight/issues/392),
  [#398](https://github.com/JoshKarpel/counterweight/pull/398)
  Control characters in text other than line breaks, such as tab and escape,
  are drawn as symbols (`␉`, `␛`) rather than written to the terminal, where they ran as commands.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  Calling a `use_state` setter after its component has unmounted does nothing,
  instead of updating orphaned state and triggering a render that changes nothing.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  A component replaced by a plain element at the same position is unmounted:
  its effects are cancelled, and components nested under it start with fresh state.
  Previously the element inherited the component's hooks, so its effects
  (including `use_mouse` listeners) kept running.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  Effects that rerun or unmount in a render are cancelled concurrently,
  and all of them finish before any effect starts,
  so an effect's cleanup always finishes before its replacement or a sibling's setup begins.
  Previously a rerun effect's new task started before the old one was cancelled.

- [#386](https://github.com/JoshKarpel/counterweight/pull/386)
  Keyed sibling components are matched by key across renders rather than by position,
  so reordering, inserting, or removing keyed children keeps each one's state and effects.
  Unkeyed children match the unkeyed child at the same index.

- [#408](https://github.com/JoshKarpel/counterweight/pull/408)
  `app` stops reading keys from the terminal before it returns,
  so input typed afterward reaches whatever runs next.
  Previously its key-reading thread kept running and consumed that input.

- [#414](https://github.com/JoshKarpel/counterweight/pull/414)
  SVG screenshots draw text that is bold, dim, italic, underlined or struck through,
  instead of drawing it plain.

### Removed

- [#305](https://github.com/JoshKarpel/counterweight/pull/305)
  **Breaking:** the style types `Border`, `BorderEdge`, `Margin`, `Padding`, `Span`, `Typography`,
  `Relative`, `Absolute`, `Fixed`, `Flex` and `Inset` are removed.
  Sizes, spacing and position live in `Style.layout`, a `waxy.Style`, which the layout utilities set,
  and colors, borders and text settings are fields of `Style` itself,
  such as `margin_color`, `border_kind`, `border_style`, `text_style`, `text_justify` and `text_wrap`.

- [#165](https://github.com/JoshKarpel/counterweight/pull/165),
  [#385](https://github.com/JoshKarpel/counterweight/pull/385)
  **Breaking:** dropped support for Python `3.11` through `3.14`.
  Python `3.15` or later is required.

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
